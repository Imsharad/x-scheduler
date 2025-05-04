"""
Configuration loader module.

This module handles loading configuration from .env files, config.yaml and AWS SSM Parameter Store.
"""
import os
import yaml
from dotenv import load_dotenv
from pathlib import Path
import boto3
import logging


class ConfigLoader:
    """
    Handles loading and accessing configuration from various sources.
    """
    
    def __init__(self, config_path=None, env_path=None, use_ssm=False):
        """
        Initialize the config loader.
        
        Args:
            config_path (str, optional): Path to the config YAML file.
                Defaults to 'src/cfg/config.yaml'.
            env_path (str, optional): Path to the .env file for local development.
                Defaults to '.env' in the project root.
            use_ssm (bool, optional): Whether to use AWS SSM Parameter Store for secrets.
                Defaults to False for local development, True for AWS deployment.
        """
        # Determine project root (parent of src)
        project_root = Path(__file__).resolve().parent.parent
        
        # Set default paths relative to project root if not provided
        if config_path is None:
            config_path = Path(__file__).resolve().parent / 'cfg' / 'config.yaml'
        else:
            config_path = Path(config_path)
            
        if env_path is None:
            env_path = project_root / '.env'
        else:
            env_path = Path(env_path)
            
        # For local development, load from .env file
        # For AWS deployment, we'll use SSM
        self.use_ssm = use_ssm
        if not use_ssm and env_path.exists():
            load_dotenv(dotenv_path=env_path)
        
        # Load config from YAML file
        try:
            with open(config_path, 'r') as file:
                self.config = yaml.safe_load(file)
        except Exception as e:
            logging.error(f"Error loading config from {config_path}: {e}")
            self.config = {}
            
    def get_ssm_parameter(self, name, default=None):
        """
        Get a parameter from AWS SSM Parameter Store.
        
        Args:
            name (str): Parameter name (without prefix)
            default: Default value if parameter not found
            
        Returns:
            str: Parameter value or default if not found
        """
        if not self.use_ssm:
            return default
            
        try:
            ssm_client = boto3.client('ssm')
            parameter_name = f"/x-scheduler/{name}"
            response = ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=True
            )
            return response['Parameter']['Value']
        except Exception as e:
            logging.error(f"Error retrieving parameter '{name}' from SSM: {e}")
            return default
            
    def get_api_credentials(self):
        """
        Get X API credentials from environment variables or SSM Parameter Store.
        
        Returns:
            dict: Dictionary containing API keys and tokens.
        """
        if self.use_ssm:
            # Get credentials from AWS SSM Parameter Store
            return {
                'api_key': self.get_ssm_parameter('api-key'),
                'api_key_secret': self.get_ssm_parameter('api-key-secret'),
                'access_token': self.get_ssm_parameter('access-token'),
                'access_token_secret': self.get_ssm_parameter('access-token-secret'),
                'bearer_token': self.get_ssm_parameter('bearer-token')
            }
        else:
            # Get credentials from environment variables (local development)
            return {
                'api_key': os.getenv('X_API_KEY'),
                'api_key_secret': os.getenv('X_API_KEY_SECRET'),
                'access_token': os.getenv('X_ACCESS_TOKEN'),
                'access_token_secret': os.getenv('X_ACCESS_TOKEN_SECRET'),
                'bearer_token': os.getenv('X_BEARER_TOKEN')
            }
    
    def get_oauth2_credentials(self):
        """
        Get OAuth 2.0 credentials for Twitter API from environment variables or SSM Parameter Store.
        
        Returns:
            dict: Dictionary containing OAuth 2.0 client credentials and settings.
        """
        if self.use_ssm:
            # Get credentials from AWS SSM Parameter Store
            return {
                'client_id': self.get_ssm_parameter('oauth-client-id'),
                'client_secret': self.get_ssm_parameter('oauth-client-secret'),
                'redirect_uri': self.get_ssm_parameter('oauth-redirect-uri', 'http://localhost:5000/callback'),
                'scopes': ['tweet.read', 'tweet.write', 'users.read', 'offline.access', 'media.write']
            }
        else:
            # Get credentials from environment variables (local development)
            return {
                'client_id': os.getenv('X_OAUTH_CLIENT_ID'),
                'client_secret': os.getenv('X_OAUTH_CLIENT_SECRET'),
                'redirect_uri': os.getenv('X_OAUTH_REDIRECT_URI', 'http://localhost:5000/callback'),
                'scopes': ['tweet.read', 'tweet.write', 'users.read', 'offline.access', 'media.write']
            }
    
    def get_content_source_config(self):
        """
        Get Google Sheets content source configuration.
        
        Returns:
            dict: Google Sheets content source configuration.
        """
        return {
            'source_type': 'google_sheet',
            'google_sheet': self.get_google_sheet_config()
        }
        
    def get_s3_config(self):
        """
        Get S3 configuration for video storage.
        
        Returns:
            dict: S3 configuration.
        """
        media_config = self.config.get('media', {})
        return {
            'bucket_name': media_config.get('s3_bucket', 'x-scheduler-video-uploads'),
            'delete_after_upload': media_config.get('delete_after_upload', True)
        }
    
    def get_google_sheet_config(self):
        """
        Get Google Sheets configuration from config file and environment variables.
        
        Returns:
            dict: Google Sheets configuration.
        """
        google_sheet_config = self.config.get('google_sheet', {})
        
        # Get credentials path from environment variable or config
        creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
        if not creds_path:
            creds_path = google_sheet_config.get('credentials_path')
            
        return {
            'sheet_id': google_sheet_config.get('sheet_id'),
            'worksheet_name': google_sheet_config.get('worksheet_name'),
            'credentials_path': creds_path
        }
    
    def get_schedule_config(self):
        """
        Get scheduling configuration.
        
        Returns:
            dict: Scheduling configuration.
        """
        schedule_config = self.config.get('schedule', {})
        
        # Convert new format to old format for backward compatibility
        if 'type' in schedule_config:
            schedule_type = schedule_config.get('type')
            
            # Create a compatible config dictionary
            result = {
                'mode': schedule_type  # 'interval' or 'specific_times'
            }
            
            if schedule_type == 'interval':
                result['interval_minutes'] = schedule_config.get('post_every_minutes', 240)
            
            if 'times_of_day' in schedule_config:
                result['specific_times'] = schedule_config.get('times_of_day', ['09:00', '17:00'])
            
            return result
        
        # If already in old format, return as-is
        return schedule_config
    
    def get_logging_config(self):
        """
        Get logging configuration.
        
        Returns:
            dict: Logging configuration.
        """
        log_config = self.config.get('logging', {})
        
        # Update log file path to new location
        if 'file_path' in log_config:
            default_path = 'src/log/pipeline.log'
            log_config['file_path'] = log_config.get('file_path', default_path)
            
            # If the path is relative to the old logs directory, update it
            if log_config['file_path'].startswith('logs/'):
                log_config['file_path'] = 'src/log/' + log_config['file_path'][5:]
                
        return log_config


# Create a default instance for easy importing
# Automatically use SSM when running on AWS (EC2 instance will have IAM role)
is_on_aws = 'AWS_EXECUTION_ENV' in os.environ or 'AWS_REGION' in os.environ
config = ConfigLoader(use_ssm=is_on_aws)


if __name__ == "__main__":
    # Test the config loader
    loader = ConfigLoader()
    print("API Credentials (Keys redacted):", {k: '***' if v else None for k, v in loader.get_api_credentials().items()})
    print("Content Source:", loader.get_content_source_config())
    print("Schedule Config:", loader.get_schedule_config()) 