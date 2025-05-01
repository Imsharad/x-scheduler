"""
File content source.

Reads tweet content from a CSV file.
"""
import csv
import os
from typing import List, Dict, Any
from pathlib import Path


class FileContentSource:
    """Content source from a CSV file."""
    
    def __init__(self, config, logger=None):
        """Initialize with config and logger."""
        self.config = config
        self.logger = logger
        
        # Get file path
        file_path = config.get('curated_content', {}).get('file_path', 'src/dat/curated_content.csv')
        
        if not os.path.isabs(file_path):
            # Resolve relative to project root
            project_root = Path(__file__).resolve().parent.parent
            file_path = project_root / file_path
            
        self.file_path = file_path
        
        if logger:
            logger.info(f"Using file: {self.file_path}")
        
        # Check if file exists
        if not os.path.exists(self.file_path):
            error_msg = f"File not found: {self.file_path}"
            if logger:
                logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
    def fetch_content(self) -> List[Dict[str, Any]]:
        """Get unposted content from CSV file."""
        items = []
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    # Skip if posted or missing tweet
                    if not row.get('tweet') or row.get('is_posted', '').lower() == 'true':
                        continue
                        
                    items.append({
                        'tweet': row.get('tweet', ''),
                        'content_type': 'curated'
                    })
                    
            if self.logger:
                self.logger.info(f"Found {len(items)} items to post")
                
            return items
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"CSV read error: {str(e)}")
            return []
                
    def mark_as_posted(self, item):
        """Mark item as posted in CSV file."""
        rows = []
        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                fieldnames = reader.fieldnames
                
                # Ensure is_posted column exists
                if 'is_posted' not in fieldnames:
                    fieldnames = fieldnames + ['is_posted']
                    
                for row in reader:
                    if row.get('tweet') == item.get('tweet'):
                        row['is_posted'] = 'true'
                    rows.append(row)
                    
            # Write updated file
            with open(self.file_path, 'w', encoding='utf-8', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
                
            if self.logger:
                self.logger.info(f"Marked as posted: {item.get('tweet')}")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"CSV update error: {str(e)}")
    
    def get_name(self) -> str:
        """Get source name."""
        return "FileContentSource" 