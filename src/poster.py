"""
Twitter Poster Module.

This module handles posting tweets to Twitter (X) using the Twitter API v2.
"""
import tweepy
import time
import os
import requests
import math
import traceback
from datetime import datetime, timezone
from typing import Dict, Optional, List, Union, BinaryIO
from .utils import retry
from .oauth import TwitterOAuth
from requests.exceptions import RequestException, HTTPError
import json
from urllib.parse import urlencode


class TwitterPoster:
    """
    Handles posting tweets to Twitter (X) using the Twitter API.
    """
    
    # Media upload constants
    MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"
    CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks
    
    def __init__(self, credentials, logger=None, oauth_credentials=None):
        """
        Initialize the Twitter poster with API credentials.
        
        Args:
            credentials (dict): Twitter API credentials for OAuth 1.0a
            logger: Logger to use for logging
            oauth_credentials (dict, optional): OAuth 2.0 credentials for video uploads
        """
        self.logger = logger
        
        # OAuth 1.0a credentials
        self.api_key = credentials.get('api_key')
        self.api_key_secret = credentials.get('api_key_secret')
        self.access_token = credentials.get('access_token')
        self.access_token_secret = credentials.get('access_token_secret')
        self.bearer_token = credentials.get('bearer_token')
        
        # OAuth 2.0 credentials and handler
        self.oauth_credentials = oauth_credentials
        self.oauth_handler = None
        if oauth_credentials and oauth_credentials.get('client_id'):
            self.init_oauth2()
        
        # Validate OAuth 1.0a credentials
        if not self.api_key or not self.api_key_secret or not self.access_token or not self.access_token_secret:
            error_msg = "Missing required Twitter API credentials."
            if self.logger:
                self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Initialize the Twitter API client
        self._init_client()
        
    def _init_client(self):
        """
        Initialize the Twitter API client using tweepy.
        """
        try:
            # Create OAuth 1.0a authentication handler
            auth = tweepy.OAuth1UserHandler(
                self.api_key,
                self.api_key_secret,
                self.access_token,
                self.access_token_secret
            )
            
            # Create API instance
            self.api = tweepy.API(auth, wait_on_rate_limit=True)
            
            # Create Client (v2) instance
            self.client = tweepy.Client(
                bearer_token=self.bearer_token,
                consumer_key=self.api_key,
                consumer_secret=self.api_key_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret
            )
            
            if self.logger:
                self.logger.info("Twitter API client initialized successfully.")
                
        except Exception as e:
            error_msg = f"Failed to initialize Twitter API client: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            raise
    
    def init_oauth2(self):
        """
        Initialize the OAuth 2.0 handler for video uploads.
        """
        if not self.oauth_credentials:
            if self.logger:
                self.logger.warning("No OAuth 2.0 credentials provided, video uploads will not be available.")
            return
            
        try:
            client_id = self.oauth_credentials.get('client_id')
            client_secret = self.oauth_credentials.get('client_secret')
            redirect_uri = self.oauth_credentials.get('redirect_uri')
            scopes = self.oauth_credentials.get('scopes')
            
            if not client_id or not redirect_uri or not scopes:
                if self.logger:
                    self.logger.warning("Incomplete OAuth 2.0 credentials, video uploads will not be available.")
                return
                
            # Initialize OAuth 2.0 handler
            self.oauth_handler = TwitterOAuth(
                client_id=client_id,
                redirect_uri=redirect_uri,
                scopes=scopes,
                logger=self.logger
            )
            
            # Create the Flask app in advance
            self.oauth_handler.get_flask_app(client_secret=client_secret)
            
            if self.logger:
                self.logger.info("OAuth 2.0 handler initialized successfully.")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize OAuth 2.0 handler: {str(e)}")
            self.oauth_handler = None
    
    def get_oauth2_token(self, user_id="default_user"):
        """
        Get OAuth 2.0 token for a user from DynamoDB.
        
        Args:
            user_id (str): User ID to get token for
            
        Returns:
            dict: Token data or None if not found
        """
        if not self.oauth_handler:
            if self.logger:
                self.logger.warning("OAuth 2.0 handler not initialized, cannot get token.")
            return None
            
        try:
            self.logger.debug(f"Attempting to retrieve OAuth token for user: {user_id}")
            
            # Get token from DynamoDB
            token_data = self.oauth_handler.get_token_from_dynamo(user_id)
            
            if not token_data:
                if self.logger:
                    self.logger.warning(f"No OAuth 2.0 token found for user {user_id}.")
                return None
                
            self.logger.debug(f"Retrieved token data from DynamoDB for user: {user_id}")
            
            # Check token structure for debugging
            expected_keys = ['access_token', 'refresh_token', 'expires_at']
            missing_keys = [key for key in expected_keys if key not in token_data]
            if missing_keys:
                self.logger.warning(f"Token data for user {user_id} is missing expected keys: {missing_keys}")
            
            # Check if token is expired
            current_time = int(time.time())
            expires_at = token_data.get('expires_at', 0)
            
            self.logger.debug(f"Token expiration check: Current time={current_time}, Expires at={expires_at}, " +
                              f"Remaining={(expires_at - current_time)} seconds")
            
            if expires_at <= current_time:
                if self.logger:
                    self.logger.info(f"OAuth 2.0 token expired for user {user_id}, refreshing.")
                    
                # Refresh token
                refresh_token = token_data.get('refresh_token')
                if not refresh_token:
                    if self.logger:
                        self.logger.error(f"No refresh token available for user {user_id}.")
                    return None
                    
                # Get client secret for token refresh
                client_secret = self.oauth_credentials.get('client_secret')
                if not client_secret:
                    self.logger.error("Missing client_secret in oauth_credentials, cannot refresh token")
                    return None
                
                self.logger.debug(f"Attempting to refresh token for user: {user_id}")
                
                # Refresh the token
                new_token_data = self.oauth_handler.refresh_access_token(
                    refresh_token=refresh_token,
                    client_secret=client_secret
                )
                
                if not new_token_data:
                    self.logger.error(f"Failed to refresh token for user {user_id}")
                    return None
                    
                self.logger.debug(f"Successfully refreshed token for user: {user_id}")
                
                # Save new token to DynamoDB
                try:
                    self.oauth_handler.save_token_to_dynamo(user_id, new_token_data)
                    self.logger.debug(f"Saved refreshed token to DynamoDB for user: {user_id}")
                except Exception as save_err:
                    self.logger.error(f"Failed to save refreshed token to DynamoDB: {save_err}")
                    # Continue with the new token even if saving failed
                
                # Return new token data
                return new_token_data
            
            self.logger.debug(f"Using existing valid token for user: {user_id}")
            return token_data
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting OAuth 2.0 token: {str(e)}")
                self.logger.debug(f"OAuth token retrieval error details: {traceback.format_exc()}")
            return None
    
    def _retry_with_instance_logger(self, func):
        """
        Wrapper to use the instance logger with the retry decorator.
        
        Args:
            func: The function to wrap with retry logic
            
        Returns:
            The wrapped function with retry logic
        """
        return retry(max_tries=5, delay=2, backoff=2, exceptions=(RequestException,), logger=self.logger)(func)
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Makes an HTTP request with logging and rate limit header capture.
        Uses the enhanced retry logic from utils.

        Args:
            method (str): HTTP method ('GET', 'POST', etc.)
            url (str): URL to request.
            **kwargs: Additional arguments passed to requests.request().

        Returns:
            requests.Response: The response object.

        Raises:
            requests.exceptions.HTTPError: If the request returns a 4xx or 5xx status.
            requests.exceptions.RequestException: For other request errors (handled by retry).
        """
        # Wrap this method with retry using the instance logger
        return self._retry_with_instance_logger(self._make_request_impl)(method, url, **kwargs)
        
    def _make_request_impl(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Implementation of the HTTP request with logging and rate limit header capture.
        """
        # Log detailed request information when in DEBUG mode
        self.logger.debug(f"Making {method} request to {url}")
        self.logger.debug(f"Request kwargs: {kwargs}")
        
        # Extract and log headers separately for better readability
        if 'headers' in kwargs:
            self.logger.debug(f"Request headers: {kwargs['headers']}")
            
        # Extract and sanitize params for logging (remove sensitive info)
        if 'params' in kwargs:
            sanitized_params = kwargs['params'].copy() if isinstance(kwargs['params'], dict) else kwargs['params']
            if isinstance(sanitized_params, dict) and 'oauth_token' in sanitized_params:
                sanitized_params['oauth_token'] = '***REDACTED***'
            self.logger.debug(f"Request params: {sanitized_params}")
            
        try:
            self.logger.debug(f"Sending {method} request to {url}...")
            response = requests.request(method, url, **kwargs)
            self.logger.debug(f"Received response: status_code={response.status_code}")
            self.logger.debug(f"Response headers: {dict(response.headers)}")

            # Log rate limit headers if present
            limit = response.headers.get('x-ratelimit-limit')
            remaining = response.headers.get('x-ratelimit-remaining')
            reset = response.headers.get('x-ratelimit-reset')
            if limit or remaining or reset:
                 reset_time_str = ""
                 if reset:
                     try:
                         reset_time_str = f" (Resets: {datetime.fromtimestamp(int(reset), tz=timezone.utc).isoformat()})"
                     except: # noqa E722 - ignore bare except here
                         reset_time_str = " (Reset time parse error)" # Handle potential parsing errors
                 self.logger.debug(
                     f"Rate Limit Info: Limit={limit}, Remaining={remaining}, Reset={reset}{reset_time_str} for {url}"
                 )

            # For any 2xx/3xx responses, try to log response content for debugging
            if response.status_code < 400:
                try:
                    if 'application/json' in response.headers.get('Content-Type', ''):
                        self.logger.debug(f"Response JSON: {response.json()}")
                    else:
                        # Log first 500 chars of text responses
                        if len(response.text) > 0:
                            preview = response.text[:500] + ('...' if len(response.text) > 500 else '')
                            self.logger.debug(f"Response content preview: {preview}")
                except Exception as e:
                    self.logger.debug(f"Could not log response content: {str(e)}")
                
            # After logging, raise HTTPError for bad responses (4xx or 5xx)
            response.raise_for_status()
            return response

        except HTTPError as http_err:
             # Log detailed error info for debugging
             self.logger.warning(f"HTTP Error during {method} {url}: {http_err.response.status_code} {http_err.response.reason}")
             self.logger.debug(f"Error response headers: {dict(http_err.response.headers)}")
             
             # Log full response text for debugging but truncate for regular warning
             self.logger.debug(f"Full error response: {http_err.response.text}")
             self.logger.warning(f"Error response preview: {http_err.response.text[:500]}...") # Log first 500 chars
             
             # The @retry decorator will catch this and handle retries/final raise
             raise
        except RequestException as req_err:
             # Log details before raising/retrying
             self.logger.warning(f"Request Exception during {method} {url}: {req_err}")
             self.logger.debug(f"Request Exception details: {traceback.format_exc()}")
             # The @retry decorator will catch this and handle retries/final raise
             raise
        except Exception as e:
            # Catch any other unexpected errors during the request phase
            self.logger.error(f"Unexpected error during {method} {url}: {e}")
            self.logger.debug(f"Unexpected error details: {traceback.format_exc()}")
            raise # Re-raise unexpected errors

    def _init_media_upload(self, file_path, media_type, media_category="tweet_video", user_id="default_user"):
        """
        Initialize a chunked media upload (INIT command).
        Uses _make_request for robustness.
        """
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return None

        file_size = os.path.getsize(file_path)
        self.logger.debug(f"Initializing media upload for file: {file_path}, size: {file_size} bytes, type: {media_type}, category: {media_category}")
        
        token_data = self.get_oauth2_token(user_id)
        if not token_data:
            self.logger.error("Failed to get OAuth 2.0 token for media upload INIT.")
            return None
        access_token = token_data.get('access_token')
        self.logger.debug(f"Successfully retrieved access token for user: {user_id}")

        # Query parameters (v2 endpoint uses URL params for command)
        init_params = {
            'command': 'INIT',
            'total_bytes': str(file_size),  # v2 requires string values
            'media_type': media_type,
            'media_category': media_category
        }
        
        # Explicitly set content type for INIT request
        headers = {
            'Authorization': f"Bearer {access_token}",
            'Content-Type': 'application/json'  # Explicit content type for INIT
        }
        
        self.logger.debug(f"Media upload INIT request parameters: {init_params}")
        self.logger.debug(f"Media upload INIT request headers: {headers}")

        try:
            self.logger.info(f"Initializing media upload for file: {file_path}")
            self.logger.debug(f"Making POST request to {self.MEDIA_UPLOAD_URL}?{urlencode(init_params)}")
            
            # For v2, we use the query parameters in the URL, not in the body
            url_with_params = f"{self.MEDIA_UPLOAD_URL}?{urlencode(init_params)}"
            
            response = self._make_request(
                "POST",
                url_with_params,
                headers=headers,
                timeout=30 # Add a timeout
            )
            
            self.logger.debug(f"Media upload INIT response status: {response.status_code}")
            self.logger.debug(f"Media upload INIT response headers: {dict(response.headers)}")
            
            result = response.json()
            self.logger.debug(f"Media upload INIT response JSON: {result}")
            
            # v2 endpoint returns media_id inside a data object
            try:
                media_id = result.get('data', {}).get('id')
                if not media_id:
                    media_id = result.get('media_id_string')  # Fallback to v1.1 format
            except (KeyError, TypeError):
                self.logger.error(f"Unexpected response format from media upload INIT: {result}")
                media_id = None
                
            if media_id:
                self.logger.info(f"Media upload initialized. Media ID: {media_id}")
                return media_id
            else:
                self.logger.error(f"Failed to extract media_id from INIT response: {result}")
                return None
                
        except HTTPError as e:
            # Special handling for 403 Forbidden errors
            if hasattr(e, 'response') and e.response and e.response.status_code == 403:
                self.logger.error(f"Authorization error (403 Forbidden) during media upload INIT")
                self.logger.debug(f"Request URL: {e.request.url if hasattr(e, 'request') else 'unknown'}")
                self.logger.debug(f"Request headers: {dict(e.request.headers) if hasattr(e, 'request') else 'unknown'}")
                self.logger.debug(f"Response headers: {dict(e.response.headers)}")
                self.logger.debug(f"Response text: {e.response.text}")
                
                # Try to parse response for more specific error details
                try:
                    error_data = e.response.json()
                    if isinstance(error_data, dict):
                        if "errors" in error_data:
                            for error in error_data["errors"]:
                                self.logger.error(f"Twitter API error: {error}")
                        elif "error" in error_data:
                            self.logger.error(f"Twitter API error: {error_data['error']}")
                except Exception as parse_err:
                    self.logger.debug(f"Could not parse error response as JSON: {parse_err}")
                
                # Log possible solutions
                self.logger.error("Possible solutions for 403 error:")
                self.logger.error("1. Check if the Twitter app has correct permissions for media uploads")
                self.logger.error("2. Verify if your API access level allows media uploads")
                self.logger.error("3. Ensure the OAuth token has the required scopes (media.upload, media.read)")
                self.logger.error("4. Check if you've hit rate limits for media uploads")
            else:
                # General error handling
                self.logger.error(f"Failed to initialize media upload after retries: {e}")
                if hasattr(e, 'response') and e.response:
                    self.logger.debug(f"Error response status: {e.response.status_code}")
                    self.logger.debug(f"Error response headers: {dict(e.response.headers)}")
                    self.logger.debug(f"Error response content: {e.response.text}")
            return None
        except RequestException as e:
            self.logger.error(f"Network error during media upload INIT: {e}")
            self.logger.debug(f"RequestException details: {traceback.format_exc()}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during media upload INIT: {e}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            return None

    def _append_media_upload(self, media_id, file_handle: BinaryIO, chunk_index, user_id="default_user"):
        """
        Append a chunk to the media upload (APPEND command).
        Uses _make_request for robustness.

        Args:
            media_id (str): The media ID from the INIT command.
            file_handle (BinaryIO): The open file handle for the media file.
            chunk_index (int): The 0-based index of the chunk being uploaded.
            user_id (str): User ID to get OAuth token for.

        Returns:
            bool: True if the append was successful, False otherwise.
        """
        token_data = self.get_oauth2_token(user_id)
        if not token_data:
            self.logger.error("Failed to get OAuth 2.0 token for media upload APPEND.")
            return False
        access_token = token_data.get('access_token')

        # For v2 API, parameters go in the URL
        append_params = {
            'command': 'APPEND',
            'media_id': media_id,
            'segment_index': str(chunk_index)  # v2 requires string values
        }
        
        # Create URL with parameters
        url_with_params = f"{self.MEDIA_UPLOAD_URL}?{urlencode(append_params)}"
        
        # Set headers explicitly for the append request
        headers = {
            'Authorization': f"Bearer {access_token}"
            # Don't set Content-Type here as requests will handle it for multipart/form-data
        }
        
        # Read the chunk from the file handle
        chunk = file_handle.read(self.CHUNK_SIZE)
        if not chunk:
            self.logger.warning("Attempted to append an empty chunk.")
            return False # Or handle as appropriate

        # Create a FormData with the media blob - no additional parameters in the body
        # For v2 API, all parameters are in the URL
        files = {
            'media': ('blob', chunk, 'application/octet-stream')
        }
        
        self.logger.debug(f"APPEND request URL: {url_with_params}")
        self.logger.debug(f"APPEND chunk size: {len(chunk)} bytes")

        try:
            self.logger.info(f"Appending chunk {chunk_index} for media ID: {media_id}")
            
            response = self._make_request(
                "POST",
                url_with_params,
                files=files,
                headers=headers,
                timeout=60 # Longer timeout for upload
            )
            # Successful APPEND returns 2xx status code, no JSON body expected
            self.logger.info(f"Successfully appended chunk {chunk_index} for media ID: {media_id}")
            return True
        except HTTPError as e:
            # Special handling for 403 Forbidden errors
            if hasattr(e, 'response') and e.response and e.response.status_code == 403:
                self.logger.error(f"Authorization error (403 Forbidden) during media upload APPEND for chunk {chunk_index}")
                self.logger.debug(f"Response text: {e.response.text}")
                
                # Try to parse response for more specific error details
                try:
                    error_data = e.response.json()
                    if isinstance(error_data, dict) and "errors" in error_data:
                        for error in error_data["errors"]:
                            self.logger.error(f"Twitter API error: {error}")
                except Exception:
                    pass
            else:
                self.logger.error(f"Failed to append chunk {chunk_index} for media ID {media_id} after retries: {e}")
            
            # Attempt to read response body if available in exception
            try:
                if e.response is not None:
                    self.logger.error(f"Append error response body: {e.response.text}")
            except Exception:
                pass
            return False
        except RequestException as e:
            self.logger.error(f"Network error during APPEND for chunk {chunk_index}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during media upload APPEND for chunk {chunk_index}: {e}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            return False

    def _finalize_media_upload(self, media_id, user_id="default_user"):
        """
        Finalize a chunked media upload (FINALIZE command).
        Uses _make_request for robustness.

        Args:
            media_id (str): The media ID from the INIT command.
            user_id (str): User ID to get OAuth token for.

        Returns:
            dict: The response JSON if successful, None otherwise.
        """
        token_data = self.get_oauth2_token(user_id)
        if not token_data:
            self.logger.error("Failed to get OAuth 2.0 token for media upload FINALIZE.")
            return None
        access_token = token_data.get('access_token')

        # For v2 API, parameters go in the URL
        finalize_params = {
            'command': 'FINALIZE',
            'media_id': media_id
        }
        
        # Create URL with parameters
        url_with_params = f"{self.MEDIA_UPLOAD_URL}?{urlencode(finalize_params)}"
        
        # Set headers for the finalize request
        headers = {
            'Authorization': f"Bearer {access_token}",
            'Content-Type': 'application/json'
        }
        
        self.logger.debug(f"FINALIZE request URL: {url_with_params}")

        try:
            self.logger.info(f"Finalizing media upload for media ID: {media_id}")
            response = self._make_request(
                "POST",
                url_with_params,
                headers=headers,
                timeout=30
            )
            
            self.logger.debug(f"FINALIZE response status: {response.status_code}")
            
            result = response.json()
            self.logger.debug(f"FINALIZE response JSON: {result}")
            
            # For v2 API, we may need to extract the result from the 'data' object
            if 'data' in result:
                self.logger.debug("Extracting data from v2 API response")
                data = result['data']
                if 'processing_info' in result:
                    data['processing_info'] = result['processing_info']
                return data
            else:
                # Fallback for v1.1-style response
                return result
                
        except HTTPError as e:
            # Special handling for 403 Forbidden errors
            if hasattr(e, 'response') and e.response and e.response.status_code == 403:
                self.logger.error(f"Authorization error (403 Forbidden) during media upload FINALIZE")
                self.logger.debug(f"Response text: {e.response.text}")
                
                try:
                    error_data = e.response.json()
                    if isinstance(error_data, dict) and "errors" in error_data:
                        for error in error_data["errors"]:
                            self.logger.error(f"Twitter API error: {error}")
                except Exception:
                    pass
            else:
                self.logger.error(f"Failed to finalize media upload after retries: {e}")
            return None
        except RequestException as e:
            self.logger.error(f"Network error during FINALIZE: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during media upload FINALIZE: {e}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            return None

    def _check_media_status(self, media_id, user_id="default_user"):
        """
        Check the status of a media upload (STATUS command).
        Uses _make_request for robustness.

        Args:
            media_id (str): The media ID from the INIT command.
            user_id (str): User ID to get OAuth token for.

        Returns:
            dict: The response JSON if successful, None otherwise.
        """
        token_data = self.get_oauth2_token(user_id)
        if not token_data:
            self.logger.error("Failed to get OAuth 2.0 token for media upload STATUS check.")
            return None
        access_token = token_data.get('access_token')
        
        # For v2 API, parameters go in the URL
        status_params = {
            'command': 'STATUS',
            'media_id': media_id
        }
        
        # Create URL with parameters
        url_with_params = f"{self.MEDIA_UPLOAD_URL}?{urlencode(status_params)}"
        
        # Set headers for the status request
        headers = {
            'Authorization': f"Bearer {access_token}"
        }
        
        self.logger.debug(f"STATUS request URL: {url_with_params}")

        try:
            self.logger.debug(f"Checking media upload status for media ID: {media_id}")
            response = self._make_request(
                "GET",
                url_with_params,
                headers=headers,
                timeout=30
            )
            
            self.logger.debug(f"STATUS response status: {response.status_code}")
            
            # Parse the response
            result = response.json()
            self.logger.debug(f"STATUS response JSON: {result}")
            
            # For v2 API, we may need to extract the result from the 'data' object
            if 'data' in result:
                self.logger.debug("Extracting data from v2 API response")
                data = result['data']
                if 'processing_info' in result:
                    data['processing_info'] = result['processing_info']
                return data
            else:
                # Fallback for v1.1-style response
                return result

        except HTTPError as e:
            # Special handling for 404 Not Found - this sometimes happens for complete media
            if hasattr(e, 'response') and e.response and e.response.status_code == 404:
                self.logger.warning(f"Media ID {media_id} not found during STATUS check. This may indicate processing is complete.")
                # Return a "succeeded" state to simulate successful completion
                return {'processing_info': {'state': 'succeeded'}}
            
            # General error handling
            self.logger.error(f"Failed to check status for media ID {media_id}: {e}")
            if hasattr(e, 'response') and e.response:
                self.logger.debug(f"Error response content: {e.response.text}")
            return None
        except RequestException as e:
            self.logger.error(f"Network error during STATUS check for media ID {media_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during media upload STATUS check for {media_id}: {e}")
            self.logger.debug(f"Exception details: {traceback.format_exc()}")
            return None

    def upload_video(self, file_path, media_type="video/mp4", media_category="tweet_video", user_id="default_user", max_wait_time=600):
        """
        Uploads a video using the chunked media upload protocol.

        Args:
            file_path (str): Path to the video file.
            media_type (str): MIME type (default: 'video/mp4').
            media_category (str): Category (default: 'tweet_video').
            user_id (str): User ID for OAuth token.
            max_wait_time (int): Maximum time in seconds to wait for processing.

        Returns:
            str: The finalized media ID string if successful, None otherwise.
        """
        start_time = time.time()
        self.logger.info(f"Starting video upload process for: {file_path}")

        # Basic file validation
        if not os.path.exists(file_path):
            self.logger.error(f"Video file not found: {file_path}")
            return None
            
        # Get file size and check basic limits
        file_size = os.path.getsize(file_path)
        self.logger.debug(f"Video file size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")
        
        # Check X/Twitter file size limits
        if file_size > 512 * 1024 * 1024:  # 512MB
            self.logger.error(f"Video file exceeds X/Twitter's 512MB limit: {file_size / (1024*1024):.2f} MB")
            return None
            
        # Attempt to get video information if ffprobe is available
        try:
            import subprocess
            ffprobe_cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "stream=codec_type,codec_name,width,height,duration",
                "-of", "json",
                file_path
            ]
            result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=False, timeout=30)
            if result.returncode == 0:
                video_info = json.loads(result.stdout)
                self.logger.debug(f"Video metadata: {video_info}")
            else:
                self.logger.debug(f"Could not get video information: {result.stderr}")
        except Exception as e:
            self.logger.debug(f"Failed to analyze video with ffprobe: {e}")
        
        # Get OAuth token first to verify credentials are working
        token_data = self.get_oauth2_token(user_id)
        if not token_data:
            self.logger.error("Could not retrieve OAuth token before starting upload. Authentication may be invalid.")
            return None
        
        # Log token expiration info for debugging
        if 'expires_at' in token_data:
            expires_at = token_data['expires_at']
            current_time = int(time.time())
            time_until_expiry = expires_at - current_time
            self.logger.debug(f"OAuth token valid for {time_until_expiry} seconds")

        # 1. INIT
        self.logger.info(f"Initializing media upload for {file_path}")
        media_id = self._init_media_upload(file_path, media_type, media_category, user_id)
        if not media_id:
            self.logger.error("Video upload failed during INIT step.")
            return None

        # 2. APPEND chunks
        try:
            with open(file_path, 'rb') as file_handle:
                total_size = os.path.getsize(file_path)
                total_chunks = math.ceil(total_size / self.CHUNK_SIZE)
                self.logger.info(f"Appending {total_chunks} chunks for {total_size} bytes...")
                
                for i in range(total_chunks):
                    start_pos = i * self.CHUNK_SIZE
                    self.logger.debug(f"Uploading chunk {i+1}/{total_chunks} (offset: {start_pos})")
                    
                    if not self._append_media_upload(media_id, file_handle, i, user_id):
                        self.logger.error(f"Video upload failed during APPEND step for chunk {i+1}/{total_chunks}.")
                        return None
                        
                    # Progress tracking
                    if i % 5 == 0 or i == total_chunks - 1:  # Log every 5 chunks and the last one
                        progress = min(100, round((i + 1) / total_chunks * 100, 1))
                        elapsed = time.time() - start_time
                        self.logger.info(f"Upload progress: {progress}% ({i+1}/{total_chunks} chunks), elapsed: {elapsed:.1f}s")
                    
                    if time.time() - start_time > max_wait_time:
                         self.logger.error(f"Video upload timed out during APPEND after {max_wait_time}s.")
                         return None

        except FileNotFoundError:
            self.logger.error(f"Video file not found during APPEND: {file_path}")
            return None
        except Exception as e:
             self.logger.error(f"Unexpected error during video APPEND phase: {e}")
             self.logger.debug(f"APPEND error details: {traceback.format_exc()}")
             return None

        # 3. FINALIZE
        self.logger.info("All chunks uploaded. Finalizing media upload...")
        finalize_result = self._finalize_media_upload(media_id, user_id)
        if not finalize_result:
            self.logger.error("Video upload failed during FINALIZE step.")
            return None

        # Handle potential processing time indicated by finalize_result
        processing_info = finalize_result.get('processing_info')
        if processing_info:
            state = processing_info.get('state')
            check_after_secs = processing_info.get('check_after_secs')
            progress = processing_info.get('progress_percent', 'N/A')
            
            self.logger.debug(f"Processing info from FINALIZE: state={state}, progress={progress}%, check_after={check_after_secs}s")

            if state == 'succeeded':
                 self.logger.info(f"Video processing finished during FINALIZE. Media ID: {media_id}")
                 return media_id # Already done
            elif state == 'failed':
                 error_info = processing_info.get('error', {})
                 self.logger.error(f"Video processing failed during FINALIZE. Code: {error_info.get('code')}, Name: {error_info.get('name')}, Message: {error_info.get('message')}")
                 return None
            elif state == 'in_progress' or state == 'pending':
                 if check_after_secs:
                     self.logger.info(f"Video processing is '{state}', progress: {progress}%. Waiting {check_after_secs}s before checking status...")
                     if time.time() - start_time + check_after_secs > max_wait_time:
                         self.logger.error(f"Video upload timed out waiting for initial processing check after {max_wait_time}s.")
                         return None
                     time.sleep(check_after_secs)
                 else:
                      # Should not happen based on docs, but handle defensively
                      self.logger.warning("Processing info present in FINALIZE but no check_after_secs provided. Waiting 5s.")
                      time.sleep(5)
        else:
            self.logger.debug("No processing info in FINALIZE response, continuing to STATUS polling")

        # 4. STATUS polling if processing is not complete
        self.logger.info(f"Polling STATUS for media ID: {media_id}")
        poll_count = 0
        
        while True:
            poll_count += 1
            elapsed_time = time.time() - start_time
            self.logger.debug(f"STATUS poll #{poll_count} at {elapsed_time:.1f}s elapsed")
            
            if elapsed_time > max_wait_time:
                self.logger.error(f"Video processing timed out after {max_wait_time} seconds.")
                return None

            status_result = self._check_media_status(media_id, user_id)
            if not status_result:
                self.logger.error("Failed to get video processing status.")
                # Consider if we should retry status check or fail upload here
                return None # Fail upload if status check fails repeatedly

            processing_info = status_result.get('processing_info')
            if not processing_info:
                self.logger.error("No processing_info found in STATUS response.")
                self.logger.debug(f"STATUS response without processing_info: {status_result}")
                # This might indicate an issue, potentially fail here
                time.sleep(5) # Wait before retrying status
                continue

            state = processing_info.get('state')
            progress = processing_info.get('progress_percent', 'N/A')
            self.logger.info(f"Current processing state: '{state}' (Progress: {progress}%)")

            if state == 'succeeded':
                total_time = time.time() - start_time
                self.logger.info(f"Video processing succeeded for media ID: {media_id} in {total_time:.1f}s")
                return media_id
            elif state == 'failed':
                error_info = processing_info.get('error', {})
                self.logger.error(f"Video processing failed. Code: {error_info.get('code')}, Name: {error_info.get('name')}, Message: {error_info.get('message')}")
                self.logger.debug(f"Full error details: {error_info}")
                return None
            elif state == 'in_progress' or state == 'pending':
                check_after_secs = processing_info.get('check_after_secs', 5) # Default wait 5s if not specified
                wait_time = max(1, check_after_secs) # Ensure at least 1s wait
                self.logger.info(f"Processing still '{state}' ({progress}%). Waiting {wait_time}s...")
                if time.time() - start_time + wait_time > max_wait_time:
                    self.logger.error(f"Video upload timed out while waiting for next status check after {max_wait_time}s.")
                    return None
                time.sleep(wait_time)
            else:
                 self.logger.error(f"Unknown processing state encountered: '{state}'. Aborting.")
                 self.logger.debug(f"Full processing info for unknown state: {processing_info}")
                 return None

    def post_tweet(self, text: str, media_ids: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Post a tweet using the Twitter API v2.

        Args:
            text (str): The text content of the tweet.
            media_ids (Optional[List[str]]): List of media ID strings to attach (e.g., from upload_video).

        Returns:
            Optional[Dict]: Dictionary containing the response data (tweet ID and text)
                            if successful, None otherwise.
        """
        # Wrap this method with retry using the instance logger and different params for tweet posting
        retry_decorator = retry(max_tries=3, delay=5, backoff=2, exceptions=(tweepy.TweepyException,), logger=self.logger)
        return retry_decorator(self._post_tweet_impl)(text, media_ids)
        
    def _post_tweet_impl(self, text: str, media_ids: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Implementation of posting a tweet using the Twitter API v2.
        """
        try:
            self.logger.info(f"Attempting to post tweet: {text[:50]}... Media IDs: {media_ids}")

            # Ensure media_ids is None or a list
            if media_ids and not isinstance(media_ids, list):
                 self.logger.warning(f"media_ids provided is not a list ({type(media_ids)}), converting.")
                 media_ids = list(media_ids)
            elif not media_ids:
                 media_ids = None # Explicitly set to None if empty or None


            # Handle parameter exclusivity - media_ids OR other params (poll, etc.)
            # Currently only handling text and media
            if media_ids:
                response = self.client.create_tweet(text=text, media_ids=media_ids)
            else:
                response = self.client.create_tweet(text=text)

            if response and response.data:
                 tweet_id = response.data.get('id')
                 tweet_text = response.data.get('text')
                 self.logger.info(f"Tweet posted successfully! ID: {tweet_id}, Text: {tweet_text}")
                 # Return the core data
                 return {"id": tweet_id, "text": tweet_text}
            else:
                 # This case might occur if the API returns an unexpected success response format
                 self.logger.error(f"Tweet post request successful but response data is missing or invalid: {response}")
                 return None

        except tweepy.errors.TweepyException as e:
            # Log detailed error, including rate limit info if available from Tweepy's exception
            api_errors = getattr(e, 'api_errors', None)
            response_headers = getattr(e.response, 'headers', None) if hasattr(e, 'response') else None

            rate_limit_info = ""
            if response_headers:
                 limit = response_headers.get('x-ratelimit-limit')
                 remaining = response_headers.get('x-ratelimit-remaining')
                 reset = response_headers.get('x-ratelimit-reset')
                 if limit or remaining or reset:
                     reset_time_str = f" (Resets: {datetime.fromtimestamp(int(reset), tz=timezone.utc).isoformat()})" if reset else ""
                     rate_limit_info = f" [Rate Limit: Limit={limit}, Remaining={remaining}, Reset={reset}{reset_time_str}]"


            self.logger.error(f"Failed to post tweet: {e}{rate_limit_info}")
            if api_errors:
                 self.logger.error(f"API Errors: {api_errors}")
             # The @retry decorator will handle retries / final raise for TweepyException

            # Re-raise the exception to be caught by the @retry decorator
            raise e
        except Exception as e:
            # Catch any other unexpected errors during tweet posting
            self.logger.error(f"Unexpected error during tweet posting: {e}\n{traceback.format_exc()}")
            raise # Re-raise unexpected errors

    def verify_credentials(self) -> bool:
        """
        Verify if the provided API credentials are valid using OAuth 1.0a.

        Returns:
            bool: True if credentials are valid, False otherwise.
        """
        try:
            # Using OAuth 1.0a client (self.api) for verify_credentials
            user = self.api.verify_credentials()
            if user:
                self.logger.info(f"Credentials verified successfully for user: {user.screen_name}")
                return True
            else:
                self.logger.error("Credential verification failed: No user object returned.")
                return False
        except tweepy.errors.TweepyException as e:
            self.logger.error(f"Credential verification failed: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during credential verification: {e}")
            return False

    def start_oauth_web_server(self, host='0.0.0.0', port=5000, debug=False):
        """
        Starts the Flask web server for OAuth 2.0 authentication.

        Args:
            host (str): Host to run the server on.
            port (int): Port to run the server on.
            debug (bool): Whether to run Flask in debug mode.
        """
        if not self.oauth_handler:
            self.logger.error("OAuth handler not initialized. Make sure OAuth credentials are provided.")
            self.logger.info("Trying to initialize OAuth handler now...")
            
            # Try to initialize OAuth handler if not already done
            self.init_oauth2()
            
            if not self.oauth_handler:
                self.logger.error("Failed to initialize OAuth handler. Cannot start web server.")
                return

        try:
            # Get client secret for the Flask app
            client_secret = self.oauth_credentials.get('client_secret') if self.oauth_credentials else None
            
            # Get the Flask app instance
            app = self.oauth_handler.get_flask_app(client_secret=client_secret)
            
            if app:
                self.logger.info(f"Starting OAuth web server on http://{host}:{port}")
                
                try:
                    # Try to use waitress for production-grade server
                    from waitress import serve
                    self.logger.info("Using waitress production server")
                    serve(app, host=host, port=port)
                except ImportError:
                    # Fall back to Flask's built-in server for development
                    self.logger.info("waitress not available, using Flask development server")
                    app.run(host=host, port=port, debug=debug)
            else:
                self.logger.error("Failed to get Flask app from OAuth handler.")

        except Exception as e:
            self.logger.error(f"Failed to start OAuth web server: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    # Test the Twitter poster
    import logging
    from dotenv import load_dotenv
    import os
    
    # Load environment variables
    load_dotenv()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("twitter_poster_test")
    
    # Get API credentials from environment variables
    credentials = {
        'api_key': os.getenv('X_API_KEY'),
        'api_key_secret': os.getenv('X_API_KEY_SECRET'),
        'access_token': os.getenv('X_ACCESS_TOKEN'),
        'access_token_secret': os.getenv('X_ACCESS_TOKEN_SECRET'),
        'bearer_token': os.getenv('X_BEARER_TOKEN')
    }
    
    # Get OAuth 2.0 credentials if available
    oauth_credentials = {
        'client_id': os.getenv('X_OAUTH_CLIENT_ID'),
        'client_secret': os.getenv('X_OAUTH_CLIENT_SECRET'),
        'redirect_uri': os.getenv('X_OAUTH_REDIRECT_URI', 'http://localhost:5000/callback'),
        'scopes': ['tweet.read', 'tweet.write', 'users.read', 'offline.access']
    }
    
    # Check if credentials are available
    if not all([credentials['api_key'], credentials['api_key_secret'], 
                credentials['access_token'], credentials['access_token_secret']]):
        logger.error("API credentials not found in environment variables!")
        print("Please set up your .env file with the required Twitter API credentials.")
    else:
        # Initialize the Twitter poster
        try:
            poster = TwitterPoster(credentials, logger, oauth_credentials)
            
            # Verify credentials
            if poster.verify_credentials():
                print("Twitter API credentials are valid.")
                
                # Uncomment to test posting a tweet
                # test_tweet = "This is a test tweet from the Twitter Automation Pipeline."
                # poster.post_tweet(test_tweet)
                
                # Uncomment to test video upload
                # video_path = "path/to/your/video.mp4"
                # media_id = poster.upload_video(video_path)
                # if media_id:
                #     poster.post_tweet("Check out this video!", [media_id])
                
                # Uncomment to start OAuth 2.0 web server
                # if poster.oauth_handler:
                #     poster.start_oauth_web_server(debug=True)
                
        except Exception as e:
            logger.error(f"Failed to initialize Twitter poster: {str(e)}") 