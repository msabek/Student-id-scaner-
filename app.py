from flask import Flask, request, jsonify, send_from_directory, url_for
import os
from werkzeug.utils import secure_filename
import pandas as pd
from datetime import datetime
from flask_cors import CORS
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

app = Flask(__name__)
CORS(app)

# Configure upload and export folders
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
EXPORT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')

# Create necessary folders
for folder in [UPLOAD_FOLDER, EXPORT_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
        logger.info(f"Created folder: {folder}")

# Ensure folders have write permissions
try:
    for folder in [UPLOAD_FOLDER, EXPORT_FOLDER]:
        test_file = os.path.join(folder, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logger.info(f"{folder} permissions verified")
except Exception as e:
    logger.error(f"Folder permission error: {str(e)}")
    raise

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXPORT_FOLDER'] = EXPORT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def process_image(image_path):
    """Process a single image using Gemini Vision API"""
    try:
        logger.info(f"Processing image: {image_path}")

        # Open and prepare the image
        try:
            image = Image.open(image_path)

            # Convert image to RGB mode if it's not already
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Optionally resize if image is too large
            max_size = 2000
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = tuple(int(dim * ratio) for dim in image.size)
                image = image.resize(new_size, Image.Resampling.LANCZOS)

        except Exception as e:
            error_message = f"Error opening image {image_path}: {str(e)}"
            logger.error(error_message)
            return {'error': error_message}

        # Create prompt for Gemini
        prompt = """
        Extract the following information from this student ID card:
        1. Student Name
        2. Student ID Number

        Format the response as:
        Name: [extracted name]
        ID: [extracted ID number]

        If you can't find either piece of information, indicate with 'Not found'.
        Only include the above fields, no other text.
        """

        # Generate response from Gemini
        try:
            response = model.generate_content([prompt, image])
            logger.info(f"Gemini API Response: {response.text}")

            # Parse the response
            response_lines = response.text.strip().split('\n')
            student_data = {
                'name': None,
                'id': None,
                'raw_text': response.text,
                'processed_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            for line in response_lines:
                if line.startswith('Name:'):
                    student_data['name'] = line.replace('Name:', '').strip()
                elif line.startswith('ID:'):
                    student_data['id'] = line.replace('ID:', '').strip()

            # Check if we found any data
            if student_data['name'] == 'Not found' and student_data['id'] == 'Not found':
                error_message = "Could not find student ID or name in the image"
                logger.warning(error_message)
                return {'error': error_message}

            return student_data

        except Exception as e:
            error_message = f"Error processing with Gemini API: {str(e)}"
            logger.error(error_message)
            return {'error': error_message}

    except Exception as e:
        error_message = f"Error processing image {image_path}: {str(e)}"
        logger.error(error_message, exc_info=True)
        return {'error': error_message}
        
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/download/<filename>')
def download_file(filename):
    """Download a file from the export folder"""
    try:
        return send_from_directory(app.config['EXPORT_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {str(e)}")
        return jsonify({'error': f"Error downloading file: {str(e)}"}), 404

@app.route('/upload', methods=['POST'])
def upload_files():
    try:
        if 'files' not in request.files:
            logger.error("No files provided in request")
            return jsonify({'error': 'No files provided'}), 400

        files = request.files.getlist('files')
        processed_data = []
        errors = []

        for file in files:
            if file.filename == '':
                continue

            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            logger.info(f"Saving file: {filepath}")
            file.save(filepath)

            try:
                # Process the image
                result = process_image(filepath)
                if result and 'error' not in result:
                    processed_data.append(result)
                else:
                    errors.append({
                        'filename': filename,
                        'error': result.get('error', 'Unknown error')
                    })
                    logger.warning(f"Error processing {filename}: {result.get('error', 'Unknown error')}")
            finally:
                # Clean up the uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)

        if not processed_data and errors:
            error_message = "No valid data extracted from images. Errors: " + "; ".join(
                f"{error['filename']}: {error['error']}" for error in errors
            )
            logger.error(error_message)
            return jsonify({
                'error': error_message,
                'details': errors
            }), 400

        # Save to Excel with timestamp
        if processed_data:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create DataFrame
            df = pd.DataFrame(processed_data)

            # Save to Excel with better formatting
            excel_filename = f'student_data_{timestamp}.xlsx'
            excel_path = os.path.join(app.config['EXPORT_FOLDER'], excel_filename)

            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Student Data')

            logger.info(f"Saved data to Excel: {excel_filename}")

            # Generate download URL
            download_url = url_for('download_file', filename=excel_filename, _external=True)

            return jsonify({
                'success': True,
                'processed_files': len(processed_data),
                'data': processed_data,
                'download_url': download_url
            })
        else:
            return jsonify({'error': 'No valid files to process'}), 400

    except Exception as e:
        error_message = f"Error in upload_files: {str(e)}"
        logger.error(error_message, exc_info=True)
        return jsonify({'error': error_message}), 500

if __name__ == '__main__':
    logger.info("Starting application...")
    app.run(host='0.0.0.0', port=8080, debug=True)
