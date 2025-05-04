"""
OAuth 2.0 PKCE Authentication Module for Twitter API.

This module implements the OAuth 2.0 PKCE (Proof Key for Code Exchange) authentication flow
for the Twitter API using Flask for the web component and DynamoDB for token storage.
"""
import os
import base64
import hashlib
import secrets
import logging
import json
import time
from urllib.parse import urlencode
from flask import Flask, request, redirect, session, url_for
import boto3
from botocore.exceptions import ClientError
import requests
from requests_oauthlib import OAuth2Session


class TwitterOAuth:
    """
    Handles OAuth 2.0 PKCE authentication flow for Twitter API.
    """
    
    # Twitter OAuth 2.0 endpoints
    AUTHORIZE_URL = 'https://twitter.com/i/oauth2/authorize'
    TOKEN_URL = 'https://api.twitter.com/2/oauth2/token'
    
    def __init__(self, client_id, redirect_uri, scopes, dynamo_table_name='XSchedulerUserTokens', logger=None):
        """
        Initialize the OAuth handler.
        
        Args:
            client_id (str): Twitter OAuth 2.0 client ID
            redirect_uri (str): URI to redirect to after authorization
            scopes (list): List of OAuth scopes to request
            dynamo_table_name (str): DynamoDB table name for token storage
            logger: Logger to use for logging
        """
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        
        # Update scopes to potentially include media permissions
        if isinstance(scopes, list):
            if 'media.write' not in scopes:
                scopes.append('media.write')
            if 'media.read' not in scopes:
                scopes.append('media.read')
        else:
            scopes = ['tweet.read', 'tweet.write', 'users.read', 'offline.access', 'media.write', 'media.read']
        
        self.logger = logger or logging.getLogger(__name__)
        self.logger.debug(f"Initializing OAuth with scopes: {scopes}")
        self.scopes = scopes
        
        self.dynamo_table_name = dynamo_table_name
        
        # Initialize DynamoDB with region_name
        region_name = os.environ.get('AWS_REGION', 'us-east-1')
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.table = self.dynamodb.Table(dynamo_table_name)
        
        # Create Flask app if it's needed for the web component
        self.app = None
    
    def _create_code_verifier(self):
        """
        Create a code verifier for PKCE.
        
        Returns:
            str: A random code verifier string
        """
        code_verifier = secrets.token_urlsafe(64)
        return code_verifier[:128]  # Ensure it's at most 128 characters
    
    def _create_code_challenge(self, code_verifier):
        """
        Create a code challenge from the code verifier using SHA-256.
        
        Args:
            code_verifier (str): The code verifier
            
        Returns:
            str: Code challenge for PKCE
        """
        code_challenge = hashlib.sha256(code_verifier.encode()).digest()
        return base64.urlsafe_b64encode(code_challenge).decode().rstrip('=')
    
    def get_authorization_url(self, state=None):
        """
        Get the authorization URL for Twitter OAuth 2.0.
        
        Args:
            state (str, optional): State parameter for CSRF protection
            
        Returns:
            tuple: (authorization_url, state, code_verifier)
        """
        # Create code verifier and challenge
        code_verifier = self._create_code_verifier()
        code_challenge = self._create_code_challenge(code_verifier)
        
        # Generate random state if not provided
        if state is None:
            state = secrets.token_urlsafe(32)
        
        # Build authorization URL
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(self.scopes),
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        
        authorization_url = f"{self.AUTHORIZE_URL}?{urlencode(params)}"
        
        return authorization_url, state, code_verifier
    
    def fetch_token(self, code, code_verifier, client_secret=None):
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            code (str): Authorization code from callback
            code_verifier (str): Code verifier used in authorization request
            client_secret (str, optional): Client secret (if applicable)
            
        Returns:
            dict: Token response containing access_token, refresh_token, etc.
        """
        token_data = {
            'client_id': self.client_id,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri,
            'code_verifier': code_verifier
        }
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        # Add client secret if provided (for confidential clients)
        if client_secret:
            auth = (self.client_id, client_secret)
        else:
            auth = None
        
        self.logger.info("Exchanging authorization code for tokens")
        response = requests.post(
            self.TOKEN_URL,
            data=token_data,
            headers=headers,
            auth=auth
        )
        
        if response.status_code != 200:
            self.logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
            response.raise_for_status()
            
        token_response = response.json()
        self.logger.info("Token exchange successful")
        
        return token_response
    
    def refresh_access_token(self, refresh_token, client_secret=None):
        """
        Refresh an expired access token using a refresh token.
        
        Args:
            refresh_token (str): Refresh token
            client_secret (str, optional): Client secret (if applicable)
            
        Returns:
            dict: Token response containing new access_token, etc.
        """
        token_data = {
            'client_id': self.client_id,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        # Add client secret if provided (for confidential clients)
        if client_secret:
            auth = (self.client_id, client_secret)
        else:
            auth = None
        
        self.logger.info("Refreshing access token")
        response = requests.post(
            self.TOKEN_URL,
            data=token_data,
            headers=headers,
            auth=auth
        )
        
        if response.status_code != 200:
            self.logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
            response.raise_for_status()
            
        token_response = response.json()
        self.logger.info("Token refresh successful")
        
        return token_response
    
    def save_token_to_dynamo(self, user_id, token_data):
        """
        Save token data to DynamoDB.
        
        Args:
            user_id (str): Unique user identifier
            token_data (dict): Token data from OAuth response
            
        Returns:
            bool: True if successful, False otherwise
        """
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
            
            self.table.put_item(Item=item)
            self.logger.info(f"Token saved to DynamoDB for user {user_id}")
            return True
            
        except ClientError as e:
            self.logger.error(f"Error saving token to DynamoDB: {str(e)}")
            return False
    
    def get_token_from_dynamo(self, user_id):
        """
        Get token data from DynamoDB.
        
        Args:
            user_id (str): Unique user identifier
            
        Returns:
            dict: Token data or None if not found
        """
        try:
            response = self.table.get_item(Key={'user_id': user_id})
            if 'Item' in response:
                self.logger.info(f"Retrieved token from DynamoDB for user {user_id}")
                return response['Item']
            else:
                self.logger.warning(f"No token found in DynamoDB for user {user_id}")
                return None
                
        except ClientError as e:
            self.logger.error(f"Error retrieving token from DynamoDB: {str(e)}")
            return None
    
    def delete_token_from_dynamo(self, user_id):
        """
        Delete token data from DynamoDB.
        
        Args:
            user_id (str): Unique user identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.table.delete_item(Key={'user_id': user_id})
            self.logger.info(f"Token deleted from DynamoDB for user {user_id}")
            return True
            
        except ClientError as e:
            self.logger.error(f"Error deleting token from DynamoDB: {str(e)}")
            return False
    
    def create_web_app(self, client_secret=None, secret_key=None):
        """
        Create and configure the Flask web application for the OAuth flow.
        
        Args:
            client_secret (str, optional): Client secret for the OAuth client
            secret_key (str, optional): Secret key for Flask session
            
        Returns:
            Flask: Configured Flask application
        """
        app = Flask(__name__)
        app.secret_key = secret_key or secrets.token_hex(16)
        
        # Store instance for reference
        self.app = app
        oauth_instance = self
        
        @app.route('/')
        def index():
            """Home page with login link."""
            # Basic HTML for the landing page
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
            </body>
            </html>
            """
        
        @app.route('/login')
        def login():
            """Initiate OAuth flow."""
            try:
                authorization_url, state, code_verifier = oauth_instance.get_authorization_url()
                session['oauth_state'] = state
                session['code_verifier'] = code_verifier
                oauth_instance.logger.info(f"Redirecting user to Twitter authorization URL. State: {state}")
                return redirect(authorization_url)
            except Exception as e:
                 oauth_instance.logger.error(f"Error generating authorization URL: {e}", exc_info=True)
                 return """
                 <h1>Error</h1>
                 <p>Could not initiate the authorization process. Please check the application logs.</p>
                 """, 500
        
        @app.route('/callback')
        def callback():
            """Handle OAuth callback with enhanced error handling."""
            oauth_instance.logger.info(f"Received callback request. Args: {request.args}")

            # --- 1. Check for User Denial or Callback Error ---
            if 'error' in request.args:
                error_code = request.args.get('error')
                error_desc = request.args.get('error_description', 'No description provided.')
                oauth_instance.logger.warning(
                    f"Authorization denied or callback error from Twitter: {error_code} - {error_desc}"
                )
                error_message = f"Authorization failed: Twitter reported an error ({error_code})."
                if error_code == 'access_denied':
                    error_message = "Authorization denied: You cancelled the authorization process on Twitter."
                return f"""
                 <h1>Authorization Failed</h1>
                 <p>{error_message}</p>
                 <p>Please try <a href="/login">authorizing again</a> if this was unintended.</p>
                 """, 400


            # --- 2. Verify State (CSRF Protection) ---
            state_received = request.args.get('state')
            state_expected = session.pop('oauth_state', None) # Pop to use only once
            if not state_expected or state_received != state_expected:
                oauth_instance.logger.error(
                    f"State verification failed. Received: {state_received}, Expected: {state_expected}"
                )
                return """
                <h1>Authorization Failed</h1>
                <p>Invalid state parameter. This could indicate a security issue (CSRF). Please try <a href="/login">authorizing again</a>.</p>
                """, 403

            # --- 3. Exchange Code for Token ---
            code = request.args.get('code')
            code_verifier = session.pop('code_verifier', None) # Pop to use only once

            if not code or not code_verifier:
                 oauth_instance.logger.error("Missing 'code' or 'code_verifier' in callback or session.")
                 return """
                 <h1>Authorization Failed</h1>
                 <p>Could not complete authorization: Missing required parameters in callback or session.</p>
                 """, 400

            try:
                oauth_instance.logger.info("Attempting to fetch token using authorization code.")
                token_data = oauth_instance.fetch_token(
                    code=code,
                    code_verifier=code_verifier,
                    client_secret=client_secret # Pass client_secret if needed
                )
                if not token_data or 'access_token' not in token_data:
                     # Should be caught by raise_for_status in fetch_token, but double-check
                     oauth_instance.logger.error("Token exchange returned invalid data.")
                     return """<h1>Authorization Failed</h1><p>Failed to obtain valid tokens from Twitter.</p>""", 500

            except requests.exceptions.HTTPError as http_err:
                # Logged in fetch_token, provide user feedback
                status_code = http_err.response.status_code
                oauth_instance.logger.error(f"HTTPError during token exchange: {http_err}", exc_info=True)
                error_message = f"Failed to exchange authorization code for tokens (HTTP {status_code})."
                if status_code == 400:
                     error_message += " This might be due to an invalid code or configuration issue."
                elif status_code == 401 or status_code == 403:
                     error_message += " This might indicate an issue with the application's credentials."
                return f"""
                 <h1>Authorization Failed</h1>
                 <p>{error_message}</p>
                 <p>Please check application configuration or try <a href="/login">authorizing again</a>.</p>
                 """, 400
            except requests.exceptions.RequestException as req_err:
                 # Logged in fetch_token
                 oauth_instance.logger.error(f"Network error during token exchange: {req_err}", exc_info=True)
                 return """
                 <h1>Authorization Failed</h1>
                 <p>A network error occurred while contacting Twitter. Please check your connection and try <a href="/login">authorizing again</a>.</p>
                 """, 500
            except Exception as e:
                 # Catch-all for unexpected errors during token fetch
                 oauth_instance.logger.error(f"Unexpected error during token exchange: {e}", exc_info=True)
                 return """
                 <h1>Authorization Failed</h1>
                 <p>An unexpected error occurred during the token exchange process.</p>
                 """, 500

            # --- 4. Store Token ---
            # TODO: Implement proper user identification instead of "default_user"
            # This might involve using the session, or querying the /2/users/me endpoint
            # with the new access token to get the user's Twitter ID.
            user_id = "default_user"
            oauth_instance.logger.info(f"Attempting to save token for user: {user_id}")

            try:
                # Fetch user info to use as user_id (optional but recommended)
                # Example:
                # user_info = self.get_user_info(token_data['access_token'])
                # if user_info and 'id' in user_info:
                #     user_id = user_info['id']
                # else:
                #     self.logger.warning("Could not fetch user info, using default user_id.")
                #     user_id = "default_user" # Fallback

                if oauth_instance.save_token_to_dynamo(user_id, token_data):
                    oauth_instance.logger.info(f"Successfully authorized and saved token for user {user_id}")
                    # Clear session variables after successful use
                    session.pop('code_verifier', None)
                    return """
                    <!DOCTYPE html>
                    <html lang="en">
                    <head><meta charset="UTF-8"><title>Authorization Successful</title></head>
                    <body>
                        <h1>Authorization Successful!</h1>
                        <p>Your X/Twitter account has been successfully linked to the application.</p>
                        <p>You can now close this window.</p>
                    </body>
                    </html>
                    """
                else:
                     # Error logged in save_token_to_dynamo
                     oauth_instance.logger.error(f"Failed to save token to DynamoDB for user {user_id}.")
                     return """
                     <h1>Authorization Failed</h1>
                     <p>Your authorization was successful with Twitter, but we failed to save the credentials securely. Please contact support or check application logs.</p>
                     """, 500
            except Exception as e:
                # Catch-all for unexpected errors during token save or user info fetch
                oauth_instance.logger.error(f"Unexpected error after token exchange (saving token): {e}", exc_info=True)
                return """
                 <h1>Authorization Failed</h1>
                 <p>An unexpected error occurred after obtaining the token. Could not save credentials.</p>
                 """, 500

        return app
    
    def run_web_app(self, host='0.0.0.0', port=5000, **kwargs):
        """
        Run the Flask web application.
        
        Args:
            host (str): Host to run the server on
            port (int): Port to run the server on
            **kwargs: Additional arguments to pass to app.run()
        """
        if self.app is None:
            self.app = self.create_web_app()
        
        self.app.run(host=host, port=port, **kwargs)

    def get_flask_app(self, client_secret=None, secret_key=None):
        """
        Get or create the Flask web app for OAuth 2.0 authentication.
        
        Args:
            client_secret (str, optional): Twitter OAuth 2.0 client secret
            secret_key (str, optional): Secret key for Flask session
            
        Returns:
            Flask: Flask application instance
        """
        if self.app is None:
            self.app = self.create_web_app(client_secret, secret_key)
        
        return self.app


# Create Table in DynamoDB if it doesn't exist
def create_dynamo_table(table_name='XSchedulerUserTokens', region=None):
    """
    Create the DynamoDB table for token storage if it doesn't exist.
    
    Args:
        table_name (str): Table name
        region (str, optional): AWS region
        
    Returns:
        bool: True if table created or already exists, False on error
    """
    try:
        dynamodb = boto3.resource('dynamodb', region_name=region)
        
        # Check if table exists
        existing_tables = [table.name for table in dynamodb.tables.all()]
        if table_name in existing_tables:
            print(f"Table {table_name} already exists")
            return True
        
        # Create table
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'user_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'  # On-demand capacity
        )
        
        # Wait for table to be created
        table.meta.client.get_waiter('table_exists').wait(TableName=table_name)
        print(f"Created DynamoDB table: {table_name}")
        return True
        
    except Exception as e:
        print(f"Error creating DynamoDB table: {str(e)}")
        return False


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("twitter_oauth_test")
    
    # Create DynamoDB table
    create_dynamo_table()
    
    # Test the OAuth flow with environment variables
    from dotenv import load_dotenv
    
    load_dotenv()
    
    client_id = os.getenv('X_OAUTH_CLIENT_ID')
    redirect_uri = os.getenv('X_OAUTH_REDIRECT_URI', 'http://localhost:5000/callback')
    scopes = ['tweet.read', 'tweet.write', 'users.read', 'offline.access']
    
    if not client_id:
        print("X_OAUTH_CLIENT_ID environment variable not set!")
    else:
        # Create OAuth handler
        oauth = TwitterOAuth(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            logger=logger
        )
        
        # Run the web app
        print(f"Starting OAuth web server at {redirect_uri}")
        oauth.run_web_app(debug=True) 