# `POST /api/exams/init-upload`

Registra um vídeo de exame prático DETRAN (Res. CONTRAN 1.020/2025) para análise pela VALBOT. Aceita dois shapes no mesmo endpoint: **objeto único** (legado, usado pelo frontend) ou **array de itens** (lote, até 50 — usado por integradores externos como DETRAN/autoescolas).

- **Base URL (prod):** `https://valbot.com.br`
- **Autenticação:** header `X-API-Key` (obrigatório, scope `exams:create`)
- **Content-Type:** `application/json`
- **Operação:** `init_upload_api_exams_init_upload_post`
- **Versão da API:** 3.0.0

---

## Visão geral do fluxo

```
┌────────┐   POST /api/exams/init-upload                     ┌──────────┐
│ Cliente│ ─────────────────────────────────────────────────▶│  VALBOT  │
│        │  { url, renach, ... }  ou  [{...}, {...}]         │ (FastAPI)│
│        │ ◀── { analysis_id, status: uploading, gs_path }   │          │
│        │  ou  [{ external_id, analysis_id, status, ... }]  │          │
└────────┘                                                   └────┬─────┘
                                                                  │
                            ┌─────────────────────────────────────┤
                            ▼                                     ▼
                       Postgres                            background worker
                       (tabela exams,                      (até 3 simultâneos)
                        status=uploading)                  GET na URL → GCS
                                                          gs://valbot-prod/uploads/...
                                                                  │
                                                                  ▼
                                                          pipeline de análise
                                                          (VLM, laudo, etc.)
```

**Importante — o backend baixa o vídeo.** Diferente de versões anteriores desta doc, este endpoint **faz download da URL pro GCS em background** (até 3 jobs simultâneos). A resposta volta em <1s mesmo com vídeos grandes, com `status=uploading` enquanto o download não terminou. Use `GET /api/exams/{analysis_id}` pra polling. Status segue `uploading → queued → running → processed`/`failed`.

---

## Quando usar cada shape

| Cenário | Shape | Schema |
|---|---|---|
| Frontend VALBOT (`UploadVideoModal.tsx`) | Objeto único | `InitUploadRequest` (13 campos) |
| Integrador externo que manda um exame por vez | Objeto único | `InitUploadRequest` (13 campos) |
| Integrador DETRAN/autoescola mandando vários exames em uma só requisição | Array | `[InitUploadItem]` (6 campos por item, até 50 itens) |

Os dois shapes convivem permanentemente — não há plano de deprecar o objeto único.

---

## Request

### Headers

| Nome           | Tipo   | Obrigatório | Descrição                                                       |
|----------------|--------|-------------|-----------------------------------------------------------------|
| `X-API-Key`    | string | **sim**     | Chave de API com scope `exams:create` (emitida pelo admin).     |
| `Content-Type` | string | sim         | Sempre `application/json`.                                      |

> **Sem header:** `401 {"detail": "X-API-Key header obrigatório"}`
> **Key inválida/revogada/sem scope:** `401 {"detail": "API key inválida, revogada ou sem scope"}`

### Body — shape objeto único (`InitUploadRequest`)

Só `url` e `renach` são obrigatórios. Os outros 11 campos são metadados que enriquecem o laudo gerado pela VALBOT — quanto mais preenchidos, melhor o relatório.

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `url` | string | — | URL HTTPS do vídeo. Backend faz GET e copia pro GCS. Veja **Validação da URL** abaixo. |
| `renach` | string (≥1 char) | — | RENACH/CNH do candidato. |
| `candidato_nome` | string | `""` | Nome completo do candidato. |
| `candidato_cpf` | string | `""` | CPF do candidato (qualquer formato; backend não normaliza). |
| `processo` | string | `""` | Número do processo administrativo do exame. |
| `categoria` | string | `""` | Categoria da CNH em exame (A, B, C, D, E ou combinações). |
| `veiculo` | string | `""` | Identificação do veículo usado no exame (modelo + placa). |
| `local` | string | `""` | Local físico do exame (CFC, pátio, endereço). |
| `examinador` | string | `""` | Nome e matrícula do examinador presencial. |
| `auto_escola` | string | `""` | Razão social ou nome fantasia da auto-escola. |
| `rubrica` | string | `"1020/2025"` | Resolução CONTRAN aplicada. |
| `training_annotations` | array de `TrainingAnnotation` | `[]` | Anotações humanas timestampadas. Ver seção **Infrações** abaixo. |
| `resultado_exame` | string ou null | `null` | Veredito presencial: `A` (Aprovado), `R` (Reprovado), `N` (Não Avaliado) ou null. |

### Body — shape de lote (`[InitUploadItem]`)

Array de 1 a 50 itens. Cada item tem o subset mais usado pelos integradores externos (DETRAN, autoescolas).

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `url` | string | **sim** | URL HTTPS do vídeo. |
| `renach` | string (≥1 char) | **sim** | RENACH/CNH do candidato. |
| `id` | integer ou null | não | ID externo (ex.: 784562 do DETRAN). Persiste em `exams.external_id` e é ecoado na resposta como `external_id`. |
| `processo` | integer / string / null | não | Número do processo (aceita os dois tipos). |
| `training_annotations` | array de `TrainingAnnotation` | não | Mesma semântica do shape objeto único. Ver seção **Infrações**. |
| `resultado_exame` | `A` / `R` / `N` / null | não | Veredito presencial. |

> Os metadados `candidato_*`, `veiculo`, `local`, `examinador`, `auto_escola`, `rubrica` **não** existem no shape de lote (iteração 2 do schema). Se precisar enviar, use shape objeto único, um item por requisição.

### `TrainingAnnotation`

| Campo | Tipo | Validação | Exemplo |
|---|---|---|---|
| `timestamp` | string | regex `^([0-9]{1,2}):[0-5][0-9]:[0-5][0-9]$` (formato `HH:MM:SS`) | `"00:02:35"` |
| `anotacoes` | string | `minLength: 1` | `"Infração GRAVE — não sinalizou ao trocar de faixa (Res. CONTRAN 1.020/2025, Anexo II, item 2.1)"` |

### Infrações — convenção de prefixo em `training_annotations`

O campo `training_annotations` é nominalmente "anotações de treino", mas **integradores DETRAN reaproveitam pra registrar as infrações decididas pelo examinador presencial**. Não há schema estruturado pra infrações no momento — toda a informação vai em `anotacoes` (texto livre).

**Convenção do prefixo:**

```
Infração <GRAVIDADE> — <descrição> (<ref CONTRAN>)
```

- **Gravidades canônicas:** `LEVE`, `MÉDIA`, `GRAVE`, `GRAVÍSSIMA` (em maiúsculas, sem variação).
- **Descrição:** texto livre, curto.
- **Ref CONTRAN:** opcional mas recomendado. Formato sugerido: `Res. CONTRAN 1.020/2025, Anexo II, item X.Y`.

Exemplos válidos:

```json
{"timestamp": "00:02:35", "anotacoes": "Infração GRAVE — não fez sinalização ao trocar de faixa (Res. CONTRAN 1.020/2025, Anexo II, item 2.1)"}
{"timestamp": "00:04:10", "anotacoes": "Infração MÉDIA — não olhou retrovisor antes da troca de faixa"}
{"timestamp": "00:06:42", "anotacoes": "Infração GRAVÍSSIMA — frenagem brusca, quase atropelou pedestre na faixa"}
{"timestamp": "00:08:55", "anotacoes": "Infração LEVE — ajuste do banco/retrovisores incompleto antes de iniciar"}
```

Anotações de treino "puras" (sem prefixo `Infração`) continuam válidas — a convenção é aditiva, não bloqueante. A skill `avaliador-detran` faz parsing do prefixo quando presente.

### Validação da URL

Por motivos de segurança e robustez, a URL passa por **duas validações** antes do registro ser aceito:

#### 1. Anti-SSRF (estrutural)

Rejeita com `422` (formato `HTTPValidationError`):

| Caso | Exemplo | Razão |
|---|---|---|
| Scheme não-HTTP | `javascript:alert(1)`, `file:///etc/passwd`, `gopher://x`, `ftp://x` | Apenas `http://` e `https://` são aceitos. |
| Loopback / localhost | `http://localhost/x`, `http://127.0.0.1/x` | Bloqueio anti-SSRF. |
| Metadata cloud | `http://169.254.169.254/...`, `http://metadata.google.internal/` | Bloqueio anti-SSRF (proibido acesso a credenciais de instância). |
| IP privado | `http://10.0.0.1/x`, `http://192.168.x.x`, `http://172.16.x.x` | Bloqueio anti-SSRF (RFC 1918). |
| Link-local / reservado / multicast | `http://169.254.x.x/`, etc. | Bloqueio anti-SSRF. |
| URL sem host | `http:///path` | Inválida. |
| URL com mais de 2048 chars | (...) | Limite duro de tamanho. |

#### 2. Acessibilidade (HEAD/GET)

Depois de passar pelo filtro anti-SSRF, o backend faz uma requisição HEAD/GET pra verificar que a URL responde. Rejeita com `422` (formato `ErrorResponse` simples) se:

- DNS não resolve → `{"detail": "URL inacessível: [Errno -2] Name or service not known"}`
- HTTP retorna 4xx/5xx → `{"detail": "URL inacessível: Client error '403 Forbidden' for url '...'"}`
- Conexão timeout/recusada → `{"detail": "URL inacessível: ..."}`

**Implicação:** URLs de exemplo tipo `https://storage.example.com/...` (que não existem) são rejeitadas. Pra testes use um host real e público (ex.: `https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4`).

### Exemplos de payload

#### Objeto único — payload mínimo

```json
{
  "url": "https://storage.example.com/exames/EX-12345.mp4",
  "renach": "SP1234567890"
}
```

#### Objeto único — payload completo (13 campos)

```json
{
  "url": "https://storage.example.com/exames/EX-12345.mp4",
  "renach": "SP1234567890",
  "candidato_nome": "João da Silva",
  "candidato_cpf": "123.456.789-00",
  "processo": "2026000123456",
  "categoria": "B",
  "veiculo": "VW Gol 1.0 ABC1D23",
  "local": "CFC Mock — Pátio 3, São Paulo/SP",
  "examinador": "Maria Examinadora (matr. 9876)",
  "auto_escola": "Auto Escola Teste Ltda",
  "rubrica": "1020/2025",
  "training_annotations": [
    {"timestamp": "00:02:35", "anotacoes": "Infração GRAVE — não sinalizou ao trocar de faixa (Res. CONTRAN 1.020/2025, Anexo II, item 2.1)"},
    {"timestamp": "00:06:42", "anotacoes": "Infração GRAVÍSSIMA — quase atropelou pedestre na faixa"}
  ],
  "resultado_exame": "R"
}
```

#### Lote — payload típico de integrador DETRAN

```json
[
  {
    "url": "https://storage.example.com/exames/EX-12345.mp4",
    "id": 784562,
    "renach": "SP1234567890",
    "processo": 1234567890,
    "resultado_exame": "R",
    "training_annotations": [
      {"timestamp": "00:02:35", "anotacoes": "Infração GRAVE — não sinalizou ao trocar de faixa"},
      {"timestamp": "00:06:42", "anotacoes": "Infração GRAVÍSSIMA — frenagem brusca em pedestre"}
    ]
  },
  {
    "url": "https://storage.example.com/exames/EX-12346.mp4",
    "id": 784563,
    "renach": "SP9876543210",
    "processo": 1234567891,
    "resultado_exame": "A"
  }
]
```

---

## Response

A forma da resposta segue a forma do request: objeto único devolve `InitUploadResponse`; array devolve `BatchInitUploadResponse` (lista na mesma ordem).

### `200 OK` — objeto único (`InitUploadResponse`)

```json
{
  "analysis_id": "9b1b8b748ee14bef9acc0a04e98be4df",
  "status": "uploading",
  "gs_path": "gs://valbot-prod/uploads/9b1b8b748ee14bef9acc0a04e98be4df/video.mp4"
}
```

| Campo         | Tipo   | Descrição                                                                  |
|---------------|--------|----------------------------------------------------------------------------|
| `analysis_id` | string | Identificador hex (32 chars). Chave pra `GET /api/exams/{analysis_id}`.    |
| `status`      | string | Sempre `"uploading"` na resposta inicial. Transições: `uploading → queued → running → processed`/`failed`. |
| `gs_path`     | string | Caminho GCS onde o vídeo será depositado: `gs://<bucket>/uploads/<analysis_id>/video.mp4`. |

### `200 OK` — lote (`BatchInitUploadResponse`)

```json
[
  {
    "external_id": 784562,
    "renach": "SP1234567890",
    "analysis_id": "cc34e800f43c43068bdfa14f2ddb5a3f",
    "status": "uploading",
    "gs_path": "gs://valbot-prod/uploads/cc34e800f43c43068bdfa14f2ddb5a3f/video.mp4"
  },
  {
    "external_id": 784563,
    "renach": "SP9876543210",
    "error": "URL inacessível: Client error '404 Not Found' for url '...'"
  }
]
```

Cada item da resposta corresponde ao item de mesma posição no request. Itens com erro de validação trazem `error` no lugar de `analysis_id` + `status` + `gs_path`.

| Campo         | Tipo            | Descrição                                                  |
|---------------|-----------------|------------------------------------------------------------|
| `external_id` | integer ou null | Eco do `id` enviado no request.                            |
| `renach`      | string          | Eco do `renach` enviado.                                   |
| `analysis_id` | string          | ID hex (32 chars). Ausente em itens com `error`.           |
| `status`      | string          | `"uploading"` em itens válidos. Ausente em itens com `error`. |
| `gs_path`     | string          | Caminho GCS. Ausente em itens com `error`.                 |
| `error`       | string          | Mensagem de erro. Ausente em itens válidos.                |

### `401 Unauthorized`

```json
{ "detail": "X-API-Key header obrigatório" }
```

ou

```json
{ "detail": "API key inválida, revogada ou sem scope" }
```

### `422 Unprocessable Entity`

Três variações, dependendo de qual validação falhou.

**Schema inválido** (campo faltando, tipo errado — formato `HTTPValidationError`):

```json
{
  "detail": [
    {
      "loc": ["body", "renach"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

**Host bloqueado por anti-SSRF** (mesmo formato):

```json
{
  "detail": [
    {
      "loc": ["body", "url"],
      "msg": "Value error, host privado/loopback/link-local não permitido",
      "type": "value_error",
      "input": "http://10.0.0.1/x"
    }
  ]
}
```

**URL inacessível** (depois do anti-SSRF passar — formato `ErrorResponse` simples):

```json
{ "detail": "URL inacessível: [Errno -2] Name or service not known" }
```

```json
{ "detail": "URL inacessível: Client error '403 Forbidden' for url 'https://...'" }
```

### `429 Too Many Requests`

```json
{ "detail": "rate limit excedido (10 req/60s) — tente em 17s" }
```

Headers de resposta:
- `Retry-After`: segundos até a janela liberar
- `X-RateLimit-Limit`: 10
- `X-RateLimit-Remaining`: 0
- `X-RateLimit-Reset`: unix timestamp da liberação

---

## Exemplos práticos

### cURL — objeto único

```bash
curl -X POST https://valbot.com.br/api/exams/init-upload \
  -H "X-API-Key: $VALBOT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://storage.example.com/exames/EX-12345.mp4",
    "renach": "SP1234567890"
  }'
```

### cURL — lote (integrador DETRAN)

```bash
curl -X POST https://valbot.com.br/api/exams/init-upload \
  -H "X-API-Key: $VALBOT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "url": "https://storage.example.com/exames/EX-12345.mp4",
      "id": 784562,
      "renach": "SP1234567890",
      "processo": 1234567890,
      "resultado_exame": "R",
      "training_annotations": [
        {"timestamp": "00:02:35", "anotacoes": "Infração GRAVE — não sinalizou ao trocar de faixa"}
      ]
    }
  ]'
```

### Python (`requests`)

```python
import os, requests

API = "https://valbot.com.br"
KEY = os.environ["VALBOT_API_KEY"]  # nunca commit


def register_exam(url: str, renach: str, **metadados) -> dict:
    """Shape objeto único — aceita kwargs pros 11 campos opcionais."""
    payload = {"url": url, "renach": renach, **metadados}
    r = requests.post(
        f"{API}/api/exams/init-upload",
        headers={"X-API-Key": KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()  # {analysis_id, status, gs_path}


def register_batch(items: list[dict]) -> list[dict]:
    """Shape de lote — até 50 itens, na mesma ordem do request."""
    r = requests.post(
        f"{API}/api/exams/init-upload",
        headers={"X-API-Key": KEY, "Content-Type": "application/json"},
        json=items,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()  # [{external_id, analysis_id, status, gs_path?, error?}]


# Uso — objeto único com metadados
result = register_exam(
    url="https://storage.example.com/exames/EX-12345.mp4",
    renach="SP1234567890",
    candidato_nome="João da Silva",
    categoria="B",
    resultado_exame="R",
    training_annotations=[
        {"timestamp": "00:02:35", "anotacoes": "Infração GRAVE — não sinalizou ao trocar de faixa"},
    ],
)
print(result["analysis_id"])

# Uso — lote
batch = register_batch([
    {"url": "...", "id": 784562, "renach": "SP1234567890", "processo": 1234567890},
    {"url": "...", "id": 784563, "renach": "SP9876543210", "processo": 1234567891},
])
for item in batch:
    if "error" in item:
        print(f"Falhou id={item.get('external_id')}: {item['error']}")
    else:
        print(f"OK id={item['external_id']} → {item['analysis_id']}")
```

### Node.js (`fetch`)

```js
const API = "https://valbot.com.br";
const KEY = process.env.VALBOT_API_KEY; // nunca commit

async function registerExam(payload) {
  // payload pode ser objeto único {url, renach, ...} ou array [{...}, ...]
  const r = await fetch(`${API}/api/exams/init-upload`, {
    method: "POST",
    headers: {
      "X-API-Key": KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`init-upload falhou: ${r.status} ${await r.text()}`);
  return r.json();
}

// Objeto único
const single = await registerExam({
  url: "https://storage.example.com/exames/EX-12345.mp4",
  renach: "SP1234567890",
  candidato_nome: "João da Silva",
  resultado_exame: "R",
});

// Lote
const batch = await registerExam([
  { url: "...", id: 784562, renach: "SP1234567890", processo: 1234567890 },
  { url: "...", id: 784563, renach: "SP9876543210", processo: 1234567891 },
]);
```

---

## Política de uso e segurança

Este endpoint é o **único** ponto de entrada exposto a clientes externos. Demais endpoints da API exigem `X-Admin-Token` interno e retornam `401` para qualquer chamada sem ele.

### O que sua API key permite

- Escopo emitido: `exams:create`.
- Permite **apenas** este endpoint (`POST /api/exams/init-upload`) e — caso aplicável — confirmação de upload via `POST /api/exams/{analysis_id}/finalize`.
- Tentativas de chamar outros endpoints retornam `401`.

### O que sua API key **não** permite

- Ler exames existentes (`GET /api/exams/...`) — endpoint interno.
- Listar exames de outros clientes.
- Acessar resultados, laudos PDF ou histórico.
- Gerar novas chaves de API (`POST /api/admin/api-keys` exige `X-Admin-Token`).
- Modificar ou apagar registros.

### Boas práticas que esperamos do cliente externo

1. **Não logue a chave.** A `X-API-Key` deve viver em variável de ambiente / cofre, nunca em código-fonte.
2. **Use HTTPS sempre** ao chamar o endpoint. A URL informada também deve usar HTTPS quando contiver dados sensíveis na query string.
3. **Não inclua tokens/segredos na URL hospedada.** Se a URL contiver `?token=...`, esse token pode acabar em logs internos do cliente, do servidor de origem, ou em caches intermediários. Backend baixa o arquivo, então qualquer credencial embutida fica visível na requisição GET.
4. **Garanta que a URL fica acessível pelo tempo do download.** O backend baixa em background — URLs com TTL curto (signed URLs com 5min de expiração) podem expirar antes do download terminar se houver fila. Recomendado: TTL ≥ 1h.
5. **Prefira o shape de lote** quando integrador (DETRAN, autoescola) tiver mais de um exame pra enviar. Reduz round-trips e o rate limit conta uma única requisição.
6. **Trate `429` e backoff.** Rate limit: **10 requisições por minuto por API key** (janela deslizante de 60s; sem API key cai para fallback por IP). Quando excedido, a resposta vem com header `Retry-After` em segundos e status `429`. Use os headers `X-RateLimit-Limit`, `X-RateLimit-Remaining` e `X-RateLimit-Reset` (presentes em todas as respostas do endpoint) pra se planejar. Trocar de IP não burla o limite — a contagem segue a chave.
7. **Polling de status.** Use `GET /api/exams/{analysis_id}` pra acompanhar a transição `uploading → queued → running → processed`/`failed`. Não chame mais que uma vez a cada 10s por análise.

### Comportamento de rede e logging

- A URL informada **é baixada** pelo backend, em job de background no servidor VALBOT. Tráfego sai do IP da VM us-central1.
- Logs do servidor armazenam: `analysis_id`, `renach`, e apenas o `hostname` da URL (não a query string completa).
- Postgres armazena: registro completo na tabela `exams` (campos `renach`, `gs_video` apontando pro `gs_path`, `status`, `created_at`, `external_id` quando enviado).
- O endpoint **não é idempotente** — cada chamada gera `analysis_id` novo, mesmo com `url` + `renach` repetidos. Integradores que precisam de idempotência devem rastrear `external_id` (`id` no request de lote) localmente.

### Solicitação de revogação

Para revogar uma key comprometida, contate o administrador do VALBOT. A revogação é imediata — chamadas subsequentes retornam `401`.

---

## Spec OpenAPI

A spec viva está em `https://valbot.com.br/docs/init-upload.openapi.yaml` e renderiza visualmente em `https://valbot.com.br/docs/init-upload`. Em caso de divergência entre este documento e a spec, **a spec é a fonte da verdade**. Em caso de divergência entre a spec e o OpenAPI publicado pelo serviço (`https://valbot.com.br/api/openapi.json`), o **OpenAPI do serviço é a fonte de verdade última**.
