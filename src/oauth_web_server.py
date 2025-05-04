#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv

# Import the Flask app from oauth.py
# Assuming the Flask app instance is named 'app' in oauth.py
try:
    from oauth import app
except ImportError:
    print("Error: Could not import 'app' from oauth.py. Make sure it exists and exports a Flask app instance.")
    sys.exit(1)

if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()
    
    # Get port from environment variable or use default (5000)
    port = int(os.environ.get("FLASK_PORT", 5000))
    
    # Get host from environment variable or use 0.0.0.0 to make it accessible externally
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    
    # Get debug mode from environment variable (default to False for production)
    debug = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    
    print(f"Starting OAuth web server on {host}:{port} (debug={debug})")
    
    # Run the Flask app
    app.run(host=host, port=port, debug=debug) 