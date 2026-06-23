# Fluxo: `POST /api/exams/init-upload`

**Status:** invariante. Mudanças aqui exigem PR com revisão. Sempre que o backend mudar uma regra de validação, **o frontend tem que mudar junto** (e vice-versa). Esta doc é o contrato.

## Diagrama (de ponta a ponta)

```mermaid
sequenceDiagram
  participant I as Integrador (DETRAN / Frontend)
  participant API as Backend FastAPI<br/>tooling/api_stub/server.py
  participant DB as Postgres (exams)
  participant FS as Disco VM<br/>/opt/valbot/storage/analyses/&lt;hash&gt;/
  participant GCS as GCS gs://valbot-prod
  participant SW as Sweep boto3<br/>tooling/process_pending_s3.py

  I->>API: POST /api/exams/init-upload<br/>{url, renach, processo?, id?, training_annotations[], resultado_exame?}
  API->>API: Pydantic valida payload<br/>(INV1, INV2, INV3, INV4)
  API->>API: analysis_id = sha256(url)<br/>(INV5)
  API->>FS: write upload.json
  API->>DB: insert_exam(ON CONFLICT preserva COFRE)<br/>(INV6) — status=uploading
  API-->>I: 202 {analysis_id, hash}
  Note over API,GCS: Background task (httpx anônimo)
  API->>GCS: GET source_url<br/>stream → blob valbot-prod/uploads/&lt;hash&gt;/video.mp4
  alt Download OK
    API->>DB: update_status(queued, gs_video=...)
    API->>API: dispatch _run_analysis
  else 403 / timeout (S3 privado)
    API->>DB: update_status(failed, error=...)
    Note over API,SW: ⚠️ Failed fica esperando o sweep<br/>(sweep só pega status=queued — precisa reset manual!)
  end
  Note over SW: cron / on-demand
  SW->>FS: lista status=queued
  SW->>GCS: boto3 baixa S3 com cred AWS → upload GCS
  SW->>API: _run_analysis(Gemini)
  SW->>DB: update_result(aprovado, gate, categoria, ...)<br/>(INV9)
  SW->>FS: render laudo.pdf<br/>(INV10 — sempre, mesmo gate-rejected)
  SW->>DB: update_status(processed)
```

## Invariantes (regras que backend E frontend devem checar)

Cada invariante tem 1 lugar canônico no backend e 1 lugar correspondente no frontend. Se um lado mudar a regra, o outro **precisa** mudar junto — testar com payload de borda no PR.

| # | Regra | Onde no Backend | Onde no Frontend |
|---|---|---|---|
| **INV1** | `renach` é obrigatório, não-vazio, min_length=1 | `InitUploadRequest.renach` / `InitUploadItem.renach` em server.py (`Field(..., min_length=1)`) | `UploadVideoModal.tsx` — input `required`, bloqueia submit se vazio |
| **INV2** | `url` é obrigatória, formato HTTPS válido | `Field(..., description="URL HTTPS")` em server.py — Pydantic só checa presença, validação de URL formato fica como TODO | `UploadVideoModal.tsx` — input `type="url"` + regex `^https://` |
| **INV3** | `resultado_exame` se presente é `A`/`R`/`N` (uppercase) | `Field(... pattern="^[ARN]$", max_length=1)` em ambos os schemas | `UploadVideoModal.tsx` — `<select>` com apenas 3 opções; nunca text input livre |
| **INV4** | `training_annotations[i].timestamp` formato `HH:MM:SS`. `anotacoes` não-vazio. | Pydantic `TrainingAnnotation` valida — itens inválidos = 422 | Antes de enviar, frontend valida cada item com regex `/^\d{2}:\d{2}:\d{2}$/` e descarta vazios |
| **INV5** | `analysis_id` = `sha256(url).hexdigest()` (32 chars, mesmo em todos os lados) | server.py: helper `_hash_url(url)` (canonical) | Frontend NUNCA calcula o hash — sempre lê o devolvido em `202 {analysis_id}`. Se for usar offline, importar `crypto.subtle.digest` e bater contra o backend |
| **INV6** | INSERT em `exams` é **idempotente via `ON CONFLICT (hash)`**. Re-init com mesma URL não apaga COFRE: `resultado_exame`, `training_annotations`, `candidato.*` preenchidos antes ficam preservados via `COALESCE(NULLIF(EXCLUDED.x, ''), exams.x)`. | `db.insert_exam` em db.py | Frontend pode re-submeter init-upload pra mesma URL sem medo. Mostrar feedback "exame já existia, atualizado" quando 200 vs 202. |
| **INV7** | `_is_real_source_url(url)` é a regra única de "real vs teste". Lista negra de fixtures (`samplelib.com`, `sample-5s.mp4`, `localhost`, `127.0.0.1`); resto = real (inclusive `None` = upload legado). | server.py: `_is_real_source_url` (server-side filter em `/api/videos`) | Frontend NÃO duplica a regra — confia no campo `is_real` que vem no payload do `/api/videos`. Toggle "Incluir testes" apenas alterna o query param `?include_test=true` |
| **INV8** | Status flow estrito: `uploading → queued → running → processed` (sucesso) ou `… → failed` (erro). Transições inválidas = bug. | `_write_status` (status.json) + `db.update_status` (DB) — devem refletir o mesmo valor | Frontend usa o status pra renderizar UI; respeita "processed" como terminal. Não infere status de outros sinais. |
| **INV9** | `update_result` extrai categoria em 3 fontes (cascata): `result.candidato.categoria` → `result.video.layout.categoria` → parse do `upload_meta.video.source_url` no path techpratico. Persiste em `exams.categoria`. | `db.update_result(... upload_meta=...)` em db.py | Frontend NÃO deriva categoria localmente — lê de `v.categoria_cnh` do `/api/videos`. (Existe um fallback `extractCategoriaFromUrl` em FilaOperacional.tsx — gambiarra a remover após validar que o backfill cobre todos os casos) |
| **INV10** | Laudo PDF é gerado **sempre**, inclusive em gate-rejected (`SEM_AVALIACAO`). Operador precisa ver o motivo da rejeição em PDF formatado, não só badge. | `process_pending_s3.py:466` — `_render_pdf` roda independente de `result.aprovado` / `gate_rejected` | Frontend mostra botão "Baixar laudo" quando `v.pdf_url` está presente, sem condição de aprovado/gate |

## Estados terminais e o que olhar primeiro quando algo dá errado

| Estado | Sinal | Diagnóstico de 1ª linha |
|---|---|---|
| `failed` no `uploading` | log do api container, exam_events.action='failed' com details `{from: uploading, to: failed}` | É S3 403 (URL privada, httpx anônimo). Solução: resetar pra `queued` e rodar `process_pending_s3` (boto3 com cred AWS). |
| `failed` no `running` | logs api: erros Gemini (timeout, quota), result.json vazio | Quota Gemini, vídeo muito grande (>1GB), prompt corrupted |
| Status fica `queued` indefinidamente | sweep não está rodando | `process_pending_s3.py` é CLI, não daemon. Verificar cron/systemd timer na VM (atualmente: nenhum — precisa rodar manual) |
| `gate_rejected=true` + `resultado=SEM_AVALIACAO` | normal | Não é erro — o gate identificou que o vídeo não passa no pré-check (categoria errada, fabricante desconhecido, etc). Laudo PDF deve existir (INV10) |
| `categoria` NULL pós-`processed` | bug em `update_result` ou `upload_meta` não passado | Verificar `db.update_result` recebeu `upload_meta`; rodar `tooling.backfill_categoria` |

## Pré-commit checklist (quando mexer no init_upload)

- [ ] Pydantic schema atualizado (`InitUploadRequest` e/ou `InitUploadItem` em server.py)
- [ ] Frontend `UploadVideoModal.tsx` ou componente equivalente atualizado pra refletir o novo schema
- [ ] Teste de fronteira: payload mínimo (só `url` + `renach`), payload completo, payload com campo inválido (esperado 422), payload duplicado (esperado idempotent)
- [ ] Esta doc atualizada se mudou regra
- [ ] Smoke: `curl -X POST /api/exams/init-upload -d '{"url":"...","renach":"SE..."}'` retorna 202

## Referências

- Backend handler: `tooling/api_stub/server.py` (search `init-upload` ou `_build_meta_`)
- Schemas: `InitUploadRequest` (single, legacy/frontend) e `InitUploadItem` (batch, DETRAN)
- Persistência: `tooling/api_stub/db.py` — `insert_exam`, `update_status`, `update_result`
- Pipeline subsequente: `tooling/process_pending_s3.py`
- Frontend submit: `frontend/artifacts/valbot/src/components/UploadVideoModal.tsx`
- Frontend lista: `frontend/artifacts/valbot/src/pages/FilaOperacional.tsx`
