# VALBOT API — Guia de Integração

Envio de exames práticos DETRAN à plataforma Valbot.

- **Endpoint único:** `POST https://valbot.com.br/api/exams/init-upload`
- **Autenticação:** header `X-API-Key`
- **Suporte:** adm@app1n.com.br

---

## 1. Autenticação

Toda requisição deve incluir o header:

```http
X-API-Key: vbk_live_<sua_key>
```

A key é fornecida pela equipe Valbot e não expira (revogável a pedido).

| Cenário | HTTP |
|---|---|
| Header ausente | `401 X-API-Key header obrigatório` |
| Key inválida ou revogada | `401 API key inválida, revogada ou sem scope` |
| Key OK | `200` |

---

## 2. Endpoint

### `POST /api/exams/init-upload`

Aceita **dois shapes**: objeto único (legado) ou **array de lote** (recomendado). Resposta em <1s — download da URL pro GCS roda em background.

**Headers:**

| Header | Valor |
|---|---|
| `X-API-Key` | `vbk_live_...` (obrigatório) |
| `Content-Type` | `application/json` (obrigatório) |

### 2.1 Shape em array (lote, recomendado)

```json
[
  {
    "url": "https://storage.example.com/exame-12345.mp4",
    "id": 784562,
    "renach": "SP1234567890",
    "processo": 1234567890
  }
]
```

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `url` | string | **sim** | URL HTTPS pública do vídeo (`video/mp4`/`mov`/`m4v`, ≤ 600 MB). |
| `renach` | string | **sim** | RENACH/CNH do candidato. |
| `id` | int | não | ID externo (ex: DETRAN). Persiste em `exams.external_id` (indexado, queryable). |
| `processo` | int \| string | não | Número do processo. |
| `training_annotations` | array | não | Anotações humanas ancoradas em timestamps do vídeo. Cada item: `{"timestamp": "HH:MM:SS", "anotacoes": "<texto>"}`. Default `[]`. |
| `resultado_exame` | string \| null | não | Veredito presencial: `"A"`/`"R"`/`"N"` ou `null`. |

Limites: **máx 50 itens/lote**, **600 MB/vídeo**.

**Resposta `200`:** array na MESMA ORDEM do request.

```json
[
  {
    "external_id": 784562,
    "renach": "SP1234567890",
    "analysis_id": "5d4a28262e0644409509be84666bc330",
    "status": "uploading",
    "gs_path": "gs://valbot-prod/uploads/5d4a.../video.mp4"
  }
]
```

URL inacessível em meio ao lote vira `{external_id, analysis_id:null, status:"error", error:"..."}` — não derruba os outros (partial success).

### 2.2 Shape objeto único (legado)

```json
{
  "url": "https://meu-storage.com/exame-001.mp4",
  "renach": "SP-12345678",
  "candidato_nome": "Joao Silva",
  "categoria": "B"
}
```

Aceita os mesmos campos do shape antigo (`candidato_nome`, `candidato_cpf`, `processo`, `categoria`, `veiculo`, `local`, `examinador`, `auto_escola`, `rubrica`, `training_annotations`, `resultado_exame` — todos opcionais).

`training_annotations` é um array de `{timestamp: "HH:MM:SS", anotacoes: "<texto>"}`. Exemplo:

```json
"training_annotations": [
  {"timestamp": "00:02:35", "anotacoes": "candidato hesitou na baliza"},
  {"timestamp": "00:04:10", "anotacoes": "não olhou retrovisor antes da troca"}
]
```

Itens com `timestamp` fora de `HH:MM:SS` ou `anotacoes` vazio → `422`.

**Resposta `200`:** objeto único.

```json
{
  "analysis_id": "5d4a28262e0644409509be84666bc330",
  "status": "uploading",
  "gs_path": "gs://valbot-prod/uploads/5d4a.../video.mp4"
}
```

### 2.3 Status state machine

`uploading` → `queued` → `running` → `processed` / `processed_no_pdf` / `failed`.

Faça polling em `GET /api/exams/{analysis_id}` (sem auth).

**Erros:**

| HTTP | Quando | Body |
|---|---|---|
| `401` | header `X-API-Key` ausente ou inválido | `{"detail": "X-API-Key header obrigatório"}` |
| `413` | `Content-Length` > 600 MB | `{"detail": "Vídeo muito grande: ..."}` |
| `415` | content-type da URL não é mp4/mov/m4v | `{"detail": "content_type '...' não suportado"}` |
| `422` | body inválido, lote vazio, lote > 50, ou (shape único) URL inacessível | `{"detail": "..."}` |

---

## 3. Exemplo (curl)

**Lote:**

```bash
curl -sX POST https://valbot.com.br/api/exams/init-upload \
  -H "X-API-Key: vbk_live_SUA_KEY_AQUI" \
  -H "Content-Type: application/json" \
  -d '[
    {"url":"https://storage.example.com/exame-12345.mp4","id":784562,"renach":"SP1234567890","processo":1234567890}
  ]' | jq
```

**Objeto único (legado):**

```bash
curl -X POST https://valbot.com.br/api/exams/init-upload \
  -H "X-API-Key: vbk_live_SUA_KEY_AQUI" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://meu-storage.com/exames/exame-001.mp4",
    "renach": "SP-12345678"
  }'
```

---

## 4. Exemplo (Python)

```python
import requests

# Lote
r = requests.post(
    "https://valbot.com.br/api/exams/init-upload",
    headers={"X-API-Key": "vbk_live_SUA_KEY_AQUI", "Content-Type": "application/json"},
    json=[
        {"url": "https://storage.example.com/exame-12345.mp4", "id": 784562, "renach": "SP1234567890", "processo": 1234567890},
    ],
)
r.raise_for_status()
for item in r.json():
    print(item)
# {"external_id": 784562, "renach": "SP1234567890", "analysis_id": "...", "status": "uploading", "gs_path": "gs://..."}
```

---

## 5. Exemplo (Node.js)

```javascript
const r = await fetch("https://valbot.com.br/api/exams/init-upload", {
  method: "POST",
  headers: { "X-API-Key": "vbk_live_SUA_KEY_AQUI", "Content-Type": "application/json" },
  body: JSON.stringify([
    { url: "https://storage.example.com/exame-12345.mp4", id: 784562, renach: "SP1234567890", processo: 1234567890 },
  ]),
});
const items = await r.json();
console.table(items);
```

---

## 6. Boas práticas

- **URL pública:** servidor faz `HEAD` (~1s) síncrono + `GET` (background) na URL. Garanta acesso público; se usar signed URL, TTL ≥ 30 min — download em background pode demorar.
- **HTTPS:** preferir sempre.
- **Tamanho:** máximo 600 MB por vídeo. Acima disso, comprima ou corte antes de enviar.
- **Tempo de resposta:** **<1s** mesmo com vídeo grande — download roda em background. Polling via `GET /api/exams/{analysis_id}`.
- **Retry:** itens com `status:"error"` ou `status:"failed"` no polling — re-envie só o item ruim. Em `422`/`413`/`415`, corrija o input antes.
- **Rate limit:** até 50 itens/lote. Evite > 5 lotes/segundo.
- **Revogação de key:** se a key vazar, avise adm@app1n.com.br — revogamos e geramos nova.

---

## 7. O que acontece depois?

1. Backend Valbot copia o vídeo da URL → GCS.
2. Pipeline analisa com VLM (Vertex AI Gemini) aplicando rubrica `1020/2025`.
3. Laudo gerado (JSON + PDF) fica disponível na interface interna do Valbot.
4. RENACH é o identificador de busca — mesmo candidato pode ter múltiplos exames.

O agente externo **não consulta status** nem **baixa resultado** via API — esses fluxos são internos. Para saber se o exame foi processado, consulte a equipe Valbot.

---

## 8. URL de referência

```
POST https://valbot.com.br/api/exams/init-upload
```

Ambiente único (produção). Sem staging exposto publicamente.
