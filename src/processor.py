"""
Content Processor Module.

This module handles the processing of tweet content.
"""
import logging


class ContentProcessor:
    """
    Process content for tweets.
    """
    
    def __init__(self, logger=None):
        """
        Initialize the content processor.
        
        Args:
            logger: Logger instance (optional)
        """
        self.logger = logger or logging.getLogger(__name__)
    
    def process(self, text):
        """
        Process tweet text.
        
        Args:
            text (str): Raw tweet text
            
        Returns:
            str: Processed tweet text
        """
        # Currently just returns the text as-is
        # Can be expanded to add hashtags, format links, etc.
        if not text:
            return ""
            
        # Truncate if over Twitter limit (280 characters)
        if len(text) > 280:
            if self.logger:
                self.logger.warning(f"Tweet text too long ({len(text)} chars), truncating to 280 chars")
            return text[:277] + "..."
            
        return text 