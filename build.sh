#!/usr/bin/env bash
# Exit on error
set -o errexit

# Update and install system deps (Tesseract + Chinese language packs)
apt-get update
apt-get install -y tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-chi-tra

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
