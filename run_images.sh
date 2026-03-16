#!/bin/bash
# run_images.sh — runs image carousel pipeline
# Called by cron 1x daily at 9AM IST

cd /home/ubuntu/freakybits
source .env
python3 pipeline.py images >> logs/cron_images.log 2>&1
