#!/bin/bash
set -e

cd /home/ubuntu/gugu-crawler

sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium

sudo systemctl restart gugu-crawler
