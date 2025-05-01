"""
Twitter Poster Module.

This module handles posting tweets to Twitter (X) using the Twitter API v2.
"""
import tweepy
import time
from typing import Dict, Optional
from .utils import retry


class TwitterPoster:
    """
    Handles posting tweets to Twitter (X) using the Twitter API.
    """
    
    def __init__(self, credentials, logger=None):
        """
        Initialize the Twitter poster with API credentials.
        
        Args:
            credentials (dict): Twitter API credentials.
            logger: Logger to use for logging.
        """
        self.logger = logger
        self.api_key = credentials.get('api_key')
        self.api_key_secret = credentials.get('api_key_secret')
        self.access_token = credentials.get('access_token')
        self.access_token_secret = credentials.get('access_token_secret')
        self.bearer_token = credentials.get('bearer_token')
        
        # Validate credentials
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
            
    @retry(max_tries=3, delay=5, backoff=2, exceptions=(tweepy.TweepyException,))
    def post_tweet(self, text: str) -> Optional[Dict]:
        """
        Post a tweet to Twitter.
        
        Args:
            text (str): Tweet text to post.
            
        Returns:
            dict: Response data from the Twitter API or None if failed.
        """
        if not text:
            if self.logger:
                self.logger.error("Cannot post empty tweet.")
            return None
        
        try:
            if self.logger:
                self.logger.info(f"Posting tweet: {text}")
                
            # Use Tweepy Client (API v2)
            response = self.client.create_tweet(text=text)
            
            tweet_id = response.data['id']
            tweet_url = f"https://twitter.com/user/status/{tweet_id}"
            
            if self.logger:
                self.logger.info(f"Tweet posted successfully. ID: {tweet_id}")
                self.logger.info(f"Tweet URL: {tweet_url}")
                
            return response.data
            
        except tweepy.TweepyException as e:
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                # Handle rate limits (status code 429)
                if status_code == 429:
                    if self.logger:
                        self.logger.warning("Rate limit exceeded. Waiting before retrying...")
                    # Wait for a while to respect rate limits
                    time.sleep(60)
                    raise  # Let the retry decorator handle it
                else:
                    error_msg = f"Twitter API error: {str(e)}, Status: {status_code}"
            else:
                error_msg = f"Twitter API error: {str(e)}"
                
            if self.logger:
                self.logger.error(error_msg)
                
            raise
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Unexpected error posting tweet: {str(e)}")
            return None
            
    def verify_credentials(self) -> bool:
        """
        Verify that the API credentials are valid.
        
        Returns:
            bool: True if credentials are valid, False otherwise.
        """
        try:
            # Use v1 API to verify credentials
            self.api.verify_credentials()
            
            if self.logger:
                self.logger.info("Twitter API credentials verified successfully.")
                
            return True
            
        except tweepy.TweepyException as e:
            if self.logger:
                self.logger.error(f"Invalid Twitter API credentials: {str(e)}")
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error verifying Twitter API credentials: {str(e)}")
            return False


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
    
    # Check if credentials are available
    if not all([credentials['api_key'], credentials['api_key_secret'], 
                credentials['access_token'], credentials['access_token_secret']]):
        logger.error("API credentials not found in environment variables!")
        print("Please set up your .env file with the required Twitter API credentials.")
    else:
        # Initialize the Twitter poster
        try:
            poster = TwitterPoster(credentials, logger)
            
            # Verify credentials
            if poster.verify_credentials():
                print("Twitter API credentials are valid.")
                
                # Uncomment to test posting a tweet
                # test_tweet = "This is a test tweet from the Twitter Automation Pipeline."
                # poster.post_tweet(test_tweet)
                
        except Exception as e:
            logger.error(f"Failed to initialize Twitter poster: {str(e)}") 