# Relatório de simulação — pipeline em todos os vídeos

**Data:** 2026-04-28T09:52:16
**Vídeos processados:** 9
**Pipeline:** detector clássico (HSV+OCR+geometria) → dedupe temporal 3s → confidence ≥ 0.5

## Eventos detectados por vídeo

| # | Vídeo | Duração | R-1 | PARE chão | Faixa pedestre |
|---|---|---|---:|---:|---:|
| 1 | `01 - TREINO IA - PI401876730_00000039191` | 427s | 17 | 9 | 46 |
| 2 | `02 - TREINO IA - PI402296974_00000039154` | 309s | 2 | 7 | 18 |
| 3 | `03 - TREINO IA - PI403276152_00000039908` | 367s | 1 | 4 | 26 |
| 4 | `04 - TREINO IA - PI402152107_00000039155` | 262s | 4 | 11 | 22 |
| 5 | `05 - TREINO IA - PI402001923_00000039155` | 316s | 10 | 10 | 33 |
| 6 | `1.mp4` | 296s | 3 | 5 | 11 |
| 7 | `2.mp4` | 251s | 1 | 2 | 10 |
| 8 | `3.mp4` | 259s | 0 | 4 | 3 |
| 9 | `4.mp4` | 300s | 0 | 2 | 7 |

## Eventos detalhados (ts inicial, câmera, confidence)

### 1. 01 - TREINO IA - PI401876730_000000391911.mp4

**vertical/pare-r1** — 17 eventos:
- 01:08–01:08  `frontal`  conf=0.56  (1 frames)
- 03:10–03:10  `frontal`  conf=0.59  (1 frames)
- 03:31–03:31  `frontal`  conf=0.54  (1 frames)
- 03:48–03:48  `frontal`  conf=0.60  (1 frames)
- 03:54–03:54  `frontal`  conf=0.72  (1 frames)
- 03:59–04:00  `frontal`  conf=0.72  (2 frames)
- 04:06–04:09  `frontal`  conf=0.75  (2 frames)
- 05:37–05:37  `frontal`  conf=0.61  (1 frames)
- ...mais 9 eventos

**horizontal/pare-chao** — 9 eventos:
- 00:00–01:21  `frontal`  conf=0.95  (79 frames)
- 01:25–01:25  `frontal`  conf=0.75  (1 frames)
- 01:29–01:30  `frontal`  conf=0.70  (2 frames)
- 02:15–02:15  `frontal`  conf=0.70  (1 frames)
- 02:40–02:40  `frontal`  conf=0.70  (1 frames)
- 02:46–03:55  `frontal`  conf=0.95  (63 frames)
- 03:59–04:53  `frontal`  conf=0.95  (46 frames)
- 05:05–06:17  `frontal`  conf=0.95  (68 frames)
- ...mais 1 eventos

**horizontal/faixa-pedestre** — 46 eventos:
- 01:14–01:14  `frontal`  conf=0.61  (1 frames)
- 01:20–01:20  `frontal`  conf=0.53  (1 frames)
- 01:27–01:27  `frontal`  conf=0.68  (1 frames)
- 01:31–01:52  `frontal`  conf=0.76  (20 frames)
- 01:57–01:57  `frontal`  conf=0.68  (1 frames)
- 02:02–02:02  `frontal`  conf=0.61  (1 frames)
- 02:07–02:07  `frontal`  conf=0.60  (1 frames)
- 02:11–02:11  `frontal`  conf=0.61  (1 frames)
- ...mais 38 eventos

### 2. 02 - TREINO IA - PI402296974_000000391541.mp4

**vertical/pare-r1** — 2 eventos:
- 01:42–01:43  `traseira_esq`  conf=0.60  (2 frames)
- 02:17–02:17  `traseira_esq`  conf=0.57  (1 frames)

**horizontal/pare-chao** — 7 eventos:
- 03:29–03:29  `frontal`  conf=0.70  (1 frames)
- 03:35–03:35  `frontal`  conf=0.70  (1 frames)
- 03:39–03:39  `frontal`  conf=0.55  (1 frames)
- 03:44–03:47  `frontal`  conf=0.70  (3 frames)
- 03:56–03:56  `frontal`  conf=0.55  (1 frames)
- 04:00–04:04  `frontal`  conf=0.90  (4 frames)
- 04:10–04:13  `frontal`  conf=0.70  (4 frames)

**horizontal/faixa-pedestre** — 18 eventos:
- 00:10–00:10  `frontal`  conf=0.53  (1 frames)
- 00:27–00:29  `frontal`  conf=0.61  (3 frames)
- 01:17–01:24  `frontal`  conf=0.61  (6 frames)
- 01:32–01:49  `frontal`  conf=0.76  (14 frames)
- 02:31–02:32  `frontal`  conf=0.58  (2 frames)
- 03:01–03:01  `frontal`  conf=0.51  (1 frames)
- 03:25–03:25  `frontal`  conf=0.70  (1 frames)
- 03:47–03:47  `frontal`  conf=0.53  (1 frames)
- ...mais 10 eventos

### 3. 03 - TREINO IA - PI403276152_000000399082.mp4

**vertical/pare-r1** — 1 eventos:
- 05:12–05:12  `frontal`  conf=0.60  (1 frames)

**horizontal/pare-chao** — 4 eventos:
- 00:00–01:36  `frontal`  conf=0.95  (91 frames)
- 01:43–01:50  `frontal`  conf=0.70  (6 frames)
- 02:26–04:29  `frontal`  conf=0.95  (109 frames)
- 04:34–06:06  `frontal`  conf=0.95  (82 frames)

**horizontal/faixa-pedestre** — 26 eventos:
- 00:16–00:16  `frontal`  conf=0.69  (1 frames)
- 00:24–00:27  `frontal`  conf=0.69  (3 frames)
- 00:32–00:32  `frontal`  conf=0.68  (1 frames)
- 01:13–02:24  `frontal`  conf=0.85  (68 frames)
- 02:30–02:36  `frontal`  conf=0.70  (4 frames)
- 02:41–02:41  `frontal`  conf=0.68  (1 frames)
- 02:46–04:03  `frontal`  conf=0.69  (74 frames)
- 04:07–04:08  `frontal`  conf=0.60  (2 frames)
- ...mais 18 eventos

### 4. 04 - TREINO IA - PI402152107_000000391558.mp4

**vertical/pare-r1** — 4 eventos:
- 02:50–02:50  `frontal`  conf=0.59  (1 frames)
- 01:35–01:35  `traseira_esq`  conf=0.69  (1 frames)
- 01:45–01:45  `traseira_esq`  conf=0.55  (1 frames)
- 02:53–02:53  `traseira_esq`  conf=0.59  (1 frames)

**horizontal/pare-chao** — 11 eventos:
- 00:00–00:44  `frontal`  conf=0.90  (42 frames)
- 01:16–01:18  `frontal`  conf=0.70  (2 frames)
- 01:22–01:34  `frontal`  conf=0.95  (11 frames)
- 01:38–02:32  `frontal`  conf=0.95  (46 frames)
- 02:42–02:42  `frontal`  conf=0.55  (1 frames)
- 02:48–03:23  `frontal`  conf=0.95  (32 frames)
- 03:29–03:33  `frontal`  conf=0.60  (4 frames)
- 03:39–03:40  `frontal`  conf=0.80  (2 frames)
- ...mais 3 eventos

**horizontal/faixa-pedestre** — 22 eventos:
- 00:05–00:07  `frontal`  conf=0.60  (3 frames)
- 00:11–00:11  `frontal`  conf=0.60  (1 frames)
- 00:15–00:21  `frontal`  conf=0.76  (5 frames)
- 00:33–00:59  `frontal`  conf=0.84  (20 frames)
- 01:07–01:22  `frontal`  conf=0.70  (12 frames)
- 01:26–01:37  `frontal`  conf=0.69  (7 frames)
- 01:41–02:07  `frontal`  conf=0.83  (21 frames)
- 02:17–02:18  `frontal`  conf=0.60  (2 frames)
- ...mais 14 eventos

### 5. 05 - TREINO IA - PI402001923_000000391553.mp4

**vertical/pare-r1** — 10 eventos:
- 01:03–01:03  `frontal`  conf=0.61  (1 frames)
- 02:49–02:49  `frontal`  conf=0.51  (1 frames)
- 02:54–02:54  `frontal`  conf=0.54  (1 frames)
- 00:39–00:42  `traseira_esq`  conf=0.55  (2 frames)
- 01:10–01:10  `traseira_esq`  conf=0.60  (1 frames)
- 01:20–01:20  `traseira_esq`  conf=0.56  (1 frames)
- 01:27–01:27  `traseira_esq`  conf=0.61  (1 frames)
- 03:43–03:43  `traseira_esq`  conf=0.57  (1 frames)
- ...mais 2 eventos

**horizontal/pare-chao** — 10 eventos:
- 00:00–00:31  `frontal`  conf=0.95  (29 frames)
- 00:38–00:46  `frontal`  conf=0.75  (9 frames)
- 00:58–01:35  `frontal`  conf=0.95  (33 frames)
- 01:46–02:05  `frontal`  conf=0.95  (13 frames)
- 02:10–02:13  `frontal`  conf=0.70  (4 frames)
- 02:17–02:45  `frontal`  conf=0.95  (27 frames)
- 02:50–02:52  `frontal`  conf=0.95  (3 frames)
- 02:56–03:07  `frontal`  conf=0.90  (9 frames)
- ...mais 2 eventos

**horizontal/faixa-pedestre** — 33 eventos:
- 00:05–00:09  `frontal`  conf=0.50  (3 frames)
- 00:20–00:20  `frontal`  conf=0.61  (1 frames)
- 00:24–00:49  `frontal`  conf=0.76  (19 frames)
- 01:00–01:00  `frontal`  conf=0.60  (1 frames)
- 01:06–01:09  `frontal`  conf=0.69  (3 frames)
- 01:18–01:18  `frontal`  conf=0.70  (1 frames)
- 01:22–01:45  `frontal`  conf=0.69  (15 frames)
- 02:08–02:13  `frontal`  conf=0.65  (4 frames)
- ...mais 25 eventos

### 6. 1.mp4

**vertical/pare-r1** — 3 eventos:
- 01:40–01:40  `frontal`  conf=0.69  (1 frames)
- 01:40–01:40  `traseira_esq`  conf=0.55  (1 frames)
- 02:05–02:05  `traseira_esq`  conf=0.67  (1 frames)

**horizontal/pare-chao** — 5 eventos:
- 00:31–00:35  `frontal`  conf=0.80  (5 frames)
- 03:07–03:07  `frontal`  conf=0.60  (1 frames)
- 03:43–03:51  `frontal`  conf=0.90  (6 frames)
- 03:59–04:37  `frontal`  conf=0.90  (38 frames)
- 04:48–04:55  `frontal`  conf=0.60  (8 frames)

**horizontal/faixa-pedestre** — 11 eventos:
- 00:31–00:31  `frontal`  conf=0.60  (1 frames)
- 00:36–00:48  `frontal`  conf=0.60  (10 frames)
- 00:53–01:24  `frontal`  conf=0.69  (31 frames)
- 01:29–01:29  `frontal`  conf=0.61  (1 frames)
- 03:11–03:11  `frontal`  conf=0.53  (1 frames)
- 03:15–03:15  `frontal`  conf=0.60  (1 frames)
- 03:48–03:48  `frontal`  conf=0.53  (1 frames)
- 04:19–04:19  `frontal`  conf=0.53  (1 frames)
- ...mais 3 eventos

### 7. 2.mp4

**vertical/pare-r1** — 1 eventos:
- 00:03–00:03  `traseira_esq`  conf=0.53  (1 frames)

**horizontal/pare-chao** — 2 eventos:
- 01:40–01:43  `frontal`  conf=0.90  (4 frames)
- 03:18–03:23  `frontal`  conf=0.95  (6 frames)

**horizontal/faixa-pedestre** — 10 eventos:
- 00:13–00:13  `frontal`  conf=0.53  (1 frames)
- 00:19–00:23  `frontal`  conf=0.61  (3 frames)
- 01:33–01:36  `frontal`  conf=0.61  (2 frames)
- 01:50–01:52  `frontal`  conf=0.61  (3 frames)
- 01:58–02:19  `frontal`  conf=0.53  (19 frames)
- 03:26–03:28  `frontal`  conf=0.69  (2 frames)
- 03:33–03:35  `frontal`  conf=0.61  (2 frames)
- 03:39–04:10  `frontal`  conf=0.68  (30 frames)
- ...mais 2 eventos

### 8. 3.mp4

**horizontal/pare-chao** — 4 eventos:
- 00:18–00:19  `frontal`  conf=0.70  (2 frames)
- 02:17–03:06  `frontal`  conf=0.80  (47 frames)
- 03:32–03:39  `frontal`  conf=0.65  (5 frames)
- 03:45–03:55  `frontal`  conf=0.60  (8 frames)

**horizontal/faixa-pedestre** — 3 eventos:
- 00:13–00:13  `frontal`  conf=0.60  (1 frames)
- 00:22–00:22  `frontal`  conf=0.61  (1 frames)
- 03:17–03:26  `frontal`  conf=0.58  (8 frames)

### 9. 4.mp4

**horizontal/pare-chao** — 2 eventos:
- 00:39–00:40  `frontal`  conf=0.60  (2 frames)
- 04:52–04:52  `frontal`  conf=0.60  (1 frames)

**horizontal/faixa-pedestre** — 7 eventos:
- 00:00–00:18  `frontal`  conf=0.70  (18 frames)
- 00:48–00:51  `frontal`  conf=0.53  (2 frames)
- 00:59–01:08  `frontal`  conf=0.69  (10 frames)
- 01:12–01:22  `frontal`  conf=0.70  (11 frames)
- 03:06–03:12  `frontal`  conf=0.53  (7 frames)
- 04:45–04:48  `frontal`  conf=0.60  (2 frames)
- 05:00–05:00  `frontal`  conf=0.53  (1 frames)

## Totais cross-vídeo

- **vertical/pare-r1**: 38 eventos
- **horizontal/pare-chao**: 54 eventos
- **horizontal/faixa-pedestre**: 176 eventos
