#!/usr/bin/env python3

import os
import sys

if __name__ == '__main__':
    # Set environment variables
    os.environ['FLASK_APP'] = 'app.py'
    os.environ['FLASK_ENV'] = 'development'
    
    # Import and run the Flask app
    from app import app
    
    print("Starting Cal Poly AuditEngine...")
    print("Access the application at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
