// OCR & Translation Tool JavaScript

let selectedFile = null;

// DOM elements - will be initialized when DOM is ready
let dropZone, fileInput, fileInfo, fileName, uploadBtn, loading, results, errorAlert, errorMessage, originalText, translatedText;

// Initialize drag and drop functionality
function initializeDragAndDrop() {
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    // Highlight drop zone when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', handleDrop, false);
    
    // Handle click to select file
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });
    
    // Handle choose file button click
    const chooseFileBtn = document.getElementById('choose-file-btn');
    if (chooseFileBtn) {
        chooseFileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.click();
        });
    }
    
    // Handle file input change
    fileInput.addEventListener('change', handleFileSelect);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function highlight(e) {
    dropZone.classList.add('dragover');
}

function unhighlight(e) {
    dropZone.classList.remove('dragover');
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFileSelect(e) {
    console.log('File selected:', e.target.files);
    const files = e.target.files;
    if (files.length > 0) {
        console.log('Processing file:', files[0].name, 'Type:', files[0].type);
        handleFile(files[0]);
    } else {
        console.log('No files selected');
    }
}

function handleFile(file) {
    // Validate file type - check both MIME type and file extension
    const allowedTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg'];
    const fileName = file.name.toLowerCase();
    const hasValidExtension = fileName.endsWith('.pdf') || fileName.endsWith('.png') || 
                             fileName.endsWith('.jpg') || fileName.endsWith('.jpeg');
    
    if (!allowedTypes.includes(file.type) && !hasValidExtension) {
        showError('Invalid file type. Please upload PDF, PNG, or JPG files.');
        console.log('File type:', file.type, 'File name:', file.name);
        return;
    }
    
    // Validate file size (16MB)
    const maxSize = 16 * 1024 * 1024;
    if (file.size > maxSize) {
        showError('File size exceeds 16MB limit. Please choose a smaller file.');
        return;
    }
    
    selectedFile = file;
    console.log('Setting file name:', file.name);
    console.log('fileName element:', fileName);
    
    if (fileName) {
        fileName.textContent = file.name;
        console.log('File name set to:', fileName.textContent);
    } else {
        console.error('fileName element not found!');
    }
    
    if (fileInfo) {
        fileInfo.classList.remove('d-none');
    } else {
        console.error('fileInfo element not found!');
    }
    
    if (uploadBtn) {
        uploadBtn.disabled = false;
    }
    
    hideError();
    console.log('File selected successfully:', file.name, file.size, 'bytes');
}

function clearFile() {
    selectedFile = null;
    if (fileInput) fileInput.value = '';
    if (fileInfo) fileInfo.classList.add('d-none');
    if (uploadBtn) uploadBtn.disabled = true;
    hideError();
    console.log('File cleared');
}

function uploadFile() {
    if (!selectedFile) {
        showError('Please select a file first.');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    // Show loading state
    loading.classList.remove('d-none');
    uploadBtn.disabled = true;
    hideError();
    hideResults();
    
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        loading.classList.add('d-none');
        
        if (data.error) {
            showError(data.error);
            uploadBtn.disabled = false;
        } else {
            // Display results
            originalText.textContent = data.original_text;
            translatedText.textContent = data.translated_text;
            results.classList.remove('d-none');
            
            // Scroll to results
            results.scrollIntoView({ behavior: 'smooth' });
        }
    })
    .catch(error => {
        loading.classList.add('d-none');
        uploadBtn.disabled = false;
        showError('An error occurred while processing the file. Please try again.');
        console.error('Error:', error);
    });
}

function copyText(elementId) {
    const element = document.getElementById(elementId);
    const text = element.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        // Show temporary success message
        const button = element.parentElement.querySelector('button');
        const originalIcon = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check"></i>';
        button.classList.remove('btn-outline-secondary');
        button.classList.add('btn-success');
        
        setTimeout(() => {
            button.innerHTML = originalIcon;
            button.classList.remove('btn-success');
            button.classList.add('btn-outline-secondary');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy text: ', err);
        showError('Failed to copy text to clipboard.');
    });
}

function clearSession() {
    if (confirm('Are you sure you want to clear all data? This action cannot be undone.')) {
        window.location.href = '/clear';
    }
}

function showError(message) {
    errorMessage.textContent = message;
    errorAlert.classList.remove('d-none');
    errorAlert.scrollIntoView({ behavior: 'smooth' });
}

function hideError() {
    errorAlert.classList.add('d-none');
}

function hideResults() {
    results.classList.add('d-none');
}

// Initialize DOM elements
function initializeElements() {
    dropZone = document.getElementById('drop-zone');
    fileInput = document.getElementById('file-input');
    fileInfo = document.getElementById('file-info');
    fileName = document.getElementById('file-name');
    uploadBtn = document.getElementById('upload-btn');
    loading = document.getElementById('loading');
    results = document.getElementById('results');
    errorAlert = document.getElementById('error-alert');
    errorMessage = document.getElementById('error-message');
    originalText = document.getElementById('original-text');
    translatedText = document.getElementById('translated-text');
}

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing app...');
    
    // Initialize DOM elements
    initializeElements();
    
    // Check if all elements are found
    console.log('Drop zone:', dropZone);
    console.log('File input:', fileInput);
    console.log('Upload button:', uploadBtn);
    
    if (!dropZone || !fileInput || !uploadBtn) {
        console.error('Required DOM elements not found!');
        showError('Failed to initialize application. Please refresh the page.');
        return;
    }
    
    initializeDragAndDrop();
    
    // Auto-hide alerts after 10 seconds
    setTimeout(() => {
        hideError();
    }, 10000);
    
    console.log('App initialized successfully');
});

// Handle page visibility change to warn about session data
document.addEventListener('visibilitychange', function() {
    if (document.hidden && selectedFile) {
        // Page is being hidden, data will be lost on refresh
        console.log('Page hidden - session data will be cleared on refresh');
    }
});

// Warn user before leaving if there's processed data
window.addEventListener('beforeunload', function(e) {
    const hasResults = !results.classList.contains('d-none');
    if (hasResults) {
        e.preventDefault();
        e.returnValue = 'You have processed text that will be lost. Are you sure you want to leave?';
        return e.returnValue;
    }
});
