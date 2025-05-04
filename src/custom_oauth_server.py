#!/usr/bin/env python3
"""
Custom OAuth Web Server for X-Scheduler.

This server can handle redirects to /oauth/callback which is what Twitter/X is configured to use.
"""
import os
import logging
import boto3
from dotenv import load_dotenv
from flask import Flask, request, redirect, session, render_template_string
import secrets
import time
from urllib.parse import urlencode
from botocore.exceptions import ClientError
import requests

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("custom_oauth_server")

# Load environment variables
load_dotenv()

# Get OAuth credentials
client_id = os.getenv('X_OAUTH_CLIENT_ID')
client_secret = os.getenv('X_OAUTH_CLIENT_SECRET')
redirect_uri = os.getenv('X_OAUTH_REDIRECT_URI', 'http://localhost:6789/oauth/callback')
scopes = ['tweet.read', 'tweet.write', 'users.read', 'offline.access', 'media.write']

# DynamoDB setup
region_name = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=region_name)
table = dynamodb.Table('XSchedulerUserTokens')

# Twitter OAuth 2.0 endpoints
AUTHORIZE_URL = 'https://twitter.com/i/oauth2/authorize'
TOKEN_URL = 'https://api.twitter.com/2/oauth2/token'

# Store state and code_verifier in memory as a fallback if session fails
fallback_store = {
    'latest_state': None,
    'latest_code_verifier': None
}

# Create Flask app
app = Flask(__name__)
# More secure secret key that's stable across runs
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(16))

def save_token_to_dynamo(user_id, token_data):
    """Save token data to DynamoDB."""
    try:
        # Store token data in DynamoDB
        item = {
            'user_id': user_id,
            'access_token': token_data['access_token'],
            'refresh_token': token_data.get('refresh_token', ''),
            'expires_at': int(token_data.get('expires_in', 7200)) + int(time.time()),
            'token_type': token_data.get('token_type', 'bearer'),
            'scopes': token_data.get('scope', '').split(' ')
        }
        
        table.put_item(Item=item)
        logger.info(f"Token saved to DynamoDB for user {user_id}")
        return True
        
    except ClientError as e:
        logger.error(f"Error saving token to DynamoDB: {str(e)}")
        return False

def create_code_verifier():
    """Create a code verifier for PKCE."""
    code_verifier = secrets.token_urlsafe(64)
    return code_verifier[:128]  # Ensure it's at most 128 characters

def create_code_challenge(code_verifier):
    """Create a code challenge from the code verifier."""
    import hashlib
    import base64
    code_challenge = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(code_challenge).decode().rstrip('=')

def get_authorization_url():
    """Get the authorization URL for Twitter OAuth 2.0."""
    # Create code verifier and challenge
    code_verifier = create_code_verifier()
    code_challenge = create_code_challenge(code_verifier)
    
    # Generate random state
    state = secrets.token_urlsafe(32)
    
    # Build authorization URL
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': ' '.join(scopes),
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256'
    }
    
    authorization_url = f"{AUTHORIZE_URL}?{urlencode(params)}"
    
    # Store in memory as fallback
    fallback_store['latest_state'] = state
    fallback_store['latest_code_verifier'] = code_verifier
    
    return authorization_url, state, code_verifier

def fetch_token(code, code_verifier):
    """Exchange authorization code for access and refresh tokens."""
    token_data = {
        'client_id': client_id,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'code_verifier': code_verifier
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    # Add client secret if provided
    auth = (client_id, client_secret) if client_secret else None
    
    logger.info("Exchanging authorization code for tokens")
    response = requests.post(
        TOKEN_URL,
        data=token_data,
        headers=headers,
        auth=auth
    )
    
    if response.status_code != 200:
        logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
        response.raise_for_status()
        
    token_response = response.json()
    logger.info("Token exchange successful")
    
    return token_response

@app.route('/')
def index():
    """Home page with login link."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>X-Scheduler Authorization</title>
        <style>
            body { font-family: sans-serif; line-height: 1.6; padding: 2em; }
            a.button { display: inline-block; background-color: #1DA1F2; color: white;
                       padding: 10px 20px; text-decoration: none; border-radius: 5px; }
            .error { color: red; border: 1px solid red; padding: 1em; margin-top: 1em; }
        </style>
    </head>
    <body>
        <h1>X-Scheduler OAuth Authorization</h1>
        <p>Click the button below to authorize the X-Scheduler application to interact with your X/Twitter account.</p>
        <a href="/login" class="button">Authorize with X/Twitter</a>
        <p style="margin-top: 20px;">
            <a href="/manual_entry">Having trouble? Click here for manual entry</a>
        </p>
    </body>
    </html>
    """

@app.route('/login')
def login():
    """Initiate OAuth flow."""
    try:
        authorization_url, state, code_verifier = get_authorization_url()
        session['oauth_state'] = state
        session['code_verifier'] = code_verifier
        logger.info(f"Redirecting user to Twitter authorization URL. State: {state}")
        return redirect(authorization_url)
    except Exception as e:
         logger.error(f"Error generating authorization URL: {e}", exc_info=True)
         return """
         <h1>Error</h1>
         <p>Could not initiate the authorization process. Please check the application logs.</p>
         """, 500

@app.route('/manual_entry', methods=['GET', 'POST'])
def manual_entry():
    """Allow manual entry of code and state for cases where redirect doesn't work properly."""
    if request.method == 'POST':
        code = request.form.get('code')
        state = request.form.get('state')
        
        if not code:
            return """
            <h1>Error</h1>
            <p>Code is required.</p>
            <p><a href="/manual_entry">Try again</a></p>
            """, 400
            
        # Use fallback storage for code verifier
        code_verifier = fallback_store.get('latest_code_verifier')
        
        if not code_verifier:
            return """
            <h1>Error</h1>
            <p>Session data not found. Please start the authorization process again.</p>
            <p><a href="/">Go to home page</a></p>
            """, 400
            
        try:
            # Exchange code for token
            token_data = fetch_token(code, code_verifier)
            if not token_data or 'access_token' not in token_data:
                return """
                <h1>Authorization Failed</h1>
                <p>Failed to obtain valid tokens from Twitter.</p>
                """, 500
                
            # Save token to DynamoDB
            user_id = "default_user"
            if save_token_to_dynamo(user_id, token_data):
                return """
                <!DOCTYPE html>
                <html lang="en">
                <head><meta charset="UTF-8"><title>Authorization Successful</title></head>
                <body>
                    <h1>Authorization Successful!</h1>
                    <p>Your X/Twitter account has been successfully linked to the application.</p>
                    <p>You can now close this window and continue with video uploads.</p>
                </body>
                </html>
                """
            else:
                return """
                <h1>Authorization Failed</h1>
                <p>Your authorization was successful with Twitter, but we failed to save the credentials securely.</p>
                """, 500
                
        except Exception as e:
            logger.error(f"Error during manual token exchange: {e}", exc_info=True)
            return f"""
            <h1>Error</h1>
            <p>An error occurred: {str(e)}</p>
            <p><a href="/manual_entry">Try again</a></p>
            """, 500
    
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Manual OAuth Entry</title>
        <style>
            body { font-family: sans-serif; line-height: 1.6; padding: 2em; }
            form { margin-top: 2em; }
            input[type="text"] { width: 100%; padding: 8px; margin-bottom: 1em; }
            button { background-color: #1DA1F2; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>Manual OAuth Entry</h1>
        <p>Paste the callback URL or just the code and state parameters:</p>
        
        <form method="post">
            <div>
                <label for="code">Authorization Code:</label>
                <input type="text" id="code" name="code" placeholder="Paste the 'code' parameter from the URL">
            </div>
            <div>
                <label for="state">State (optional):</label>
                <input type="text" id="state" name="state" placeholder="Paste the 'state' parameter from the URL">
            </div>
            <button type="submit">Submit</button>
        </form>
        
        <p>How to find these values:</p>
        <ol>
            <li>When Twitter redirects you, you'll see a URL like: <code>http://localhost:6789/oauth/callback?state=abc123&code=xyz789</code></li>
            <li>Copy the value after <code>code=</code> into the Authorization Code field</li>
            <li>Optionally, copy the value after <code>state=</code> into the State field</li>
        </ol>
    </body>
    </html>
    """

@app.route('/oauth/callback')
def callback():
    """Handle OAuth callback."""
    logger.info(f"Received callback request. Args: {request.args}")

    # Check for errors
    if 'error' in request.args:
        error_code = request.args.get('error')
        error_desc = request.args.get('error_description', 'No description provided.')
        logger.warning(f"Authorization denied or callback error from Twitter: {error_code} - {error_desc}")
        error_message = f"Authorization failed: Twitter reported an error ({error_code})."
        if error_code == 'access_denied':
            error_message = "Authorization denied: You cancelled the authorization process on Twitter."
        return f"""
         <h1>Authorization Failed</h1>
         <p>{error_message}</p>
         <p>Please try <a href="/login">authorizing again</a> if this was unintended.</p>
         <p>If you keep having issues, try <a href="/manual_entry">manual entry</a>.</p>
         """, 400

    # Get state and code from request
    state_received = request.args.get('state')
    code = request.args.get('code')
    
    # First try to get values from session
    state_expected = session.get('oauth_state')
    code_verifier = session.get('code_verifier')
    
    # If session doesn't have values, try fallback store
    if not state_expected or not code_verifier:
        logger.warning("Session data not found, trying fallback store")
        state_expected = fallback_store.get('latest_state')
        code_verifier = fallback_store.get('latest_code_verifier')
    
    # Check state (skip if using fallback store as we can't guarantee state match)
    if state_expected and state_received != state_expected:
        logger.error(f"State verification failed. Received: {state_received}, Expected: {state_expected}")
        return """
        <h1>Authorization Failed</h1>
        <p>Invalid state parameter. This could indicate a security issue (CSRF).</p>
        <p>Please try <a href="/login">authorizing again</a> or use <a href="/manual_entry">manual entry</a> if the issue persists.</p>
        """, 403

    # Verify we have required parameters
    if not code or not code_verifier:
         logger.error("Missing 'code' or 'code_verifier' in callback or session/fallback.")
         return """
         <h1>Authorization Failed</h1>
         <p>Could not complete authorization: Missing required parameters.</p>
         <p>Try <a href="/manual_entry">manual entry</a> instead.</p>
         """, 400

    try:
        logger.info("Attempting to fetch token using authorization code.")
        token_data = fetch_token(code, code_verifier)
        if not token_data or 'access_token' not in token_data:
             logger.error("Token exchange returned invalid data.")
             return """
             <h1>Authorization Failed</h1>
             <p>Failed to obtain valid tokens from Twitter.</p>
             <p>Try <a href="/manual_entry">manual entry</a> instead.</p>
             """, 500

    except Exception as e:
         logger.error(f"Error during token exchange: {e}", exc_info=True)
         return """
         <h1>Authorization Failed</h1>
         <p>An error occurred during the token exchange process.</p>
         <p>Try <a href="/manual_entry">manual entry</a> instead.</p>
         """, 500

    # Save token to DynamoDB
    user_id = "default_user"
    logger.info(f"Attempting to save token for user: {user_id}")

    try:
        if save_token_to_dynamo(user_id, token_data):
            logger.info(f"Successfully authorized and saved token for user {user_id}")
            # Clear session variables after successful use
            session.pop('oauth_state', None)
            session.pop('code_verifier', None)
            fallback_store['latest_state'] = None
            fallback_store['latest_code_verifier'] = None
            return """
            <!DOCTYPE html>
            <html lang="en">
            <head><meta charset="UTF-8"><title>Authorization Successful</title></head>
            <body>
                <h1>Authorization Successful!</h1>
                <p>Your X/Twitter account has been successfully linked to the application.</p>
                <p>You can now close this window and continue with video uploads.</p>
            </body>
            </html>
            """
        else:
             logger.error(f"Failed to save token to DynamoDB for user {user_id}.")
             return """
             <h1>Authorization Failed</h1>
             <p>Your authorization was successful with Twitter, but we failed to save the credentials securely.</p>
             <p>Please contact support or check application logs.</p>
             """, 500
    except Exception as e:
        logger.error(f"Unexpected error after token exchange: {e}", exc_info=True)
        return """
         <h1>Authorization Failed</h1>
         <p>An unexpected error occurred after obtaining the token. Could not save credentials.</p>
         """, 500

if __name__ == "__main__":
    port = 6789
    host = "0.0.0.0"
    debug = True
    
    print(f"Starting custom OAuth web server on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug) 