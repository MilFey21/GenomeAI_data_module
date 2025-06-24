from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import os
import json
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
import mimetypes
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('genomeai_frontend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB in bytes
ALLOWED_EXTENSIONS = {
    'csv', 'tsv', 'xlsx', 'vcf', 'fasta', 'fa', 'fastq', 'fq',
    'txt', 'json', 'xml', 'bed', 'gff', 'gtf', 'sam', 'bam'
}
ALLOWED_MIME_TYPES = {
    'text/csv', 'text/tab-separated-values', 'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain', 'application/json', 'application/xml', 'text/xml'
}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Mock user session for demo (replace with real authentication)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            session['user_id'] = 'demo_user'  # Mock user for demo
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    """Check if file extension is allowed"""
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS

def validate_file_type(file):
    """Validate file type using both extension and MIME type"""
    filename = file.filename
    if not allowed_file(filename):
        return False, f"File extension not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check MIME type
    mime_type = file.mimetype
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        # Some files might not have proper MIME types, so we'll be lenient
        logger.warning(f"File {filename} has unexpected MIME type: {mime_type}")
    
    return True, "File type validation passed"

def log_upload_attempt(user_id, filename, status, error_message=None):
    """Log upload attempts for monitoring and debugging"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'filename': filename,
        'status': status,
        'error_message': error_message
    }
    
    if status == 'success':
        logger.info(f"Upload successful: {filename} by user {user_id}")
    else:
        logger.error(f"Upload failed: {filename} by user {user_id} - {error_message}")
    
    # Store in session for upload history
    if 'upload_history' not in session:
        session['upload_history'] = []
    session['upload_history'].append(log_entry)
    
    return log_entry

@app.route('/')
@login_required
def index():
    """Main upload interface"""
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """Handle file upload with comprehensive validation and error handling"""
    try:
        user_id = session.get('user_id')
        
        # Check if file was included in request
        if 'file' not in request.files:
            error_msg = "No file selected for upload"
            log_upload_attempt(user_id, 'unknown', 'failed', error_msg)
            return jsonify({
                'success': False,
                'error': error_msg,
                'error_code': 'NO_FILE'
            }), 400
        
        file = request.files['file']
        
        # Check if filename is empty
        if file.filename == '':
            error_msg = "No file selected for upload"
            log_upload_attempt(user_id, 'empty', 'failed', error_msg)
            return jsonify({
                'success': False,
                'error': error_msg,
                'error_code': 'EMPTY_FILENAME'
            }), 400
        
        # Validate file type
        is_valid, validation_message = validate_file_type(file)
        if not is_valid:
            log_upload_attempt(user_id, file.filename, 'failed', validation_message)
            return jsonify({
                'success': False,
                'error': validation_message,
                'error_code': 'INVALID_FILE_TYPE'
            }), 400
        
        # Check file size (additional check beyond Flask's MAX_CONTENT_LENGTH)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        if file_size > MAX_FILE_SIZE:
            error_msg = f"File too large. Maximum size allowed: {MAX_FILE_SIZE // (1024*1024*1024)} GB"
            log_upload_attempt(user_id, file.filename, 'failed', error_msg)
            return jsonify({
                'success': False,
                'error': error_msg,
                'error_code': 'FILE_TOO_LARGE'
            }), 400
        
        # Secure filename and save
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{user_id}_{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        
        # Save file
        file.save(filepath)
        
        # Log successful upload
        log_entry = log_upload_attempt(user_id, filename, 'success')
        
        # Here you would typically trigger the ML pipeline
        # For now, we'll simulate this with a success response
        
        return jsonify({
            'success': True,
            'message': 'File uploaded successfully',
            'filename': filename,
            'file_size': file_size,
            'upload_id': safe_filename,
            'timestamp': log_entry['timestamp']
        })
        
    except Exception as e:
        error_msg = f"Unexpected error during upload: {str(e)}"
        user_id = session.get('user_id', 'unknown')
        filename = request.files.get('file', {}).get('filename', 'unknown') if 'file' in request.files else 'unknown'
        log_upload_attempt(user_id, filename, 'failed', error_msg)
        logger.exception("Unexpected error in upload_file")
        
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.',
            'error_code': 'INTERNAL_ERROR'
        }), 500

@app.route('/upload_history')
@login_required
def upload_history():
    """Get upload history for the current user"""
    history = session.get('upload_history', [])
    return jsonify({
        'success': True,
        'uploads': history
    })

@app.route('/upload_status/<upload_id>')
@login_required
def upload_status(upload_id):
    """Get status of a specific upload (mock implementation)"""
    # In a real implementation, this would check the ML pipeline status
    # For now, we'll return a mock status
    return jsonify({
        'success': True,
        'upload_id': upload_id,
        'status': 'completed',  # queued, processing, completed, failed
        'progress': 100,
        'message': 'File processed successfully'
    })

@app.route('/supported_formats')
def supported_formats():
    """Return list of supported file formats"""
    return jsonify({
        'success': True,
        'formats': list(ALLOWED_EXTENSIONS),
        'max_file_size_gb': MAX_FILE_SIZE // (1024*1024*1024)
    })

# Error handlers
@app.errorhandler(413)
def too_large(e):
    user_id = session.get('user_id', 'unknown')
    error_msg = f"File too large. Maximum size allowed: {MAX_FILE_SIZE // (1024*1024*1024)} GB"
    log_upload_attempt(user_id, 'large_file', 'failed', error_msg)
    return jsonify({
        'success': False,
        'error': error_msg,
        'error_code': 'FILE_TOO_LARGE'
    }), 413

@app.errorhandler(500)
def internal_error(e):
    logger.exception("Internal server error")
    return jsonify({
        'success': False,
        'error': 'Internal server error. Please try again later.',
        'error_code': 'INTERNAL_ERROR'
    }), 500

if __name__ == '__main__':
    logger.info("Starting GenomeAI Frontend Server")
    app.run(debug=True, host='0.0.0.0', port=5000)
