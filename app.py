import os
import logging
from flask import Flask, render_template, request, session, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from PIL import Image
import PyPDF2
import io
from googletrans import Translator
import uuid
import tempfile
import shutil
import time
from datetime import datetime
import requests

# Use your real OCR.space API key (fallback to demo if not set)
OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY", "helloworld")

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "your-secret-key-here")


@app.route("/health")
def health():
    return "App is running and OCR.space mode is active.", 200


# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize translator
translator = Translator()


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit(
        '.', 1)[1].lower() in ALLOWED_EXTENSIONS


def clean_and_preserve_formatting(text):
    """Clean up text while preserving formatting structure"""
    if not text:
        return ""
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.rstrip()
        if not line.strip():
            cleaned_lines.append('')
            continue
        cleaned_lines.append(line)
    import re
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def extract_text_from_image(image_path):
    """Use OCR.space only"""
    try:
        with open(image_path, 'rb') as f:
            r = requests.post(
                "https://api.ocr.space/parse/image",
                files={"file": f},
                data={
                    "apikey": OCR_SPACE_API_KEY,
                    "language":
                    "eng,chs,cht",  # English + Simplified + Traditional Chinese
                },
                timeout=60)
        result = r.json()
        logging.debug(f"OCR.space response: {result}")
        if "ParsedResults" in result and result["ParsedResults"]:
            parsed_text = result["ParsedResults"][0].get("ParsedText", "")
            return clean_and_preserve_formatting(parsed_text)
        return ""
    except Exception as e:
        logging.error(f"OCR.space failed: {e}")
        return ""


def extract_text_from_pdf(pdf_path):
    """Use OCR.space only (for PDFs)"""
    try:
        with open(pdf_path, 'rb') as f:
            r = requests.post("https://api.ocr.space/parse/image",
                              files={"file": f},
                              data={
                                  "apikey": OCR_SPACE_API_KEY,
                                  "language": "eng,chs,cht",
                              },
                              timeout=120)
        result = r.json()
        logging.debug(f"OCR.space PDF response: {result}")
        if "ParsedResults" in result and result["ParsedResults"]:
            parsed_text = result["ParsedResults"][0].get("ParsedText", "")
            return clean_and_preserve_formatting(parsed_text)
        return ""
    except Exception as e:
        logging.error(f"OCR.space failed on PDF: {e}")
        return ""
