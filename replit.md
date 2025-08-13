# OCR & Translation Tool

## Overview

This is a web-based OCR (Optical Character Recognition) and translation application built with Flask. The tool allows users to upload images or PDF files, extract text using Tesseract OCR, and translate the extracted text using Google Translate. The application supports multiple languages including English, Simplified Chinese, and Traditional Chinese for OCR processing.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes

### Session Management Enhancement (August 13, 2025)
- Added prominent user reminder to clear session for uploading additional files
- Enhanced footer with tip about session clearing functionality
- Improved translation error handling to prevent worker crashes from Google Translate timeouts
- Added warning about using English/numeric characters only in file names for optimal performance

## System Architecture

### Frontend Architecture
- **Technology**: Vanilla JavaScript with Bootstrap for UI components
- **Design Pattern**: Single-page application with dynamic content updates
- **User Interface**: Dark-themed Bootstrap interface with drag-and-drop file upload
- **File Handling**: Client-side file validation and drag-and-drop functionality
- **Supported Formats**: PDF, PNG, JPG, JPEG files up to 16MB

### Backend Architecture
- **Framework**: Flask web framework with Python
- **Architecture Pattern**: Traditional server-side rendering with JSON API endpoints
- **File Processing**: Server-side file upload handling with secure filename generation
- **OCR Engine**: Tesseract OCR integration for text extraction from images and PDFs
- **Translation Service**: Google Translate API integration for text translation
- **Session Management**: Flask sessions for temporary data storage
- **Error Handling**: Comprehensive logging and error response system

### Text Processing Pipeline
- **Image Processing**: PIL (Python Imaging Library) for image preprocessing and format conversion
- **PDF Processing**: PyPDF2 for text extraction from PDF documents
- **OCR Processing**: Tesseract with multi-language support (English, Simplified Chinese, Traditional Chinese)
- **Translation**: Google Translate API for automatic language detection and translation

### File Management
- **Upload Directory**: Local filesystem storage in 'uploads' folder
- **File Security**: Secure filename generation and file type validation
- **Temporary Files**: Automatic cleanup of uploaded files after processing
- **Size Limits**: 16MB maximum file size restriction

## External Dependencies

### Core Libraries
- **Flask**: Web framework for application structure and routing
- **Werkzeug**: WSGI utilities for secure file handling
- **PIL (Pillow)**: Image processing and format conversion
- **PyPDF2**: PDF text extraction capabilities
- **pytesseract**: Python wrapper for Tesseract OCR engine

### External Services
- **Google Translate API**: Text translation service via googletrans library
- **Tesseract OCR**: External OCR engine for text extraction from images

### Frontend Dependencies
- **Bootstrap**: UI framework loaded via CDN for responsive design
- **Font Awesome**: Icon library for user interface elements
- **Custom CSS/JS**: Application-specific styling and functionality

### Development Dependencies
- **Python 3.x**: Runtime environment
- **Tesseract OCR**: System-level OCR engine installation required