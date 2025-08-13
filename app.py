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
import tempfile
import shutil

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "your-secret-key-here")

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
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_image(image_path):
    """Extract text from image using Tesseract OCR"""
    try:
        # Open and preprocess image
        image = Image.open(image_path)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Use Tesseract to extract text
        text = pytesseract.image_to_string(image, lang='eng+chi_sim+chi_tra')
        return text.strip()
    except Exception as e:
        logging.error(f"Error extracting text from image: {str(e)}")
        raise

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF"""
    try:
        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        
        # If PDF text extraction failed or returned minimal text, try OCR
        if len(text.strip()) < 50:
            # Convert PDF pages to images and OCR them
            try:
                import pdf2image
                images = pdf2image.convert_from_path(pdf_path)
                ocr_text = ""
                for image in images:
                    # Save image temporarily
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
                        image.save(temp_img.name)
                        ocr_text += pytesseract.image_to_string(image, lang='eng+chi_sim+chi_tra') + "\n"
                        os.unlink(temp_img.name)
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
            except ImportError:
                logging.warning("pdf2image not available, using text extraction only")
        
        return text.strip()
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {str(e)}")
        raise

def translate_to_traditional_chinese(text):
    """Translate text to Traditional Chinese"""
    try:
        if not text.strip():
            return ""
        
        # Split text into chunks if too long (Google Translate has limits)
        max_chunk_size = 4500
        chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]
        
        translated_chunks = []
        for chunk in chunks:
            if chunk.strip():
                result = translator.translate(chunk, dest='zh-tw')
                translated_chunks.append(result.text)
        
        return '\n'.join(translated_chunks)
    except Exception as e:
        logging.error(f"Error translating text: {str(e)}")
        raise

@app.route('/')
def index():
    """Main page"""
    # Clear any previous session data
    session.pop('original_text', None)
    session.pop('translated_text', None)
    session.pop('filename', None)
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload PDF, PNG, or JPG files.'}), 400
        
        # Generate unique session ID if not exists
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        session_filename = f"{session['session_id']}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], session_filename)
        file.save(filepath)
        
        # Extract text based on file type
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        if file_ext == 'pdf':
            original_text = extract_text_from_pdf(filepath)
        elif file_ext in ['png', 'jpg', 'jpeg']:
            original_text = extract_text_from_image(filepath)
        else:
            raise ValueError("Unsupported file type")
        
        if not original_text.strip():
            # Clean up file
            os.remove(filepath)
            return jsonify({'error': 'No text could be extracted from the file. Please ensure the image contains readable text.'}), 400
        
        # Translate to Traditional Chinese
        translated_text = translate_to_traditional_chinese(original_text)
        
        # Store in session
        session['original_text'] = original_text
        session['translated_text'] = translated_text
        session['filename'] = filename
        session['filepath'] = filepath
        
        return jsonify({
            'success': True,
            'original_text': original_text,
            'translated_text': translated_text,
            'filename': filename
        })
        
    except Exception as e:
        logging.error(f"Error processing file: {str(e)}")
        # Clean up file if it exists
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

@app.route('/clear')
def clear_session():
    """Clear session data and uploaded files"""
    try:
        # Remove uploaded file if exists
        if 'filepath' in session and os.path.exists(session['filepath']):
            os.remove(session['filepath'])
        
        # Clear session data
        session.clear()
        
        return redirect(url_for('index'))
    except Exception as e:
        logging.error(f"Error clearing session: {str(e)}")
        return redirect(url_for('index'))

@app.teardown_appcontext
def cleanup_files(error):
    """Clean up temporary files when session ends"""
    try:
        if 'filepath' in session and os.path.exists(session['filepath']):
            os.remove(session['filepath'])
    except Exception as e:
        logging.error(f"Error in cleanup: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
