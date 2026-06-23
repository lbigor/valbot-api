# Prompts VALBOT — Tier 1 (MVP v0.1)

Especificação canônica dos prompts enviados à VLM para cada infração detectável com ≥85% de assertividade.

## Princípios de design

1. **Um prompt = uma infração.** Não misturamos itens no mesmo call.
2. **Só a câmera relevante é enviada.** Não o grid 2×2 inteiro. Resolução útil efetiva: 640×360.
3. **System prompt estável**, user prompt traz só timestamp/contexto variável.
4. **Saída JSON estrita** — 4 campos: `detected`, `confidence`, `evidence`, `timestamp_relative_s`.
5. **Eventos temporais enviam sequência de frames**, não um frame único.
6. **Prefira falso negativo a falso positivo** — em caso de dúvida, `detected=null`.

## Ajustes v2 (pós-execução real nos vídeos)

- **CINTO**: system prompt reconhece que o condutor está à DIREITA da imagem no layout VIP Intelbras (não à esquerda como era o default).
- **MAO_FORA_VOLANTE**: aceita "1 mão visível no volante = OK", porque a câmera interna não enquadra ambas as mãos simultaneamente.

## Estrutura de um call completo

```python
{
    "model": "claude-sonnet-4-5" | "qwen2.5-vl-7b",
    "temperature": 0.0,
    "max_tokens": 400,
    "system": <system_prompt da infração>,
    "messages": [{
        "role": "user",
        "content": [
            {"type": "image", "source": <frame_1>},
            {"type": "image", "source": <frame_2>},
            ...
            {"type": "text", "text": <user_prompt formatado>}
        ]
    }]
}
```

---

## Resumo rápido dos 7 prompts

| # | Prompt | Câmera | Frames | Severidade | Assertividade |
|---|---|---|---|---|---|
| 1 | CINTO | INTERNA | 1 | Eliminatória | 95% |
| 2 | MEIO_FIO | TRASEIRA-ESQ | 3 | Eliminatória | 90% |
| 3 | LINHA_RETENCAO | FRONTAL | 5 | Eliminatória | 90% |
| 4 | PARE_CHAO | FRONTAL | 5 | Eliminatória | 90% |
| 5 | MAO_FORA_VOLANTE | INTERNA | 4 | Leve | 88% |
| 6 | SEMAFORO_VERMELHO | FRONTAL | 5 | Eliminatória | 85% |
| 7 | ZEBRADO | FRONTAL | 3 | Grave | 85% |

---

## Orquestração — como o pipeline usa os 7 prompts

```
para cada keyframe:
    se keyframe.camera_hint == INTERNA:
        rodar CINTO (1 frame)
        rodar MAO_FORA_VOLANTE (4 frames consecutivos)
    se keyframe.camera_hint == FRONTAL:
        rodar LINHA_RETENCAO (5 frames)
        rodar PARE_CHAO (5 frames)
        rodar SEMAFORO_VERMELHO (5 frames)
        rodar ZEBRADO (3 frames)
    se keyframe.camera_hint == TRASEIRA_ESQ:
        rodar MEIO_FIO (3 frames)
```

**Observação:** mesmo sem keyframe, `CINTO` roda 1× a cada 30 segundos (amostragem regular).

## Custo estimado por vídeo

Para prova de ~40 min com ~60 keyframes detectados:
- **Claude Sonnet 4 via API:** R$ 0,15-0,25 por vídeo (estimativa original)
- **Custo real medido em execução:** ~R$ 17 por prova completa (10× mais alto que estimado)
- **Qwen 7B local (Runpod RTX 4090):** ~R$ 0,03 por vídeo (compute only)

Com event-windowing (detectores OpenCV filtrando frames antes do VLM), o custo cai em 7-10x. Ver `src/detectors/` para implementação.

## Próxima iteração

Depois de validar os 7 Tier 1 num dataset de 20-30 vídeos rotulados, medir precisão real de cada item e só então adicionar Tier 2 um por um, só se atingir ≥80% de precisão no holdout.

Ver especificação completa de cada prompt em `src/prompts/tier1.py`.
