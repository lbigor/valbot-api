# Briefing de Discovery — Val Auditor Exames

> Fonte primária: *Val Auditor Exames — Especificação Funcional v2.0* (Valma, jun/2026).
> Base normativa: Resolução CONTRAN nº 1.020/2025 + MBEDV (Senatran, 01/02/2026).
> Projeto **já existente** (backend Python/FastAPI + frontend React 19). Briefing derivado da spec; lacunas de entrega em *Itens a Definir*.

## 1. Visão e Propósito

Plataforma de **auditoria técnico-regulatória** do exame prático de direção veicular (CNH). Recebe vídeo/áudio/dados do exame, detecta eventos de condução por IA, enquadra cada evento no artigo do CTB + ficha do MBEDV, calcula a pontuação normativa, compara com o resultado oficial da Comissão Examinadora e gera laudo explicável com trilha de auditoria.

**Posicionamento (🔴 inegociável):** a IA **não substitui** a Comissão de Exame — ela **apoia, audita, evidencia e recomenda**. A decisão formal permanece humana. Reposicionamento de "IA que confere resultado" → "plataforma de auditoria técnico-regulatória" (juridicamente defensável).

**Diferencial:** visão computacional + Matriz Nacional CTB/MBEDV versionada + trilha de auditoria + laudo explicável + detecção de comentários proibidos do examinador (áudio). Cobertura próxima de **100%** dos exames vs. ~27% de auditoria humana atual.

## 2. Usuários e Stakeholders

| Ator | Papel |
|---|---|
| **Auditor** (Techpark, nível 3) | Recebe OS com laudo do Comitê, analisa, registra parecer |
| **Supervisor** (Techpark, nível 4) | Analisa TODA divergência, emite decisão final |
| **Comissão de Exame** | Registra resultado oficial (no Techpark); decisão formal do exame |
| **Admin Techpark / Admin Valma** | Operação e dashboards |
| Candidato / DETRAN / Senatran / TCU / MP / Jurídico | Consumidores do laudo (contestação, controle) |

- **Cliente:** Techpark (controladora dos dados). **Fornecedor:** Valma (operadora LGPD).
- **Time Valma** `[fornecido]`: Krysler (Produto), Victor (Spec/Pricing), Rodrigo (Arquitetura/Coordenação), Igor (Desenvolvimento).

## 3. Escopo

### MVP / Piloto `[fornecido]`
- Cliente piloto: **Techpark — CTR-SE**, ~**6.000 exames/mês**, **30 dias**, parecer **sem efeito formal** na decisão.
- 5 motores (Evidências, Detecção, Normativo, Pontuação, Comparação) + Comitê de IA + OS (4 níveis) + Portais Auditor/Supervisor + Dashboard Regulatório.
- **Matriz mínima viável** (top ~30 condutas mais frequentes), construída com especialista da Techpark `[recomendação Alt. B/C]`.
- Integração Techpark por **polling REST**.

### Pós-MVP
- Matriz completa (todos artigos CTB/fichas MBEDV); expansão por categoria (B/A → C/D/E) e por unidade (CTR-MA, CTR-PE…).
- Retroalimentação batch mensal (evolui modelos + Matriz).

### Fora de escopo (🔴)
- IA decidir o resultado do exame — decisão é sempre humana.
- Tratamento especial para prepostos (seguem o mesmo fluxo de 4 níveis).

## 4. Prioridades e Trade-offs
- **Rigor acima de velocidade** no Comitê de IA (SLA do Comitê pode exceder o da IA Principal).
- **Explicabilidade/segurança jurídica** acima de automação total — todo evento fundamentado em norma vinculante.
- Matriz mínima viável primeiro (validar metodologia no piloto) vs. matriz completa de dia 1.

## 5. Restrições
- **Normativas (🔴):** Resolução 1.020/2025 + MBEDV vinculantes; pontuação acumulativa leve=1/média=2/grave=4/gravíssima=6, aprovação ≤10; sem faltas eliminatórias automáticas; exame interrompido = categoria especial sem nota.
- **LGPD:** Valma operadora (Art. 39); CPF mascarado em logs/PDF; cripto em trânsito (HTTPS) e repouso; retenção a definir com Techpark.
- **Trilha de auditoria:** write-once, retenção mínima 12 meses; logs de acesso ≥6 meses.
- **Entrega/equipe/budget:** ver *Itens a Definir* (não especificados na spec funcional).

## 6. Stack Técnica
- **Sugerida na spec §20:** Python/FastAPI (ingestão), RabbitMQ/SQS (fila), Python+GPU (detecção), Motores Normativo/Pontuação/Comparação determinísticos (Python), PostgreSQL + Redis + versionamento (Matriz), S3 (mídia), **React + TypeScript** (portais), Grafana/Prometheus/Loki, K8s/Docker Compose.
- **Implementação real `[inferido do repo]`:** backend Python/FastAPI (backend v2 = 5 motores + Comitê + OS + Matriz MBEDV/84 fichas, migrations 009–016, 38 testes); frontend React 19 + Vite + wouter + TanStack Query + Tailwind v4; **GCP + Gemini (Vertex)** como provedor/VLM (diverge da sugestão AWS da spec); Postgres 16. Integração Techpark: polling REST (cursor incremental, API Key + IP allowlist, ~5 min).

## 7. Qualidade e Padrões
- **Go/No-Go do piloto:** ≥95% exames processados sem falha; ≥99% uptime; análise IA ≤ duração do vídeo (NFR ≤5 min); ≥90% enquadramentos corretos; cálculo idêntico à Resolução 1.020/2025; nenhum incidente crítico sem solução.
- **NFRs:** throughput ≥200 exames/h; escala 100k/mês; RTO ≤4h, RPO ≤1h; backup diário (≥30 dias); navegadores Chrome/Edge/Firefox (2 últimas).
- **Testes/CI `[inferido do repo]`:** pytest (38 testes backend v2), GitHub Actions, coverage gate.
- **Laudo explicável:** PDF + JSON, hash de integridade.

## 8. Visão de Futuro
- Expansão de categorias CNH e unidades; mais estados (portarias estaduais).
- Retroalimentação automatizada (batch mensal com revisão técnica antes da promoção).
- Provedor brasileiro por soberania de dados; GPU dedicada em regime permanente.
- Matriz Nacional como ativo evolutivo — atualizações normativas viram nova versão sem retreinar a IA.

## Itens a Definir (pendências — spec §21)
**Com a Techpark:** padrão da API de polling (endpoints/auth/payload); confirmação de que o resultado oficial traz pontuação + infrações enquadradas; política de retenção de vídeos; localização do arquivamento de relatórios; SLAs de Auditor/Supervisor; autenticação de usuários (SSO vs login local); Auditores/Supervisores designados; acesso aos critérios atuais (mapear divergências de transição).
**Internas (Valma):** alternativas técnicas marcadas 🔧 (Rodrigo); top 30 condutas da Matriz (Krysler + especialista); regras do Comitê de IA (Krysler + Igor); treinamento inicial p/ nova lógica (Rodrigo + Igor); custo de infra e provedor cloud (Rodrigo); critérios numéricos de aceite Go/No-Go (Krysler + Victor).
**Entrega:** prazo/cronograma do produto, alocação/dedicação da equipe e budget — não especificados na spec funcional.
