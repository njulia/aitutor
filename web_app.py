#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Homework Magic - Complete Web Application

A modern, SEO-friendly Flask web application that replaces Gradio,
but retains all existing homework generation and review logic.
"""

import os
import sys
import logging
import base64
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from src.file_utils import read_text_file, read_pdf_file, extract_text_from_image

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, 
            static_folder='static', 
            template_folder='templates')
CORS(app)

# File upload configuration
UPLOAD_FOLDER = os.path.join(project_root, 'uploads')
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'heic', 'gif'}
ALLOWED_TEXT_EXTENSIONS = {'txt', 'md', 'csv'}
ALLOWED_PDF_EXTENSION = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize LLM and components
llm = None
initialized = False


def initialize():
    """Initialize all components"""
    global llm, initialized
    if initialized:
        return
    
    from src.agent_workflow import init_llm
    llm, _, _ = init_llm()
    initialized = True
    logger.info("✓ Web application initialized")


def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def process_uploaded_file(file):
    """Process uploaded file and extract text/content"""
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    file_ext = os.path.splitext(filename)[1].lower().lstrip('.')
    
    content = ""
    is_image = False
    
    if file_ext in ALLOWED_IMAGE_EXTENSIONS:
        logger.info(f"[File Upload] Processing image: {filename}")
        content = extract_text_from_image(filepath)
        is_image = True
    elif file_ext in ALLOWED_TEXT_EXTENSIONS:
        logger.info(f"[File Upload] Processing text file: {filename}")
        content = read_text_file(filepath)
    elif file_ext in ALLOWED_PDF_EXTENSION:
        logger.info(f"[File Upload] Processing PDF: {filename}")
        content = read_pdf_file(filepath)
    else:
        raise ValueError(f"Unsupported file type: {file_ext}")
    
    # Clean up the file
    try:
        os.remove(filepath)
    except:
        pass
    
    return content, is_image


def process_base64_image(data_url):
    """Process base64 encoded image from camera"""
    from src.file_utils import extract_text_from_image
    import tempfile
    
    # Remove data URL prefix
    if 'base64,' in data_url:
        data_url = data_url.split('base64,')[1]
    
    # Decode base64
    image_data = base64.b64decode(data_url)
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        tmp.write(image_data)
        tmp_path = tmp.name
    
    try:
        content = extract_text_from_image(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass
    
    return content


# Import core logic
def generate_homework_with_profile(profile, subjects):
    """Generate homework using existing logic"""
    from src.homework_generator import generate_homework_for_subject
    from src.homework_manager import process_homework_with_review
    
    # Ensure student_id exists in profile
    if 'student_id' not in profile or not profile['student_id']:
        profile['student_id'] = 'student_' + str(profile.get('year_group', 3)) + '_default'
    
    results = []
    
    for subject in subjects:
        try:
            homework_content, doc_id = generate_homework_for_subject(profile, subject, llm)
            results.append({
                'subject': subject,
                'content': homework_content,
                'doc_id': doc_id
            })
            logger.info(f"✓ Generated NEW homework for {subject} for student {profile['student_id']}")
        except Exception as e:
            logger.error(f"✗ Error generating {subject}: {e}")
            results.append({
                'subject': subject,
                'content': f"Error generating homework: {str(e)}",
                'doc_id': None
            })
    
    return results


def review_homework(homework_content, student_answers, subject, profile=None):
    """Review homework using existing logic"""
    from src.homework_manager import review_uploaded_homework
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from src.prompts import REVIEW_HOMEWORK_PROMPT
    from datetime import datetime
    
    if profile is None:
        profile = {
            'year_group': 3,
            'age': 7
        }
    
    try:
        prompt = ChatPromptTemplate.from_template(REVIEW_HOMEWORK_PROMPT)
        chain = prompt | llm | StrOutputParser()
        
        # Format the day properly
        current_day = datetime.now().strftime("%A, %B %d, %Y")
        
        result = chain.invoke({
            'day': current_day,
            'homework_content': homework_content,
            'student_answer': student_answers,  # Use singular as in prompt
            'subject': subject,
            'student_profile': str(profile)
        })
        
        return {
            'success': True,
            'review': result
        }
    except Exception as e:
        logger.error(f"✗ Error reviewing homework: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# --- Web Routes ---

@app.route('/')
def index():
    """Homepage"""
    return send_from_directory('static', 'index.html')


@app.route('/ks1-homework')
def ks1_homework():
    """KS1 landing page"""
    return send_from_directory('static', 'ks1-homework.html')


@app.route('/ks2-homework')
def ks2_homework():
    """KS2 landing page"""
    return send_from_directory('static', 'ks2-homework.html')


@app.route('/11-plus-practice')
def eleven_plus():
    """11+ landing page"""
    return send_from_directory('static', '11-plus-practice.html')


@app.route('/check-my-homework')
def check_homework():
    """Homework checking page"""
    return send_from_directory('static', 'check-my-homework.html')


@app.route('/app')
def app_page():
    """Main application page"""
    return render_template('app.html')


# --- API Endpoints ---

@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    """Get list of available subjects"""
    from src.models import UK_PRIMARY_SUBJECTS, ELEVEN_PLUS_SUBJECTS
    
    return jsonify({
        'primary': UK_PRIMARY_SUBJECTS,
        'eleven_plus': ELEVEN_PLUS_SUBJECTS
    })


@app.route('/api/year-groups', methods=['GET'])
def get_year_groups():
    """Get year group options"""
    return jsonify({
        'year_groups': [1, 2, 3, 4, 5, 6],
        'quick_select': [
            {'year': 1, 'age': 5, 'stage': 'KS1'},
            {'year': 2, 'age': 6, 'stage': 'KS1'},
            {'year': 3, 'age': 7, 'stage': 'KS2'},
            {'year': 4, 'age': 8, 'stage': 'KS2'},
            {'year': 5, 'age': 9, 'stage': 'KS2'},
            {'year': 6, 'age': 10, 'stage': 'KS2'}
        ]
    })


@app.route('/api/generate', methods=['POST'])
def api_generate():
    """Generate homework via API"""
    try:
        data = request.json
        
        # Initialize if needed
        initialize()
        
        # Parse profile
        profile = data.get('profile', {})
        subjects = data.get('subjects', [])
        
        # Handle quick select mode
        if data.get('quick_select'):
            year = data.get('year')
            profile = {
                'year_group': year,
                'age': 5 + (year - 1),
                'student_id': f'student_{year}'
            }
        
        # Generate homework
        results = generate_homework_with_profile(profile, subjects)
        
        return jsonify({
            'success': True,
            'homework': results,
            'profile': profile
        })
        
    except Exception as e:
        logger.error(f"Error generating homework: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/review', methods=['POST'])
def api_review():
    """Review homework via API"""
    try:
        data = request.json
        
        # Initialize if needed
        initialize()
        
        homework_content = data.get('homework', '')
        student_answers = data.get('answers', '')
        subject = data.get('subject', 'Maths')
        profile = data.get('profile', None)
        
        result = review_homework(homework_content, student_answers, subject, profile)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error reviewing homework: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/quick-profile/<int:year>', methods=['GET'])
def get_quick_profile(year):
    """Get a quick student profile for a given year"""
    from src.models import SAMPLE_STUDENT_PROFILES
    
    student_id = f'student_{year}'
    profile = SAMPLE_STUDENT_PROFILES.get(student_id, {
        'year_group': year,
        'age': 5 + (year - 1),
        'student_id': student_id
    })
    
    return jsonify({
        'success': True,
        'profile': profile
    })


@app.route('/api/upload-file', methods=['POST'])
def upload_file():
    """Upload and process file for homework review"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Initialize if needed
        initialize()
        
        allowed_all = ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_TEXT_EXTENSIONS).union(ALLOWED_PDF_EXTENSION)
        
        if file and allowed_file(file.filename, allowed_all):
            content, is_image = process_uploaded_file(file)
            
            return jsonify({
                'success': True,
                'content': content,
                'is_image': is_image
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Unsupported file type. Please upload .jpg, .jpeg, .png, .heic, .gif, .txt, .md, .csv, or .pdf files.'
            }), 400
            
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/upload-photo', methods=['POST'])
def upload_photo():
    """Upload and process base64 encoded photo from camera"""
    try:
        data = request.json
        photo_data = data.get('photo', '')
        
        if not photo_data:
            return jsonify({'success': False, 'error': 'No photo data'}), 400
        
        # Initialize if needed
        initialize()
        
        content = process_base64_image(photo_data)
        
        return jsonify({
            'success': True,
            'content': content
        })
        
    except Exception as e:
        logger.error(f"Error uploading photo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)


def main():
    """Main entry point"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                    Homework Magic                             ║
║             AI Tutor for UK Primary Schools                   ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize
    initialize()
    
    # Start server
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print(f"""
🚀 Starting server...
📱 Homepage:         http://localhost:{port}
✨ Main App:         http://localhost:{port}/app

Available pages:
  • http://localhost:{port}/
  • http://localhost:{port}/ks1-homework
  • http://localhost:{port}/ks2-homework
  • http://localhost:{port}/11-plus-practice
  • http://localhost:{port}/check-my-homework

Press Ctrl+C to stop
    """)
    
    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == '__main__':
    main()
