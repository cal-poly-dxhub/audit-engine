#!/usr/bin/env python3

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def check_environment():
    """Check if all required environment variables are set"""
    # Check for bearer token first (preferred)
    if os.getenv('AWS_BEARER_TOKEN_BEDROCK'):
        # Set default region if not provided
        if not os.getenv('AWS_DEFAULT_REGION'):
            os.environ['AWS_DEFAULT_REGION'] = 'us-west-2'
        print("AWS Bearer Token configured for Bedrock")
        print(f"Using region: {os.getenv('AWS_DEFAULT_REGION')}")
        return True

    # Fallback to standard AWS credentials
    required_vars = [
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_DEFAULT_REGION'
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print("Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nOptions:")
        print("1. Set AWS_BEARER_TOKEN_BEDROCK in your .env file (recommended)")
        print("2. Set standard AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION)")
        return False

    print("AWS credentials configured")
    return True

def main():
    print("Evidence Validation Engine")
    print("=" * 50)
    
    if not check_environment():
        sys.exit(1)
    
    try:
        from evidence_app import app
        print("Starting Evidence Validation Engine...")
        print("Access the application at: http://localhost:5001")
        print("Upload audit PDFs and validate evidence with AI")
        print("\n" + "=" * 50)
        
        app.run(
            host='0.0.0.0',
            port=5001,
            debug=True
        )
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all dependencies are installed:")
        print("pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
