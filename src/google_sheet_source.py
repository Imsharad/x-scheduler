"""
Google Sheets content source.

Reads tweet content from a Google Sheet.
"""
import os
from typing import List, Dict, Any
from pathlib import Path

import gspread
from google.oauth2 import service_account


class GoogleSheetSource:
    """Content source from a Google Sheet."""
    
    def __init__(self, config, logger=None):
        """Initialize with config and logger."""
        self.config = config
        self.logger = logger
        
        # Get Google Sheet ID and worksheet name
        sheet_config = config.get('google_sheet', {})
        self.sheet_id = sheet_config.get('sheet_id')
        self.worksheet_name = sheet_config.get('worksheet_name')
        
        # Get credentials path
        creds_path = sheet_config.get('credentials_path')
        
        if not self.sheet_id:
            error_msg = "Google Sheet ID not provided in configuration."
            if logger:
                logger.error(error_msg)
            raise ValueError(error_msg)
            
        if not creds_path:
            error_msg = "Google credentials path not provided in configuration."
            if logger:
                logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Resolve relative path if needed
        if not os.path.isabs(creds_path):
            project_root = Path(__file__).resolve().parent.parent
            creds_path = project_root / creds_path
            
        # Check if credentials file exists
        if not os.path.exists(creds_path):
            error_msg = f"Credentials file not found: {creds_path}"
            if logger:
                logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # Initialize Google Sheets API
        try:
            scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
            credentials = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
            self.client = gspread.authorize(credentials)
            
            # Open the sheet and get the desired worksheet
            self.sheet = self.client.open_by_key(self.sheet_id)
            
            if self.worksheet_name:
                self.worksheet = self.sheet.worksheet(self.worksheet_name)
            else:
                # Use the first worksheet if none specified
                self.worksheet = self.sheet.get_worksheet(0)
                
            if logger:
                logger.info(f"Connected to Google Sheet: {self.sheet.title}, worksheet: {self.worksheet.title}")
                
        except Exception as e:
            error_msg = f"Failed to initialize Google Sheets API: {str(e)}"
            if logger:
                logger.error(error_msg)
            raise Exception(error_msg)
            
    def fetch_content(self) -> List[Dict[str, Any]]:
        """Get unposted content from Google Sheet."""
        items = []
        
        try:
            # Get all records (dict per row, with column names as keys)
            records = self.worksheet.get_all_records()
            
            for row in records:
                # Skip if posted or missing tweet
                if not row.get('tweet') or row.get('is_posted', '').lower() == 'true':
                    continue
                    
                items.append({
                    'tweet': row.get('tweet', ''),
                    'content_type': 'curated'
                })
                
            if self.logger:
                self.logger.info(f"Found {len(items)} items to post from Google Sheet.")
                
            return items
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Google Sheet read error: {str(e)}")
            return []
                
    def mark_as_posted(self, item):
        """Mark item as posted in Google Sheet."""
        try:
            # Find rows that match the tweet text
            tweet_text = item.get('tweet', '')
            if not tweet_text:
                if self.logger:
                    self.logger.warning("Cannot mark as posted: empty tweet text.")
                return
                
            # Get all records with their indexes
            all_values = self.worksheet.get_all_values()
            header = all_values[0]
            
            # Find tweet column and is_posted column
            try:
                tweet_col_idx = header.index('tweet')
                
                # Check if is_posted column exists
                try:
                    is_posted_col_idx = header.index('is_posted')
                except ValueError:
                    # Add is_posted column if it doesn't exist
                    is_posted_col_idx = len(header)
                    header.append('is_posted')
                    # Update header row
                    self.worksheet.update_cell(1, is_posted_col_idx + 1, 'is_posted')
                
                # Find the row(s) with the matching tweet
                for i, row in enumerate(all_values[1:], start=2):  # Start at 2 to account for 1-indexed cells and header row
                    if len(row) > tweet_col_idx and row[tweet_col_idx] == tweet_text:
                        # Update the is_posted cell to true
                        self.worksheet.update_cell(i, is_posted_col_idx + 1, 'true')
                        
                        if self.logger:
                            self.logger.info(f"Marked as posted in Google Sheet: {tweet_text}")
                        return
                
                if self.logger:
                    self.logger.warning(f"Tweet not found in Google Sheet: {tweet_text}")
                    
            except ValueError as e:
                if self.logger:
                    self.logger.error(f"Column not found in Google Sheet: {str(e)}")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Google Sheet update error: {str(e)}")
    
    def get_name(self) -> str:
        """Get source name."""
        return "GoogleSheetSource" 