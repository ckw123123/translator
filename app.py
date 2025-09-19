import os
import logging
from flask import Flask, render_template, request, session, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from PIL import Image
import PyPDF2
import uuid
from datetime import datetime
import requests
from googletrans import Translator

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Use OCR.space API (default key: "helloworld" but you should set env var OCR_SPACE_API_KEY)
OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY", "helloworld")

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "your-secret-key-here")

# Configuration
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

translator = Translator()


def allowed_file(filename):
    return "." in filename and filename.rsplit(
        ".", 1)[1].lower() in ALLOWED_EXTENSIONS


def clean_and_preserve_formatting(text: str) -> str:
    if not text:
        return ""
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def extract_text_from_image(image_path: str) -> str:
    """Extract text using OCR.space only"""
    try:
        with open(image_path, "rb") as f:
            r = requests.post(
                "https://api.ocr.space/parse/image",
                files={"file": f},
                data={
                    "apikey": OCR_SPACE_API_KEY,
                    "language":
                    "eng",  # Only English input → will be translated later
                },
                timeout=60,
            )
        result = r.json()
        logging.debug(f"OCR.space response: {result}")

        if "ParsedResults" in result and result["ParsedResults"]:
            return clean_and_preserve_formatting(
                result["ParsedResults"][0].get("ParsedText", ""))

        return ""
    except Exception as e:
        logging.error(f"OCR.space failed: {e}")
        return ""


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using PyPDF2 and OCR.space if needed"""
    text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
    except Exception as e:
        logging.warning(f"PDF text extraction failed: {e}")

    # If no text, fallback to OCR.space on each page (as images)
    if len(text.strip()) < 20:
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(pdf_path)
            for img in images:
                with requests.Session() as s:
                    temp_file = os.path.join(UPLOAD_FOLDER,
                                             f"page_{uuid.uuid4().hex}.png")
                    img.save(temp_file, "PNG")
                    text += extract_text_from_image(temp_file) + "\n\n"
                    os.remove(temp_file)
        except Exception as e:
            logging.error(f"OCR.space PDF fallback failed: {e}")

    return clean_and_preserve_formatting(text)


def translate_to_traditional_chinese(text: str) -> str:
    """Translate English text to Traditional Chinese"""
    if not text.strip():
        return ""
    try:
        result = translator.translate(text, src="en", dest="zh-tw")
        return clean_and_preserve_formatting(result.text)
    except Exception as e:
        logging.error(f"Translation failed: {e}")
        return f"翻譯出現錯誤，以下為原始文本：\n\n{text}"


@app.route("/")
def index():
    session.clear()
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file selected"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type"}), 400

        if "session_id" not in session:
            session["session_id"] = str(uuid.uuid4())

        filename = secure_filename(file.filename)
        if not filename:
            filename = "uploaded_file.pdf"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        ext = filename.rsplit(".", 1)[1].lower()
        if ext == "pdf":
            original_text = extract_text_from_pdf(filepath)
        else:
            original_text = extract_text_from_image(filepath)

        if not original_text.strip():
            os.remove(filepath)
            return jsonify({"error": "No text could be extracted"}), 400

        translated_text = translate_to_traditional_chinese(original_text)

        session["original_text"] = original_text
        session["translated_text"] = translated_text
        session["filename"] = filename
        session["filepath"] = filepath

        return jsonify({
            "success": True,
            "original_text": original_text,
            "translated_text": translated_text,
            "filename": filename,
        })
    except Exception as e:
        logging.error(f"Upload error: {e}")
        return jsonify({"error": f"Server error: {e}"}), 500


@app.route("/clear")
def clear_session():
    try:
        if "filepath" in session and os.path.exists(session["filepath"]):
            os.remove(session["filepath"])
        session.clear()
    except Exception as e:
        logging.warning(f"Clear session error: {e}")
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
