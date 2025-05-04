"""
S3 Utilities Module.

This module provides utility functions for AWS S3 operations related to video handling.
"""
import os
import boto3
import uuid
import logging
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any


class S3Manager:
    """
    Handles AWS S3 operations for video storage.
    """
    
    def __init__(self, bucket_name: str, logger=None):
        """
        Initialize the S3 manager.
        
        Args:
            bucket_name (str): Name of the S3 bucket to use
            logger: Logger instance (optional)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3')
        
        # Ensure the bucket exists
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self) -> bool:
        """
        Check if the configured S3 bucket exists, create it if it doesn't.
        
        Returns:
            bool: True if bucket exists or was created, False otherwise
        """
        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            self.logger.info(f"S3 bucket '{self.bucket_name}' exists")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            
            # If bucket doesn't exist (404) or we don't have permission to check (403)
            if error_code == '404':
                try:
                    # Create the bucket
                    self.logger.info(f"Creating S3 bucket '{self.bucket_name}'")
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    return True
                except ClientError as ce:
                    self.logger.error(f"Failed to create S3 bucket '{self.bucket_name}': {str(ce)}")
                    return False
            else:
                self.logger.error(f"Error accessing S3 bucket '{self.bucket_name}': {str(e)}")
                return False
    
    def upload_file(self, local_file_path: str, s3_key: Optional[str] = None) -> Optional[str]:
        """
        Upload a file to S3.
        
        Args:
            local_file_path (str): Path to the local file
            s3_key (str, optional): S3 key to use. If not provided, one will be generated.
            
        Returns:
            str: S3 URI (s3://bucket-name/key) if successful, None otherwise
        """
        if not os.path.exists(local_file_path):
            self.logger.error(f"Local file not found: {local_file_path}")
            return None
            
        try:
            # Generate a unique key if not provided
            if not s3_key:
                file_ext = os.path.splitext(local_file_path)[1].lower()
                s3_key = f"videos/{str(uuid.uuid4())}{file_ext}"
                
            # Upload the file
            self.logger.info(f"Uploading file {local_file_path} to S3 {self.bucket_name}/{s3_key}")
            self.s3_client.upload_file(local_file_path, self.bucket_name, s3_key)
            
            # Return the S3 URI
            s3_uri = f"s3://{self.bucket_name}/{s3_key}"
            self.logger.info(f"File uploaded successfully to {s3_uri}")
            return s3_uri
            
        except ClientError as e:
            self.logger.error(f"Error uploading file to S3: {str(e)}")
            return None
    
    def download_file(self, s3_uri: str, local_file_path: Optional[str] = None) -> Optional[str]:
        """
        Download a file from S3.
        
        Args:
            s3_uri (str): S3 URI (s3://bucket-name/key)
            local_file_path (str, optional): Path where to save the file.
                If not provided, a temporary file will be created.
                
        Returns:
            str: Path to the downloaded file if successful, None otherwise
        """
        try:
            # Parse S3 URI
            if not s3_uri.startswith("s3://"):
                self.logger.error(f"Invalid S3 URI: {s3_uri}")
                return None
                
            s3_parts = s3_uri[5:].split('/', 1)
            if len(s3_parts) != 2:
                self.logger.error(f"Invalid S3 URI format: {s3_uri}")
                return None
                
            bucket = s3_parts[0]
            key = s3_parts[1]
            
            # If bucket doesn't match configured bucket, log a warning
            if bucket != self.bucket_name:
                self.logger.warning(
                    f"S3 URI bucket ({bucket}) does not match configured bucket ({self.bucket_name})"
                )
            
            # Generate a local file path if not provided
            if not local_file_path:
                file_ext = os.path.splitext(key)[1].lower()
                local_file_path = os.path.join('/tmp', f"{str(uuid.uuid4())}{file_ext}")
                
            # Ensure directory exists
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            
            # Download the file
            self.logger.info(f"Downloading file from S3 {s3_uri} to {local_file_path}")
            self.s3_client.download_file(bucket, key, local_file_path)
            
            self.logger.info(f"File downloaded successfully to {local_file_path}")
            return local_file_path
            
        except ClientError as e:
            self.logger.error(f"Error downloading file from S3: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error downloading file from S3: {str(e)}")
            return None
    
    def delete_file(self, s3_uri: str) -> bool:
        """
        Delete a file from S3.
        
        Args:
            s3_uri (str): S3 URI (s3://bucket-name/key)
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            # Parse S3 URI
            if not s3_uri.startswith("s3://"):
                self.logger.error(f"Invalid S3 URI: {s3_uri}")
                return False
                
            s3_parts = s3_uri[5:].split('/', 1)
            if len(s3_parts) != 2:
                self.logger.error(f"Invalid S3 URI format: {s3_uri}")
                return False
                
            bucket = s3_parts[0]
            key = s3_parts[1]
            
            # If bucket doesn't match configured bucket, log a warning
            if bucket != self.bucket_name:
                self.logger.warning(
                    f"S3 URI bucket ({bucket}) does not match configured bucket ({self.bucket_name})"
                )
            
            # Delete the file
            self.logger.info(f"Deleting file from S3: {s3_uri}")
            self.s3_client.delete_object(Bucket=bucket, Key=key)
            
            self.logger.info(f"File deleted successfully: {s3_uri}")
            return True
            
        except ClientError as e:
            self.logger.error(f"Error deleting file from S3: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error deleting file from S3: {str(e)}")
            return False
    
    def is_s3_uri(self, path: str) -> bool:
        """
        Check if a path is an S3 URI.
        
        Args:
            path (str): Path to check
            
        Returns:
            bool: True if path is an S3 URI, False otherwise
        """
        return path is not None and path.startswith("s3://") 