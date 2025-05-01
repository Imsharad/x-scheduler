"""
Content processor.

Processes tweet content.
"""


class ContentProcessor:
    """Processes content items into tweets."""
    
    def __init__(self, config=None, logger=None):
        """Initialize processor."""
        self.logger = logger
        
    def process_content(self, content_item):
        """Get tweet text from content item."""
        tweet = content_item.get('tweet', '')
        
        if self.logger and tweet:
            self.logger.debug(f"Processing: {tweet}")
            
        return tweet 