"""
Scheduler Module.

This module handles the scheduling of tweets based on the configured schedule.
"""
import schedule
import time
import random
import datetime
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from .config import config
from .utils import setup_logging, create_file_if_not_exists
from .source import FileContentSource
from .google_sheet_source import GoogleSheetSource
from .processor import ContentProcessor
from .poster import TwitterPoster


class TweetScheduler:
    """
    Manages scheduling and posting of tweets.
    """
    
    def __init__(self, debug=False):
        """
        Initialize the tweet scheduler.
        """
        # Set up logging based on debug flag
        log_config = config.get_logging_config()
        log_level = 'DEBUG' if debug else log_config.get('level')
        self.logger = setup_logging(log_config.get('file_path'), log_level)
        
        self.logger.info("Initializing Tweet Scheduler...")
        
        # Load config
        self.content_source_config = config.get_content_source_config()
        self.schedule_config = config.get_schedule_config()
        
        # Initialize components
        self._init_components()
        
        # Set up schedule
        self._setup_schedule()
        
        self.logger.info("Tweet Scheduler initialized successfully.")
        
    def _create_content_source(self):
        """
        Create and return the appropriate content source based on configuration.
        """
        source_type = self.content_source_config.get('source_type', 'file')
        
        if source_type == 'google_sheet':
            self.logger.info("Using Google Sheets content source")
            return GoogleSheetSource(self.content_source_config, self.logger)
        else:
            self.logger.info("Using file content source")
            return FileContentSource(self.content_source_config, self.logger)
        
    def _init_components(self):
        """
        Initialize content sources, processor, and poster.
        """
        # Initialize content source (file or Google Sheets)
        self.content_source = self._create_content_source()
        
        # Initialize content processor
        self.processor = ContentProcessor(logger=self.logger)
        
        # Initialize Twitter poster
        try:
            self.twitter_poster = TwitterPoster(config.get_api_credentials(), self.logger)
            
            # Verify credentials
            if not self.twitter_poster.verify_credentials():
                self.logger.error("Failed to verify Twitter API credentials. Please check your .env file.")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Twitter poster: {str(e)}")
            self.twitter_poster = None
            
    def _setup_schedule(self):
        """
        Set up the posting schedule based on configuration.
        """
        mode = self.schedule_config.get('mode', 'interval')
        
        if mode == 'interval':
            # Schedule at regular intervals
            interval_minutes = self.schedule_config.get('interval_minutes', 240)  # Default to 4 hours
            
            self.logger.info(f"Setting up schedule to post every {interval_minutes} minutes.")
            
            # Schedule the tweet job
            schedule.every(interval_minutes).minutes.do(self.post_scheduled_tweet)
            
        elif mode == 'specific_times':
            # Schedule at specific times
            times = self.schedule_config.get('specific_times', ['09:00', '17:00'])
            
            self.logger.info(f"Setting up schedule to post at specific times: {', '.join(times)}")
            
            # Schedule the tweet job at each specified time
            for post_time in times:
                schedule.every().day.at(post_time).do(self.post_scheduled_tweet)
                
        else:
            self.logger.error(f"Unknown schedule mode: {mode}. Using default interval of 4 hours.")
            schedule.every(240).minutes.do(self.post_scheduled_tweet)
        
    def get_content(self) -> Optional[Dict[str, Any]]:
        """
        Get content from the configured source. Already filters based on 'is_posted' flag.
        
        Returns:
            dict: A content item to tweet, or None if no suitable content found.
        """
        self.logger.info("Fetching content for posting...")
        
        # Get content from source
        all_content = []
        
        try:
            # Get content from configured source
            source_content = self.content_source.fetch_content()
            all_content.extend(source_content)
            
            source_name = self.content_source.get_name()
            self.logger.info(f"Fetched {len(all_content)} new items from {source_name}.")
            
        except Exception as e:
            self.logger.error(f"Error fetching content: {str(e)}")
            
        # If no content available, return None
        if not all_content:
            self.logger.warning("No new content available for posting.")
            return None
            
        # Select a random content item
        selected_item = random.choice(all_content)
        
        self.logger.info(f"Selected content: {selected_item.get('tweet')}")
        return selected_item
        
    def post_scheduled_tweet(self) -> bool:
        """
        Post a scheduled tweet and mark it as posted in the source.
        
        Returns:
            bool: True if tweet was posted successfully, False otherwise.
        """
        self.logger.info("Running scheduled tweet posting...")
        
        try:
            # Get content
            content_item = self.get_content()
            
            if not content_item:
                self.logger.warning("No content available for posting. Skipping this scheduled tweet.")
                return False
                
            # Process content into a tweet
            tweet_text = self.processor.process_content(content_item)
            
            # Post tweet
            if self.twitter_poster:
                result = self.twitter_poster.post_tweet(tweet_text)
                
                if result:
                    # Mark as posted in the source upon successful posting
                    try:
                        self.content_source.mark_as_posted(content_item)
                        self.logger.info("Tweet posted successfully and marked as posted in source.")
                        return True
                    except Exception as e:
                        # Log error but consider the tweet posted
                        self.logger.error(f"Tweet posted successfully, but failed to mark as posted in source: {str(e)}")
                        return True # Tweet was still posted
                else:
                    self.logger.error("Failed to post tweet.")
                    return False
            else:
                self.logger.error("Twitter poster is not initialized. Cannot post tweet.")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in scheduled tweet posting: {str(e)}")
            return False
            
    def run(self):
        """
        Run the scheduler continuously.
        """
        self.logger.info("Starting tweet scheduler. Press Ctrl+C to exit.")
        
        # Post a tweet immediately on startup (optional)
        try:
            self.post_scheduled_tweet()
        except Exception as e:
            self.logger.error(f"Error posting initial tweet: {str(e)}")
        
        # Run the scheduler continuously
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                self.logger.info("Scheduler stopped by user.")
                break
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {str(e)}")
                # Sleep a bit longer to avoid hammering in case of persistent errors
                time.sleep(60)


def main():
    """
    Main entry point for the scheduler.
    """
    scheduler = TweetScheduler()
    scheduler.run()


if __name__ == "__main__":
    main() 