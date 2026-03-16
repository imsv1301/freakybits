#!/bin/bash
# run_videos.sh — runs video pipeline
# Called by cron 4x daily

cd /home/ubuntu/freakybits
source .env
python3 pipeline.py video >> logs/cron_video.log 2>&1
