# Student ID Card Scanner

This application allows multiple users to upload student ID card photos simultaneously. It uses Google Cloud Vision API to extract student names and IDs from the photos and saves the data to both CSV and Excel files.

## Features

- Multiple file upload support with drag-and-drop interface
- Concurrent processing of multiple images
- Google Cloud Vision API integration for text extraction
- Automatic saving to both CSV and Excel formats
- Modern, responsive web interface

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up Google Cloud Vision API:
   - Create a Google Cloud Project
   - Enable the Cloud Vision API
   - Create a service account and download the JSON key file
   - Set the environment variable GOOGLE_APPLICATION_CREDENTIALS to point to your key file:
```bash
set GOOGLE_APPLICATION_CREDENTIALS=path/to/your/credentials.json
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and navigate to `http://localhost:5000`

## Usage

1. Drag and drop student ID card photos onto the drop zone, or click to select files
2. Click the "Upload and Process" button
3. Wait for the processing to complete
4. The extracted data will be saved in both CSV and Excel formats in the application directory

## Requirements

- Python 3.7+
- Google Cloud Vision API credentials
- See requirements.txt for all Python dependencies

## Notes

- The application processes images in parallel for better performance
- Uploaded files are temporarily stored and then deleted after processing
- The extraction logic can be customized based on your specific ID card format
