"""
Google Sheets content source.

This module provides functionality to fetch content from Google Sheets.
"""
import gspread
from google.oauth2.service_account import Credentials
import logging
import os
from pathlib import Path
from typing import List, Dict, Any


class GoogleSheetSource:
    """
    Fetch content from a Google Sheet.
    """
    
    def __init__(self, credentials_file=None, sheet_id=None, worksheet_name='main', logger=None):
        """
        Initialize the Google Sheets content source.
        
        Args:
            credentials_file (str): Path to the Google API credentials JSON file
            sheet_id (str): Google Sheet ID
            worksheet_name (str): Name of the worksheet to use
            logger: Logger instance (optional)
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Set required scopes
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        
        # Get credentials file path (from parameter or environment variable)
        self.credentials_file = credentials_file or os.environ.get('GOOGLE_CREDENTIALS_PATH')
        if not self.credentials_file:
            error_msg = "No Google credentials file provided"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Make sure the path is absolute
        if not os.path.isabs(self.credentials_file):
            project_root = Path(__file__).resolve().parent.parent
            self.credentials_file = project_root / self.credentials_file
            
        self.sheet_id = sheet_id
        if not self.sheet_id:
            error_msg = "No Google Sheet ID provided"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
            
        self.worksheet_name = worksheet_name
        
        # Check if credentials file exists
        if not os.path.exists(self.credentials_file):
            error_msg = f"Google credentials file not found: {self.credentials_file}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        # Initialize the Google Sheets client
        try:
            self._init_client()
        except Exception as e:
            error_msg = f"Failed to initialize Google Sheets client: {str(e)}"
            self.logger.error(error_msg)
            raise
    
    def _init_client(self):
        """
        Initialize the Google Sheets client.
        """
        try:
            # Authenticate with Google
            credentials = Credentials.from_service_account_file(
                self.credentials_file, 
                scopes=self.scopes
            )
            
            # Create client
            self.client = gspread.authorize(credentials)
            
            # Open the spreadsheet
            self.sheet = self.client.open_by_key(self.sheet_id)
            
            # Get the worksheet
            try:
                self.worksheet = self.sheet.worksheet(self.worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                self.logger.warning(f"Worksheet '{self.worksheet_name}' not found, using first worksheet")
                self.worksheet = self.sheet.get_worksheet(0)
                
            self.logger.info(f"Connected to Google Sheet: {self.sheet.title}, worksheet: {self.worksheet.title}")
            
        except Exception as e:
            self.logger.error(f"Error initializing Google Sheets client: {str(e)}")
            raise
    
    def fetch_content(self) -> List[Dict[str, Any]]:
        """
        Fetch content from the Google Sheet.
        
        Returns:
            List of content items as dictionaries
        """
        try:
            # Get all records from the worksheet
            records = self.worksheet.get_all_records()
            
            # Filter out items that have already been posted
            unposted_items = []
            for item in records:
                # Skip if missing tweet content or already posted
                if not item.get('tweet') or item.get('is_posted', '').lower() == 'true':
                    continue
                    
                # Create content item
                content_item = {
                    'tweet': item.get('tweet', ''),
                    'content_type': 'google_sheet',
                    'row_index': records.index(item) + 2  # +2 for header row and 0-indexing
                }
                
                # Add media_path if present
                if 'media_path' in item and item['media_path']:
                    content_item['media_path'] = item['media_path']
                    self.logger.info(f"Found media to upload: {item['media_path']}")
                
                # Add video_url if present
                if 'video_url' in item and item['video_url']:
                    content_item['video_url'] = item['video_url']
                    self.logger.info(f"Found video URL to download: {item['video_url']}")
                
                unposted_items.append(content_item)
            
            self.logger.info(f"Found {len(unposted_items)} unposted items in Google Sheet")
            return unposted_items
            
        except Exception as e:
            self.logger.error(f"Error fetching content from Google Sheet: {str(e)}")
            return []
    
    def mark_as_posted(self, item):
        """
        Mark an item as posted in the Google Sheet.
        
        Args:
            item: Content item to mark as posted
        """
        try:
            # Get the row index
            row_index = item.get('row_index')
            if not row_index:
                self.logger.error("Cannot mark item as posted: missing row_index")
                return
                
            # Update the is_posted column
            try:
                # Find the is_posted column
                headers = self.worksheet.row_values(1)
                if 'is_posted' not in headers:
                    # Add is_posted column if it doesn't exist
                    self.worksheet.update_cell(1, len(headers) + 1, 'is_posted')
                    is_posted_col = len(headers) + 1
                else:
                    is_posted_col = headers.index('is_posted') + 1
                    
                # Update the cell
                self.worksheet.update_cell(row_index, is_posted_col, 'true')
                self.logger.info(f"Marked item as posted in Google Sheet (row {row_index})")
                
            except Exception as e:
                self.logger.error(f"Error updating Google Sheet: {str(e)}")
                
        except Exception as e:
            self.logger.error(f"Error marking item as posted: {str(e)}")
    
    def get_name(self) -> str:
        """
        Get the name of this content source.
        
        Returns:
            str: Name of the content source
        """
        return "GoogleSheetSource" 