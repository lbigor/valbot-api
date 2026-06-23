#!/bin/bash
# Processa os 5 vídeos novos em sequência: yolo → pose → cv → tier_a
# Saída em /tmp/valbot_batch.log
set -u
cd /Users/igorlima/Documents/Valbot
PY=.venv/bin/python
LOG=/tmp/valbot_batch.log
echo "=== batch start $(date) ===" > "$LOG"

for v in storage/videos/0[1-5]*TREINO*.mp4; do
  name=$(basename "$v")
  echo "" >> "$LOG"
  echo "######## $name $(date +%H:%M:%S) ########" >> "$LOG"

  echo "-- yolo_explore --" >> "$LOG"
  $PY -m tooling.yolo_explore "$v" >> "$LOG" 2>&1
  echo "yolo done $(date +%H:%M:%S)" >> "$LOG"

  echo "-- pose_runner --" >> "$LOG"
  $PY -m tooling.pose_runner "$v" >> "$LOG" 2>&1
  echo "pose done $(date +%H:%M:%S)" >> "$LOG"

  echo "-- cv_detectors --" >> "$LOG"
  $PY -m tooling.cv_detectors_runner "$v" --samples 120 >> "$LOG" 2>&1
  echo "cv done $(date +%H:%M:%S)" >> "$LOG"

  echo "-- tier_a --" >> "$LOG"
  $PY -m src.tier_a_pipeline "$v" --force >> "$LOG" 2>&1
  echo "tier_a done $(date +%H:%M:%S)" >> "$LOG"
done

echo "" >> "$LOG"
echo "=== batch end $(date) ===" >> "$LOG"
