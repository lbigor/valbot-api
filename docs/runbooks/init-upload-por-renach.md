# Runbook — pegar o JSON do `init_upload` de um exame pelo RENACH

Objetivo: dado um **RENACH** (ex.: `SE031656765`), recuperar rápido o **JSON inicial
do `init_upload`** — o payload que o integrador (TechPrático/DETRAN) enviou no
`POST /api/exams/init-upload`.

> ⚠️ **O payload bruto NÃO é persistido.** O backend recebe o body, monta o
> `upload.json` enriquecido (acrescenta `analysis_id`, `gs_path`, `downloaded_at`,
> `engine`, `duration_s`…) e **descarta o original**. Confirmado: não há cópia do
> body em arquivo, nos logs retidos do container, nem no audit `exam_events`.
> Portanto o "JSON inicial" é sempre **reconstruído** a partir do `upload.json`
> (que é um snapshot fiel — carrega 100% dos campos do POST, só reorganizados em
> `candidato`/`exame`/`video`).

Há 3 caminhos, do mais cômodo ao mais direto.

---

## 1. Tela Relatórios (forma normal, sem terminal)

1. Abrir **Relatórios** no app.
2. Filtrar/localizar o exame pela coluna **RENACH**.
3. Abrir o laudo (clique na linha) → o grupo **`init_upload`** aparece no topo do
   detalhe. Botão **JSON** mostra o objeto completo do laudo com o `init_upload`
   embutido como um grupo.

Por baixo, a tela chama o endpoint do caminho 2.

---

## 2. Via API (precisa do `hash`, não do renach direto)

O endpoint é por `hash` (= `sha256(url)`), não por renach:

```bash
# JSON inicial reconstruído (formato InitUploadRequest):
curl -s --cookie "$COOKIE" https://valbot.com.br/api/exams/<HASH>/init-upload | jq
```

Para descobrir o `hash` a partir do renach sem terminal na VM, use a listagem de
resultados (mesma que a tela consome) e filtre pelo renach no `jq`:

```bash
curl -s --cookie "$COOKIE" "https://valbot.com.br/api/relatorios/resultados?dias=365" \
  | jq '.rows[]? | select(.renach=="SE031656765") | {hash, renach}'
```

(`$COOKIE` = cookie de sessão de um login válido; o endpoint exige `require_session`.)

---

## 3. Direto na VM (mais rápido para debug/suporte)

Não há MCP dedicado do Valbot — o banco é um Postgres próprio no container
`valbot-postgres`. O caminho mais rápido é **SSH + `docker exec psql`** para achar o
hash pelo renach, depois ler o `upload.json` no volume.

```bash
# 0. (uma vez) selecionar o projeto certo do gcloud
gcloud config configurations activate valbot

# 1. renach -> hash (pode haver mais de um: re-submissões da mesma URL)
gcloud compute ssh valbot-prod --zone=us-central1-a --command="
  sudo docker exec valbot-postgres psql -U valbot -d valbot -c \
  \"SELECT hash, status, created_at FROM exams WHERE renach='SE031656765' ORDER BY created_at DESC;\""

# 2. hash -> upload.json (snapshot completo, já enriquecido)
HASH=<cole_o_hash>
gcloud compute ssh valbot-prod --zone=us-central1-a --command="
  sudo cat /mnt/data/docker-volumes/valbot-deploy_valbot-storage/_data/analyses/$HASH/upload.json"
```

Paths fixos da VM (`valbot-prod`, zona `us-central1-a`):

| O quê | Onde |
|---|---|
| Storage dos exames | `/mnt/data/docker-volumes/valbot-deploy_valbot-storage/_data/analyses/<hash>/` |
| Snapshot do upload | `…/<hash>/upload.json` |
| Banco | container `valbot-postgres`, db `valbot`, user `valbot` |
| Tabela | `exams` (busca por `renach`, `processo`); auditoria em `exam_events` |

### One-liner: renach → JSON inicial reconstruído

Reconstrói direto o payload original (sem campos do Valbot), na VM:

```bash
RENACH=SE031656765
gcloud compute ssh valbot-prod --zone=us-central1-a --command="
H=\$(sudo docker exec valbot-postgres psql -U valbot -d valbot -tA -c \"SELECT hash FROM exams WHERE renach='$RENACH' ORDER BY created_at DESC LIMIT 1;\");
sudo cat /mnt/data/docker-volumes/valbot-deploy_valbot-storage/_data/analyses/\$H/upload.json \
 | python3 -c 'import json,sys; m=json.load(sys.stdin); c=m.get(\"candidato\",{}); e=m.get(\"exame\",{}); v=m.get(\"video\",{}); print(json.dumps({\"url\":v.get(\"source_url\") or v.get(\"gs_path_original_s3\",\"\"),\"renach\":c.get(\"renach\",\"\"),\"candidato_nome\":c.get(\"nome\",\"\"),\"candidato_cpf\":c.get(\"cpf\",\"\"),\"processo\":c.get(\"processo\",\"\"),\"categoria\":c.get(\"categoria\",\"\"),\"veiculo\":e.get(\"veiculo\",\"\"),\"local\":e.get(\"local\",\"\"),\"examinador\":e.get(\"examinador\",\"\"),\"auto_escola\":e.get(\"auto_escola\",\"\"),\"rubrica\":e.get(\"rubrica\",\"1020/2025\"),\"training_annotations\":m.get(\"training_annotations\",[]),\"resultado_exame\":m.get(\"resultado_exame\")}, indent=2, ensure_ascii=False))'
"
```

---

## Notas

- **Re-submissões:** o mesmo renach pode ter vários `hash` (a mesma URL reenviada
  gera runs distintos). Ordene por `created_at DESC` e pegue o mais recente, ou
  inspecione todos.
- **Runs antigos (via sweep S3):** nesses o `upload.json` guarda a URL original em
  `video.gs_path_original_s3` em vez de `video.source_url` — a reconstrução já cobre
  os dois.
- **Endpoint backend:** `GET /api/exams/{hash}/init-upload` → `tooling/api_stub/server.py`
  (`_init_upload_inicial` / `get_init_upload`). Contrato do fluxo em
  [`docs/flows/init_upload.md`](../flows/init_upload.md).
