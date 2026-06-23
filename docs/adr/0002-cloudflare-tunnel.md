# ADR 0002 — Cloudflare Tunnel vs IP estático + certbot

- **Status:** aceito
- **Data:** 2026-05-05
- **Decisores:** Igor Lima

## Contexto

A VM `valbot-prod` precisa expor `valbot.stillflows.com.br` na internet com HTTPS, e também permitir acesso remoto pelo iPad (code-server + SSH). Duas abordagens:

### A. IP público + nginx + certbot (Let's Encrypt)
- Reservar IP estático GCP (~$3.60/mês quando atrelado).
- Abrir 80/443 no firewall.
- Nginx + certbot renova SSL a cada 90 dias.
- DNS A-record direto pro IP da VM.

### B. Cloudflare Tunnel
- Container `cloudflared` na VM cria conexão saída pra rede Cloudflare.
- Sem IP público necessário — VM fica em rede privada.
- SSL automático em todos os hostnames.
- Cloudflare Access nativo pra autenticação (login email).
- Já é o padrão usado no projeto: `ooo.stillflows.com.br` (MCP "Projetos Igor") roda via Cloudflare Tunnel `ooo-mcp`.

## Decisão

Usar **Cloudflare Tunnel** (caminho B).

## Consequências

### Positivas
- Zero firewall a configurar — VM nem precisa de IP público.
- SSL gratuito + renovação automática + edge caching de CF.
- Cloudflare Access protege `/code` (code-server) e SSH com login email — sem precisar de senha forte exposta.
- Padrão consistente com `ooo.stillflows.com.br`.
- Permite múltiplos hostnames no mesmo tunnel (`valbot.stillflows.com.br` + `ssh.valbot.stillflows.com.br`).
- Sem custo recorrente do Tunnel (free tier cobre pra MVP — limite 50 usuários no Access free).

### Negativas
- Toda request passa pela rede Cloudflare — adiciona ~10-30ms vs conexão direta.
- Logs de acesso ficam no painel Cloudflare (não em arquivo local).
- Se Cloudflare cair, site cai junto — mas é o mesmo risco de qualquer CDN.
- Token do tunnel é um secret crítico (vai em `.env` da VM).

### Mitigações
- Token rotaciona-se trivial no painel Cloudflare se vazar.
- Cloudflare uptime histórico é > 99.99%.
- Logs estruturados do app (structlog JSON) ficam locais; CF só loga edge.
