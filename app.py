import os
import logging
from flask import Flask, render_template, request, session, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from PIL import Image
import PyPDF2
from googletrans import Translator
import uuid
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


def translate_to_traditional_chinese(text):
    """Translate text to Traditional Chinese while preserving formatting"""
    try:
        if not text.strip():
            return ""
        translator = Translator()
        chunks = []
        current_chunk = ""
        lines = text.split('\n')
        for line in lines:
            if len(current_chunk + line + '\n') > 500 and current_chunk:
                chunks.append(current_chunk.rstrip())
                current_chunk = line + '\n'
            else:
                current_chunk += line + '\n'
        if current_chunk:
            chunks.append(current_chunk.rstrip())

        translated_chunks = []
        for chunk in chunks:
            if not chunk.strip():
                translated_chunks.append(chunk)
                continue
            try:
                result = translator.translate(chunk.strip(),
                                              src='auto',
                                              dest='zh-tw')
                if result and hasattr(
                        result,
                        'text') and result.text and result.text.strip():
                    translated_chunks.append(result.text)
                else:
                    translated_chunks.append(chunk)
            except Exception as e:
                logging.warning(f"Translation chunk failed: {e}")
                translated_chunks.append(chunk)

        return '\n'.join(translated_chunks)
    except Exception as e:
        logging.error(f"Translation failed: {str(e)}")
        return f"翻譯出現錯誤，以下為原始文本：\n\n{text}"


@app.route('/')
def index():
    """Main page"""
    session.pop('original_text', None)
    session.pop('translated_text', None)
    session.pop('filename', None)
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        if not file.filename or not allowed_file(file.filename):
            return jsonify({
                'error':
                'Invalid file type. Please upload PDF, PNG, or JPG files.'
            }), 400

        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())

        original_filename = file.filename or 'uploaded_file'
        filename = secure_filename(original_filename)
        if not filename:
            _, ext = os.path.splitext(original_filename)
            filename = f'uploaded_file{ext or ".txt"}'

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(filename)
        session_filename = f"{session['session_id']}_{name}_{timestamp}{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], session_filename)
        file.save(filepath)

        file_ext = filename.rsplit('.', 1)[1].lower()
        if file_ext == 'pdf':
            original_text = extract_text_from_pdf(filepath)
        elif file_ext in ['png', 'jpg', 'jpeg']:
            original_text = extract_text_from_image(filepath)
        else:
            raise ValueError("Unsupported file type")

        if not original_text.strip():
            os.remove(filepath)
            return jsonify({
                'error':
                'No text could be extracted. Please ensure the image contains readable text.'
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
        try:
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500


@app.route('/clear')
def clear_session():
    """Clear session data and uploaded files"""
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
    """Clean up temporary files when session ends"""
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
