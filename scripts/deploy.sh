#!/bin/bash
set -e

cd /home/ubuntu/gugu-crawler

sudo dpkg --configure -a
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium

sudo cp /home/ubuntu/gugu-crawler/scripts/gugu-crawler.service /etc/systemd/system/gugu-crawler.service
sudo systemctl daemon-reload
sudo systemctl enable gugu-crawler
sudo systemctl restart gugu-crawler
