"""Reenvio/reprocessamento do Comitê de IA para divergências pendentes/travadas.

PROBLEMA QUE RESOLVE
--------------------
O Comitê de IA é disparado UMA ÚNICA VEZ, INLINE, dentro de
``backend.pipeline.processar`` — só quando o Motor de Comparação encaminha para
``comite_de_ia`` (houve divergência) E há ``infracoes_detectadas`` E o Comitê
está habilitado (ver pipeline.py linhas ~205-222). O Comitê usa Vertex AI/Gemini
(``backend/committee/comite.py``); quando o Vertex devolve 429 (quota) ou 403, a
2ª passada falha. Hoje isso deixa o exame em estados inconsistentes:

  • ``stage = 'auditoria'`` com ``comite_concluido = 0`` — a divergência foi para
    a fila do Auditor SEM nunca ter passado pelo Comitê (não existe linha em
    ``exam_comite_laudos``). Em produção: ~141 exames.
  • ``stage = 'comite'`` — tem laudo, mas o exame ficou travado nessa etapa
    (re-processar pode ser desejado após a quota voltar). Em produção: 6 OS.

A derivação desses estágios vive na view canônica ``v_exams_overview``
(migration 027): ``comite_concluido = EXISTS(SELECT 1 FROM exam_comite_laudos
WHERE exam_id = e.id)`` e ``stage`` deriva de ``divergente`` + ``comite_concluido``.

O QUE ESTE SCRIPT FAZ
---------------------
Seleciona as OS/exames divergentes que NÃO passaram pelo Comitê (e, opcionalmente,
os travados em 'comite') e RE-DISPARA a análise do Comitê para cada um, REUSANDO
as funções existentes (``backend.committee.comite.revisar`` +
``backend.persistence.salvar_comite`` + ``backend.committee.comite.aplicar_exclusoes``
+ ``backend.workflow.ordens.atualizar_pos_analise``) — NÃO duplica a lógica do
Comitê. Os insumos do Comitê (infrações detectadas, ``Comparacao``,
``SaidaDeteccao``) são RECONSTRUÍDOS a partir do que já está persistido em
``exam_infractions``, ``exam_divergencias`` e ``exam_eventos`` — não reprocessa o
vídeo nem chama o Motor de Detecção.

  • IDEMPOTENTE: por padrão pula exames que já têm laudo de Comitê
    (``comite_concluido``). Use ``--incluir-comite`` para reprocessar os travados
    em 'comite' (gera um NOVO laudo; o histórico de ``exam_comite_laudos`` é
    append-only).
  • ``--dry-run`` é o PADRÃO (só lista o que faria). ``--apply`` executa de fato.
  • ``--limite N`` controla o tamanho do lote (default 20).
  • EXECUÇÃO EM LOTE CONCORRENTE: os exames selecionados são processados em
    PARALELO num ``ThreadPoolExecutor`` (igual ao worker de análise), porque o
    gargalo é a chamada Vertex/Gemini do Comitê (~10-40s por exame). Concorrência
    via ``VALBOT_COMITE_CONCURRENCY`` (default 4, conservador p/ não estourar a
    quota do Vertex) ou ``--concorrencia N`` (sobrepõe o env). A SELEÇÃO de
    candidatos e a IDEMPOTÊNCIA não mudam — só a EXECUÇÃO virou concorrente.
    Thread-safety: ``backend.core.db`` abre uma conexão autocommit nova por
    chamada (sem conexão global), então cada thread grava na sua própria conexão
    e exames distintos são independentes — ver ``_reprocessar_um_safe``.

⚠️  DEPENDE DA QUOTA DO VERTEX. Este script só tem EFEITO REAL de reanálise quando
a quota do Vertex AI/Gemini estiver disponível. Sob 429/403 o ``revisar`` cai no
laudo DETERMINÍSTICO (sem IA) — o que ainda assim DESTRAVA o estado (cria a linha
em ``exam_comite_laudos`` e move a OS para ``aguardando_auditor``), mas a
fundamentação rica do Comitê só vem com o Gemini respondendo. O destravamento da
quota em si é infra (fora deste código). Rode este script DEPOIS que a quota
voltar para obter os laudos completos; rode com ``VALBOT_COMITE=0`` se quiser
apenas o destravamento determinístico imediato.

USO
---
    # 1) prévia (não escreve nada) — quantos e quais exames seriam reprocessados:
    python -m tooling.reprocessar_comite

    # 2) executa de fato um lote de 20 divergências sem Comitê:
    python -m tooling.reprocessar_comite --apply --limite 20

    # 3) inclui também as OS travadas no estágio 'comite' (gera novo laudo):
    python -m tooling.reprocessar_comite --apply --limite 20 --incluir-comite

    # 4) FORÇA re-rodar TODOS os divergentes (mesmo os que já têm laudo) — usado
    #    para reprocessar os 148 com o prompt novo (veredito A/R do Comitê),
    #    em LOTE concorrente de 8 chamadas Vertex simultâneas:
    python -m tooling.reprocessar_comite --apply --limite 200 --reprocessar-todos \
        --concorrencia 8
    #    (ou: VALBOT_COMITE_CONCURRENCY=8 python -m tooling.reprocessar_comite ...)

Requer ``DATABASE_URL`` apontando para o Postgres do Valbot (ver memória do
projeto: container ``valbot-postgres`` na VM ``valbot-prod``). Sem DB, sai no-op.
"""

from __future__ import annotations

import argparse
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from backend import persistence
from backend.committee import comite as comite_engine
from backend.core import db
from backend.models import (
    Comparacao,
    Encaminhamento,
    EventoDetectado,
    ResultadoExame,
    SaidaDeteccao,
    TipoDivergencia,
)
from backend.workflow import ordens

log = logging.getLogger("valbot.reprocessar_comite")


# ---------------------------------------------------------------------------
# Seleção dos candidatos (lê da view canônica — fonte única do estágio)
# ---------------------------------------------------------------------------


def _selecionar(limite: int, incluir_comite: bool, forcar_todos: bool = False) -> list[dict]:
    """Exames divergentes que precisam de (re)disparo do Comitê.

    Por padrão: ``divergente AND NOT comite_concluido`` — as divergências que
    foram para 'auditoria' sem passar pelo Comitê. Com ``incluir_comite``,
    também os travados em ``stage = 'comite'`` (já têm laudo; reprocessa).

    Com ``forcar_todos`` (flag ``--reprocessar-todos``/``--forcar``): RE-processa
    TODOS os divergentes, INCLUSIVE os que JÁ têm laudo de Comitê — necessário
    para re-rodar os exames com um PROMPT NOVO (ex.: o veredito A/R do Comitê).
    Gera um NOVO laudo por exame (``exam_comite_laudos`` é append-only).

    Mais antigos primeiro (created_at ASC) — a fila mais velha é a mais urgente.
    """
    if forcar_todos:
        where = "divergente"
    elif incluir_comite:
        where = "divergente AND (NOT comite_concluido OR stage = 'comite')"
    else:
        where = "divergente AND NOT comite_concluido"
    return db.fetch_all(
        f"""
        SELECT id::text AS id, hash, external_id, candidato_nome, categoria,
               stage, divergente, comite_concluido,
               resultado_oficial, resultado_calculado, aprovado, pontuacao_total
          FROM v_exams_overview
         WHERE {where}
         ORDER BY created_at ASC
         LIMIT %s
        """,
        (int(limite),),
    )


# ---------------------------------------------------------------------------
# Reconstrução dos insumos do Comitê a partir do que já está persistido
# ---------------------------------------------------------------------------


def _infracoes_detectadas(exam_id: str) -> list[dict]:
    """Infrações detectadas (1ª análise) no formato que ``comite.revisar`` espera:
    chaves ``id``/``timestamp_s``/``evidence``/``descricao`` (ver _build_prompt_*).

    Só as ativas — descarta as já excluídas por um Comitê anterior.
    """
    linhas = db.fetch_all(
        """
        SELECT regra_id, gravidade, pontos, descricao, timestamp_s, evidence, base_legal
          FROM exam_infractions
         WHERE exam_id = %s
           AND (status IS NULL OR status NOT IN ('excluida_comite', 'descartada'))
         ORDER BY COALESCE(timestamp_s, 0) ASC
        """,
        (exam_id,),
    )
    return [
        {
            "id": r["regra_id"],
            "codigo": r["regra_id"],
            "timestamp_s": float(r["timestamp_s"]) if r.get("timestamp_s") is not None else None,
            "evidence": r.get("evidence") or r.get("descricao") or "",
            "descricao": r.get("descricao") or "",
            "gravidade": r.get("gravidade"),
            "pontos": r.get("pontos"),
            "base_legal": r.get("base_legal"),
        }
        for r in linhas
    ]


def _comparacao(exam_id: str, candidato: dict) -> Comparacao:
    """Reconstrói a ``Comparacao`` persistida (``exam_divergencias``).

    Fallback (linha ausente): deriva da própria view — divergência de resultado
    com encaminhamento ao Comitê (é o caso por construção: só selecionamos
    ``divergente``).
    """
    row = db.fetch_one(
        """
        SELECT tipo_divergencia, resultado_oficial, resultado_calculado,
               pontuacao_oficial, pontuacao_calculada, concorda_resultado,
               concorda_pontuacao, concorda_infracoes, evidencia_suficiente,
               encaminhamento, detalhes
          FROM exam_divergencias WHERE exam_id = %s
        """,
        (exam_id,),
    )

    def _res(v: str | None) -> ResultadoExame | None:
        if not v:
            return None
        try:
            return ResultadoExame(v)
        except ValueError:
            return None

    if row:
        return Comparacao(
            exame_id=exam_id,
            resultado_oficial=_res(row.get("resultado_oficial")),
            resultado_calculado=_res(row.get("resultado_calculado")) or ResultadoExame.NAO_AVALIADO,
            pontuacao_oficial=row.get("pontuacao_oficial"),
            pontuacao_calculada=row.get("pontuacao_calculada"),
            tipo_divergencia=TipoDivergencia(row.get("tipo_divergencia") or "1_resultado"),
            concorda_resultado=bool(row.get("concorda_resultado")),
            concorda_pontuacao=bool(row.get("concorda_pontuacao")),
            concorda_infracoes=bool(row.get("concorda_infracoes")),
            evidencia_suficiente=bool(row.get("evidencia_suficiente", True)),
            detalhes=row.get("detalhes") or {},
            encaminhamento=Encaminhamento.COMITE_DE_IA,
        )

    # Fallback: monta a partir da view (sempre é divergência -> comitê).
    of = "A" if candidato.get("resultado_oficial") == "A" else "R"
    return Comparacao(
        exame_id=exam_id,
        resultado_oficial=_res(of),
        resultado_calculado=ResultadoExame.REPROVADO
        if candidato.get("aprovado") is False
        else ResultadoExame.APROVADO,
        pontuacao_calculada=candidato.get("pontuacao_total"),
        tipo_divergencia=TipoDivergencia.RESULTADO,
        evidencia_suficiente=True,
        detalhes={"origem": "reconstruido_da_view"},
        encaminhamento=Encaminhamento.COMITE_DE_IA,
    )


def _deteccao(exam_id: str) -> SaidaDeteccao:
    """Reconstrói uma ``SaidaDeteccao`` mínima — só o necessário ao Comitê:
    os comentários do examinador (para o laudo determinístico) e a flag de
    evidência suficiente. Eventos de detecção completos não são reidratados:
    ``comite.revisar`` raciocina sobre ``infracoes_detectadas`` + Matriz, não
    sobre ``deteccao.eventos_detectados`` (só usa ``deteccao`` no fallback)."""
    coment = db.fetch_all(
        """
        SELECT evento_id, descricao, timestamp_audio_seg, transcricao, classificacao
          FROM exam_eventos
         WHERE exam_id = %s AND classificacao IS NOT NULL
         ORDER BY COALESCE(timestamp_audio_seg, 0) ASC
        """,
        (exam_id,),
    )
    comentarios = [
        EventoDetectado(
            evento_id=c.get("evento_id") or "examinador",
            categoria="examinador",
            descricao=c.get("descricao") or "",
            timestamp_audio_seg=float(c["timestamp_audio_seg"])
            if c.get("timestamp_audio_seg") is not None
            else None,
            canal_evidencia="audio",
            transcricao=c.get("transcricao"),
            classificacao=c.get("classificacao"),
        )
        for c in coment
    ]
    return SaidaDeteccao(
        exame_id=exam_id,
        modelo_versao="reprocessamento",
        comentarios_examinador=comentarios,
        evidencia_suficiente=True,
    )


# ---------------------------------------------------------------------------
# Reprocessamento de um exame (idempotente)
# ---------------------------------------------------------------------------


def _reprocessar_um(exame: dict, *, apply: bool) -> dict:
    """(Re)dispara o Comitê para UM exame. Devolve um resumo do que (faria/fez).

    Fluxo (todo reusando funções existentes):
      1. reconstrói infracoes_detectadas + Comparacao + SaidaDeteccao;
      2. comite.revisar(...) -> LaudoComite (Gemini se houver quota, senão determinístico);
      3. persistence.salvar_comite(...) -> cria a linha em exam_comite_laudos
         (faz comite_concluido virar TRUE -> exame sai de 'auditoria');
      4. comite.aplicar_exclusoes(...) -> remove infrações 'nao_sustenta' e recalcula;
      5. ordens.atualizar_pos_analise(...) -> reflete na OS (aguardando_auditor / encerra).
    """
    exam_id = exame["id"]
    hash_ = exame["hash"]
    infracoes = _infracoes_detectadas(exam_id)
    comp = _comparacao(exam_id, exame)
    det = _deteccao(exam_id)

    resumo = {
        "exam_id": exam_id,
        "hash": hash_,
        "candidato": exame.get("candidato_nome"),
        "stage_antes": exame.get("stage"),
        "tipo_divergencia": comp.tipo_divergencia.value,
        "n_infracoes": len(infracoes),
    }

    if not apply:
        resumo["acao"] = "DRY_RUN (nada gravado)"
        return resumo

    # 2) (re)disparo do Comitê — reusa a engine existente.
    laudo = comite_engine.revisar(
        None,
        exame_id=exam_id,
        infracoes_detectadas=infracoes,
        comparacao=comp,
        deteccao=det,
    )
    determ = "+deterministico" in (laudo.comite_versao or "")

    # 3) persiste o laudo -> comite_concluido = TRUE (destrava 'auditoria').
    persistence.salvar_comite(hash_, laudo)

    # 4) aplica veredictos (exclui 'nao_sustenta' e recalcula pontuação).
    exclusoes = comite_engine.aplicar_exclusoes(exam_id, infracoes, laudo)

    # 5) reflete na OS (mantém o invariante 1 vídeo = 1 OS consistente).
    os_id = ordens.atualizar_pos_analise(hash_, comp)

    resumo.update(
        {
            "acao": "REPROCESSADO",
            "comite_versao": laudo.comite_versao,
            "modo": "deterministico (sem quota/IA)" if determ else "gemini",
            "conclusao_comite": laudo.conclusao_comite,
            "causas": len(laudo.causas_identificadas),
            "exclusoes": exclusoes.get("excluidas", 0),
            "os_id": os_id,
        }
    )
    return resumo


def _reprocessar_um_safe(exame: dict, *, apply: bool) -> dict:
    """Wrapper que NUNCA lança — espelha ``_process_one_claimed`` do worker de
    análise (tooling/api_stub/server.py): captura qualquer exceção e devolve um
    resumo com ``acao='ERRO'`` para que um exame ruim não derrube o
    ThreadPoolExecutor do lote.

    THREAD-SAFETY: a chamada inteira (Comitê Vertex + gravações no banco) roda
    concorrente. Isto é seguro porque ``backend.core.db`` abre uma conexão
    psycopg autocommit NOVA por chamada (sem conexão global compartilhada, sem
    transação cruzando exames) — cada thread, ao chamar ``db.execute``/
    ``fetch_*`` via persistence/committee/ordens, usa a sua própria conexão de
    vida curta. As escritas de exames distintos são independentes (cada exame
    tem o seu ``exam_id``/``hash``), então paralelizar ponta-a-ponta preserva
    exatamente a semântica do loop sequencial. O único recurso realmente
    contendido é a quota do Vertex, limitada pelo nº de workers (concorrência)."""
    try:
        return _reprocessar_um(exame, apply=apply)
    except Exception as e:  # noqa: BLE001 — um exame ruim não derruba o lote
        log.exception("falha ao reprocessar exam_id=%s", exame.get("id"))
        return {
            "exam_id": exame.get("id"),
            "hash": exame.get("hash"),
            "candidato": exame.get("candidato_nome"),
            "stage_antes": exame.get("stage"),
            "tipo_divergencia": "?",
            "n_infracoes": 0,
            "acao": "ERRO",
            "erro": str(e),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reprocessar_comite",
        description=(
            "Reenvia ao Comitê de IA as divergências que não passaram por ele "
            "(stage=auditoria, comite_concluido=0) e/ou as travadas em 'comite'. "
            "Idempotente; dry-run por padrão. Só tem efeito de reanálise rica com "
            "a quota do Vertex disponível."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="executa de fato (sem isto, é dry-run: só lista o que faria).",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=20,
        help="tamanho do lote (default 20). Mais antigos primeiro.",
    )
    parser.add_argument(
        "--incluir-comite",
        action="store_true",
        help=(
            "também reprocessa os exames travados em stage='comite' (que já têm "
            "laudo) — gera um NOVO laudo. Sem isto, só os divergentes sem Comitê."
        ),
    )
    parser.add_argument(
        "--reprocessar-todos",
        "--forcar",
        dest="forcar_todos",
        action="store_true",
        help=(
            "FORÇA o reprocessamento de TODOS os exames divergentes, inclusive os "
            "que JÁ têm laudo de Comitê (ignora 'comite_concluido') — necessário "
            "para re-rodar os 148 com o prompt NOVO (veredito A/R). Gera um novo "
            "laudo por exame. Default: NÃO forçar (só pendentes)."
        ),
    )
    parser.add_argument(
        "--concorrencia",
        type=int,
        default=None,
        help=(
            "nº de exames processados em PARALELO (ThreadPoolExecutor). Sobrepõe "
            "o env VALBOT_COMITE_CONCURRENCY (default 4 — conservador p/ não "
            "estourar a quota do Vertex). Cada exame faz 1 chamada Vertex/Gemini "
            "(~10-40s), então a concorrência acelera muito o lote."
        ),
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="loga cada exame em detalhe.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if not db.db_enabled():
        print(
            "[reprocessar_comite] DB desabilitado/indisponível "
            "(defina DATABASE_URL e não use VALBOT_DB_DISABLED). Nada a fazer.",
            flush=True,
        )
        return 2

    candidatos = _selecionar(args.limite, args.incluir_comite, args.forcar_todos)
    modo = "APPLY" if args.apply else "DRY-RUN"
    print(
        f"[reprocessar_comite] modo={modo} limite={args.limite} "
        f"incluir_comite={args.incluir_comite} forcar_todos={args.forcar_todos} "
        f"-> {len(candidatos)} exame(s).",
        flush=True,
    )
    if not candidatos:
        print("[reprocessar_comite] nada a reprocessar.", flush=True)
        return 0

    if not args.apply:
        print(
            "[reprocessar_comite] DRY-RUN: nada será gravado. "
            "Reexecute com --apply para reprocessar.",
            flush=True,
        )

    # Concorrência: --concorrencia (CLI) sobrepõe VALBOT_COMITE_CONCURRENCY (env),
    # default 4 (conservador p/ não estourar a quota do Vertex). Espelha o knob
    # VALBOT_BATCH_CONCURRENCY do worker de análise.
    if args.concorrencia is not None:
        concurrency = max(1, args.concorrencia)
    else:
        concurrency = max(1, int(os.environ.get("VALBOT_COMITE_CONCURRENCY", "4") or "4"))
    # Não adianta abrir mais threads que exames no lote.
    concurrency = min(concurrency, len(candidatos))
    print(
        f"[reprocessar_comite] EXECUÇÃO EM LOTE CONCORRENTE: "
        f"{len(candidatos)} submetido(s), concorrência={concurrency} "
        f"(VALBOT_COMITE_CONCURRENCY / --concorrencia).",
        flush=True,
    )

    reprocessados = 0
    determ = 0
    erros = 0
    pulados = 0
    total = len(candidatos)
    # Serializa apenas a impressão/contagem; o processamento (Vertex + writes) é
    # paralelo. As escritas no banco são thread-safe por construção (conexão
    # autocommit nova por chamada em backend.core.db) — ver _reprocessar_um_safe.
    lock = threading.Lock()
    contador = {"i": 0}

    def _trabalho(exame: dict) -> dict:
        nonlocal reprocessados, determ, erros, pulados
        r = _reprocessar_um_safe(exame, apply=args.apply)
        with lock:
            contador["i"] += 1
            i = contador["i"]
            acao = r.get("acao")
            if args.apply and acao == "REPROCESSADO":
                reprocessados += 1
                if "deterministico" in (r.get("modo") or ""):
                    determ += 1
            elif acao == "ERRO":
                erros += 1
            elif acao not in ("REPROCESSADO", "DRY_RUN (nada gravado)"):
                pulados += 1
            exam_id = r.get("exam_id") or "????????"
            linha = (
                f"  [{i}/{total}] {acao} "
                f"exam={str(exam_id)[:8]} stage={r.get('stage_antes')} "
                f"div={r.get('tipo_divergencia')} infr={r.get('n_infracoes')}"
            )
            if acao == "REPROCESSADO":
                linha += (
                    f" modo={r.get('modo')} concl={r.get('conclusao_comite')} "
                    f"excl={r.get('exclusoes')}"
                )
            elif acao == "ERRO":
                linha += f" ERRO: {r.get('erro')}"
            print(linha, flush=True)
            if args.verbose:
                tag = "OK" if acao in ("REPROCESSADO", "DRY_RUN (nada gravado)") else acao
                log.info("exam=%s %s", str(exam_id)[:12], tag)
        return r

    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="comite-batch") as ex:
        futures = [ex.submit(_trabalho, exame) for exame in candidatos]
        for fut in futures:
            # _trabalho/_reprocessar_um_safe nunca lançam; result() só sincroniza.
            fut.result()

    print(
        f"[reprocessar_comite] LOTE: {total} submetido(s), "
        f"{reprocessados} ok, {erros} erro(s)"
        + (f", {pulados} pulado(s)" if pulados else "")
        + ".",
        flush=True,
    )

    if args.apply:
        print(
            f"[reprocessar_comite] FIM: {reprocessados} reprocessado(s) "
            f"({determ} em modo determinístico — sem quota/IA).",
            flush=True,
        )
        if determ:
            print(
                "[reprocessar_comite] ⚠️  laudos determinísticos foram gerados: "
                "DESTRAVAM o estado, mas SEM a fundamentação rica do Gemini. "
                "Reexecute --incluir-comite quando a quota do Vertex voltar.",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
