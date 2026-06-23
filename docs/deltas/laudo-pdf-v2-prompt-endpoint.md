# Delta de integração — Laudo PDF v2.0 (prompt de detecção + endpoint)

> Este PR entrega o **núcleo frio** do laudo PDF de 8 blocos (geração determinística +
> template + testes). Dois pontos de integração ficaram **fora** porque estavam em
> edição ativa por outra sessão no momento (regra da casa: nunca dois agentes no mesmo
> arquivo): o **prompt de detecção** (`src/analysis/openrouter_gemini.py`) e o
> **endpoint** (`tooling/api_stub/server.py`). Abaixo, exatamente o que aplicar nesses
> arquivos quando a outra frente commitar. Tudo aqui é **descritivo** — não altera
> pontuação (constitution §V).

## 1. `src/analysis/openrouter_gemini.py` — campos descritivos no schema de saída

No bloco "FORMATO DE SAÍDA — JSON ESTRITO" de `_build_user_prompt` (hoje ~linha 340),
adicionar por item de `infracoes_avaliadas` (somar às chaves existentes):

```jsonc
"conduta_observada": "Frase factual curta da conduta (ex.: 'Veículo subiu na calçada durante conversão').",
"evidencia_audio": "Transcrição LITERAL do áudio relevante, entre aspas. \"\" se nenhum.",
"excecao_considerada": "<id/ficha da exceção MBEDV avaliada | null>",
"excecao_resultado": "aplicada|descartada|nao_aplicavel"
```

E formalizar o array top-level (hoje já lido por `backend/engines/deteccao.py:80-97`,
mas **ausente** do schema estrito do prompt — risco de o modelo não emitir):

```jsonc
"observacoes_conduta": [
  {
    "ts_seconds": 0,
    "categoria": "comportamento|audio_examinador|trajetoria|conduta_candidato",
    "origem": "visao|audio|trajetoria",
    "classificacao": "adequado|inadequado|neutro",
    "transcricao_audio": "literal, entre aspas, ou \"\"",
    "descricao": "observação factual; NÃO pontua (MBEDV §4-5)"
  }
]
```

Acrescentar à seção de REGRAS DURAS: *"Preencha `evidencia_audio`/`transcricao_audio`
com a fala LITERAL entre aspas; sob o mesmo princípio in dubio, sem inferência."*

**Validação:** a saída deve ser validada contra
`src/analysis/schemas/laudo_deteccao.schema.json` (entregue neste PR). Campos fora do
vocabulário → rejeitar/normalizar antes de entrar no laudo. Propagar os novos campos em
`_normalize` (~848) e `_normalize_v26` (~778).

**Comitê (`backend/committee/comite.py`):** opcionalmente, adicionar por infração um
`recomendacao_tecnica` (enum `CONFIRMAR|REVISAR|DESCARTAR`). Enquanto não vier do comitê,
o laudo já a **deriva deterministicamente** via
`backend.reporting.regras_laudo.recomendacao_tecnica` (confiança ≥0.85 → CONFIRMAR,
senão REVISAR). Não é bloqueante.

## 2. `tooling/api_stub/server.py` — ligar o endpoint ao template rico

Em `get_laudo_pdf_dossie` (`/api/exams/{hash}/laudo-pdf`), trocar o HTML genérico
(`_laudo_pdf_html`) pelo laudo v2:

```python
from backend.reporting.laudo_pdf_view import montar_laudo_pdf_view
from src.reporting.render_laudo_v2 import render_html, render_pdf

dossie = _dossie_de_laudo(hash)          # adapter do dossiê do DB → contrato do dossiê (ver abaixo)
view = montar_laudo_pdf_view(dossie)     # versao_controlada=True só em ambiente restrito da Comissão
# servir storage/analyses/<hash>/laudo.pdf se existir; senão:
pdf_path = render_pdf(view, ANALYSES_DIR / hash / "laudo.pdf")
if pdf_path is None:                      # WeasyPrint ausente → fallback HTML 200
    return HTMLResponse(render_html(view), headers={"X-Laudo-Fallback": "html"})
return FileResponse(pdf_path, media_type="application/pdf", filename=f"laudo-{hash[:12]}.pdf")
```

`_dossie_de_laudo(hash)` mapeia o dossiê do DB (`db.laudo_dossie`, usado hoje em
`_laudo_blocos_14_2`) para o **contrato de entrada** do dossiê — ver o docstring/seções de
`backend/reporting/laudo_pdf_view.montar_laudo_pdf_view` (candidato, examinador, veiculo,
unidade, tempo, resultado_oficial, anotacoes_tpa, resultado_calculado, infracoes,
observacoes_conduta, divergencia). Campos ausentes viram "não informado" (resiliente).

`/api/relatorios/consolidado` deve usar o mesmo `render_html`/`render_pdf` (1 laudo por
página). `_laudo_pdf_html` fica como fallback legado.

**Frontend:** o botão "PDF" em `Relatorios.tsx` já aponta para `/api/exams/{hash}/laudo-pdf`
— passa a abrir o laudo rico automaticamente após este delta, sem mudança no frontend.

## 3. Calibração conhecida — checklist Anexo K

`backend/reporting/checklist_anexo_k.py` é **conservador por design**: itens sem sinal
técnico automático confiável ficam `requer_verificacao_humana` (não conta como aprovado).
No caso real isso dá "4 de 12" (o mockup ilustra "11 de 12"). À medida que sinais reais
forem expostos no dossiê (continuidade de gravação, regulagem/sincronia de câmera, QA de
áudio), mais itens passam a `sim` automaticamente. Nunca se marca `sim` sem evidência —
isso é proposital (defensabilidade).
