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
import time
from datetime import datetime

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

def clean_and_preserve_formatting(text):
    """Clean up text while preserving formatting structure"""
    if not text:
        return ""
    
    # Split into lines and process each line
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Strip trailing whitespace but preserve leading whitespace for indentation
        line = line.rstrip()
        
        # Preserve empty lines for paragraph breaks
        if not line.strip():
            cleaned_lines.append('')
            continue
            
        # Keep the line as is to preserve bullet points, numbers, and spacing
        cleaned_lines.append(line)
    
    # Join lines and clean up excessive empty lines (max 2 consecutive)
    result = '\n'.join(cleaned_lines)
    
    # Replace multiple consecutive newlines with max 2
    import re
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result.strip()

def extract_text_from_image(image_path):
    """Extract text from image using Tesseract OCR"""
    try:
        # Open and preprocess image
        image = Image.open(image_path)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Use Tesseract with PSM 6 (uniform block of text) to preserve structure
        custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
        text = pytesseract.image_to_string(image, lang='eng+chi_sim+chi_tra', config=custom_config)
        
        # Clean up text while preserving structure
        return clean_and_preserve_formatting(text)
    except Exception as e:
        logging.error(f"Error extracting text from image: {str(e)}")
        raise

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF"""
    try:
        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text.strip():
                    text += page_text + "\n\n"  # Add page breaks
        
        # If PDF text extraction failed or returned minimal text, try OCR
        if len(text.strip()) < 50:
            # Convert PDF pages to images and OCR them
            try:
                import pdf2image
                images = pdf2image.convert_from_path(pdf_path)
                ocr_text = ""
                for i, image in enumerate(images):
                    # Save image temporarily
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
                        image.save(temp_img.name)
                        custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
                        page_text = pytesseract.image_to_string(image, lang='eng+chi_sim+chi_tra', config=custom_config)
                        if page_text.strip():
                            ocr_text += page_text + "\n\n"  # Add page breaks
                        os.unlink(temp_img.name)
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
            except ImportError:
                logging.warning("pdf2image not available, using text extraction only")
        
        return clean_and_preserve_formatting(text)
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {str(e)}")
        raise

def translate_to_traditional_chinese(text):
    """Translate text to Traditional Chinese while preserving formatting"""
    try:
        if not text.strip():
            return ""
        
        # Create translator with better error handling
        translator = Translator(timeout=20)
        
        # Split text into smaller chunks to avoid API limits and parsing errors
        max_chunk_size = 2000  # Reduced chunk size to avoid parsing issues
        chunks = []
        
        # Split by paragraphs first, then by size if needed
        paragraphs = text.split('\n\n')
        current_chunk = ""
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                if current_chunk:
                    current_chunk += '\n\n'
                continue
                
            # If adding this paragraph would exceed chunk size, save current chunk
            if len(current_chunk) + len(paragraph) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += '\n\n'
                current_chunk += paragraph
        
        # Add the last chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Translate each chunk
        translated_chunks = []
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                translated_chunks.append(chunk)
                continue
                
            try:
                # Attempt translation with retries
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        result = translator.translate(chunk.strip(), dest='zh-tw')
                        if result and hasattr(result, 'text') and result.text:
                            translated_chunks.append(result.text)
                            break
                        else:
                            if attempt == max_retries - 1:
                                logging.warning(f"Translation returned empty result for chunk {i+1}, using original")
                                translated_chunks.append(chunk)
                    except Exception as e:
                        if attempt == max_retries - 1:
                            logging.warning(f"Translation failed for chunk {i+1} after {max_retries} attempts: {e}")
                            translated_chunks.append(chunk)
                        else:
                            time.sleep(1)  # Brief delay before retry
                            
            except Exception as chunk_error:
                logging.error(f"Error translating chunk {i+1}: {chunk_error}")
                translated_chunks.append(chunk)
        
        # Join translated chunks
        result = '\n\n'.join(translated_chunks)
        return clean_and_preserve_formatting(result)
        
    except Exception as e:
        logging.error(f"Error in translation function: {str(e)}")
        # Return original text if translation completely fails
        return text

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
        if not file.filename or not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload PDF, PNG, or JPG files.'}), 400
        
        # Generate unique session ID if not exists
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        # Generate secure filename with better handling for non-English characters
        original_filename = file.filename or 'uploaded_file'
        filename = secure_filename(original_filename)
        
        # If secure_filename removes all characters (e.g., Chinese filenames), create a fallback
        if not filename or filename == '':
            # Extract extension from original filename
            _, ext = os.path.splitext(original_filename)
            if not ext:
                ext = '.txt'  # Default extension
            filename = f'uploaded_file{ext}'
        
        # Create session-specific filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(filename)
        session_filename = f"{session['session_id']}_{name}_{timestamp}{ext}"
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
        
        # Store in session (use original filename for display, but sanitized for processing)
        session['original_text'] = original_text
        session['translated_text'] = translated_text
        session['filename'] = original_filename  # Store original filename for display
        session['filepath'] = filepath
        
        return jsonify({
            'success': True,
            'original_text': original_text,
            'translated_text': translated_text,
            'filename': original_filename  # Return original filename for display
        })
        
    except Exception as e:
        logging.error(f"Error processing file: {str(e)}")
        # Clean up file if it exists
        try:
            if 'filepath' in locals() and 'filepath' in vars():
                if os.path.exists(filepath):
                    os.remove(filepath)
        except (NameError, UnboundLocalError, NameError):
            # If filepath wasn't created, nothing to clean up
            pass
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
        from flask import has_request_context
        if has_request_context() and 'filepath' in session and os.path.exists(session['filepath']):
            os.remove(session['filepath'])
    except Exception as e:
        logging.error(f"Error in cleanup: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
