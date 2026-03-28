#!/bin/bash
set -e

cd /home/ubuntu/gugu-crawler

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium

sudo systemctl restart gugu-crawler
