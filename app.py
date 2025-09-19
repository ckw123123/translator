import os
import logging
from flask import Flask, render_template, request, session, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import PyPDF2
import io
from googletrans import Translator
import uuid
import time
from datetime import datetime
import requests
import pdf2image

# Use your real OCR.space API key (fallback to demo if not set)
OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY", "helloworld")

# Explicitly set Tesseract path
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "your-secret-key-here")


@app.route("/health")
def health():
    import subprocess
    try:
        version = subprocess.check_output(["tesseract", "--version"],
                                          text=True)
        return f"Tesseract is installed:\n{version}", 200
    except Exception as e:
        return f"Tesseract check failed: {e}", 500


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
    return '.' in filename and filename.rsplit(
        '.', 1)[1].lower() in ALLOWED_EXTENSIONS


def clean_and_preserve_formatting(text):
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
    """Try OCR.space (cht only), fallback to local Tesseract"""
    try:
        with open(image_path, 'rb') as f:
            r = requests.post(
                "https://api.ocr.space/parse/image",
                files={"file": f},
                data={
                    "apikey": OCR_SPACE_API_KEY,
                    "language": "cht",  # Traditional Chinese only
                },
                timeout=60)
        result = r.json()
        logging.debug(f"OCR.space response: {result}")

        if "ParsedResults" in result and result["ParsedResults"]:
            parsed_text = result["ParsedResults"][0].get("ParsedText", "")
            if parsed_text.strip():
                return clean_and_preserve_formatting(parsed_text)
    except Exception as e:
        logging.warning(f"OCR.space failed: {e}")

    # Fallback: Tesseract
    try:
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
        text = pytesseract.image_to_string(
            image,
            lang='eng+chi_tra',  # English + Traditional Chinese
            config=custom_config)
        return clean_and_preserve_formatting(text)
    except Exception as e:
        logging.error(f"Tesseract fallback failed: {e}")
        raise


def extract_text_from_pdf(pdf_path):
    """Try OCR.space (cht only), fallback to local PyPDF2 + Tesseract"""
    try:
        with open(pdf_path, 'rb') as f:
            r = requests.post("https://api.ocr.space/parse/image",
                              files={"file": f},
                              data={
                                  "apikey": OCR_SPACE_API_KEY,
                                  "language": "cht",
                              },
                              timeout=120)
        result = r.json()
        logging.debug(f"OCR.space response (PDF): {result}")

        if "ParsedResults" in result and result["ParsedResults"]:
            parsed_text = result["ParsedResults"][0].get("ParsedText", "")
            if parsed_text.strip():
                return clean_and_preserve_formatting(parsed_text)
    except Exception as e:
        logging.warning(f"OCR.space failed on PDF: {e}")

    # Fallback: Local PyPDF2 + Tesseract
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text += page_text + "\n\n"

        if len(text.strip()) < 50:  # fallback OCR if text too weak
            images = pdf2image.convert_from_path(pdf_path)
            for image in images:
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
                page_text = pytesseract.image_to_string(image,
                                                        lang='eng+chi_tra',
                                                        config=custom_config)
                if page_text.strip():
                    text += page_text + "\n\n"
    except Exception as e:
        logging.error(f"Local PDF extraction failed: {e}")

    return clean_and_preserve_formatting(text)


def translate_to_traditional_chinese(text):
    try:
        if not text.strip():
            return ""
        translator = Translator()
        result = translator.translate(text, src='auto', dest='zh-tw')
        return clean_and_preserve_formatting(
            result.text if result.text else text)
    except Exception as e:
        logging.error(f"Translation failed: {e}")
        return f"翻譯出現錯誤，以下為原始文本：\n\n{text}"


@app.route('/')
def index():
    session.pop('original_text', None)
    session.pop('translated_text', None)
    session.pop('filename', None)
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        if not allowed_file(file.filename):
            return jsonify({
                'error':
                'Invalid file type. Please upload PDF, PNG, or JPG files.'
            }), 400

        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())

        original_filename = file.filename
        filename = secure_filename(original_filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(filename)
        session_filename = f"{session['session_id']}_{name}_{timestamp}{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], session_filename)
        file.save(filepath)

        file_ext = filename.rsplit('.', 1)[1].lower()
        if file_ext == 'pdf':
            original_text = extract_text_from_pdf(filepath)
        else:
            original_text = extract_text_from_image(filepath)

        if not original_text.strip():
            os.remove(filepath)
            return jsonify({
                'error':
                'No text could be extracted from the file. Please ensure it contains readable text.'
            }), 400

        translated_text = translate_to_traditional_chinese(original_text)

        session['original_text'] = original_text
        session['translated_text'] = translated_text
        session['filename'] = original_filename
        session['filepath'] = filepath

        return jsonify({
            'success': True,
            'original_text': original_text,
            'translated_text': translated_text,
            'filename': original_filename
        })
    except Exception as e:
        logging.error(f"Error processing file: {str(e)}")
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500


@app.route('/clear')
def clear_session():
    try:
        if 'filepath' in session and os.path.exists(session['filepath']):
            os.remove(session['filepath'])
        session.clear()
        return redirect(url_for('index'))
    except Exception as e:
        logging.error(f"Error clearing session: {str(e)}")
        return redirect(url_for('index'))


@app.teardown_appcontext
def cleanup_files(error):
    try:
        from flask import has_request_context
        if has_request_context() and 'filepath' in session and os.path.exists(
                session['filepath']):
            os.remove(session['filepath'])
    except Exception as e:
        logging.error(f"Error in cleanup: {str(e)}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
