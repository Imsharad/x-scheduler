"""
Scheduler Module.

This module handles the scheduling of tweets based on the configured schedule.
"""
import schedule
import time
import os
import tempfile
from typing import Dict, Any, Optional, List, Tuple
from .s3_utils import S3Manager
from .video_downloader import VideoDownloader
from .video_validator import VideoValidator


class Scheduler:
    """
    Handles scheduling and execution of tweets.
    """
    
    def __init__(self, poster, source, processor, config, logger=None):
        """
        Initialize the scheduler.
        
        Args:
            poster: Twitter poster instance
            source: Content source instance
            processor: Content processor instance
            config: Configuration dictionary
            logger: Logger instance
        """
        self.poster = poster
        self.source = source
        self.processor = processor
        self.config = config
        self.logger = logger
        
        # Get scheduling configuration
        self.schedule_config = config.get('schedule', {})
        self.schedule_mode = self.schedule_config.get('mode', 'interval')
        self.schedule_interval = self.schedule_config.get('interval_minutes', 60)
        self.schedule_times = self.schedule_config.get('specific_times', [])
        
        # Initialize S3 manager
        media_config = config.get('media', {})
        s3_bucket = media_config.get('s3_bucket', 'x-scheduler-video-uploads')
        self.s3_manager = S3Manager(bucket_name=s3_bucket, logger=logger)
        
        # Initialize video downloader
        max_filesize_mb = int(media_config.get('max_size_bytes', 147483648) / (1024 * 1024))
        max_duration = media_config.get('max_duration_seconds', 140)
        self.video_downloader = VideoDownloader(
            max_filesize_mb=max_filesize_mb,
            max_duration_seconds=max_duration,
            logger=logger
        )
        
        # Initialize video validator
        self.video_validator = VideoValidator(
            strict_mode=media_config.get('strict_validation', False),
            logger=logger
        )
        
        # Flag to determine if we should delete videos from S3 after upload
        self.delete_after_upload = media_config.get('delete_after_upload', True)
        
        # Set up schedule
        self._setup_schedule()
        
    def _process_content_item(self, item):
        """
        Process a single content item and post it to Twitter.
        
        Args:
            item: Content item dictionary
            
        Returns:
            bool: True if posted successfully, False otherwise
        """
        try:
            # Process the content
            tweet_text = self.processor.process(item.get('tweet', ''))
            
            # Track temporary files that need to be cleaned up
            temp_files_to_cleanup = []
            # Track S3 URIs that need to be deleted after successful post
            s3_uris_to_cleanup = []
            
            # Flag to track if media was handled
            media_handled = False
            # Media ID from Twitter upload
            media_id = None
            
            try:
                # Check for media in this priority order:
                # 1. video_url (download from external source)
                # 2. media_path (could be local or S3 path)
                
                # Priority 1: Check if we have a video URL to download
                video_url = item.get('video_url')
                if video_url:
                    if self.logger:
                        self.logger.info(f"Found video URL to download: {video_url}")
                    
                    # Download the video
                    local_video_path = self.video_downloader.download_video(video_url)
                    if not local_video_path:
                        if self.logger:
                            self.logger.error(f"Failed to download video from URL: {video_url}")
                        return False
                    
                    # Add to cleanup list
                    temp_files_to_cleanup.append(local_video_path)
                    
                    # Upload to S3
                    s3_uri = self.s3_manager.upload_file(local_video_path)
                    if not s3_uri:
                        if self.logger:
                            self.logger.error(f"Failed to upload video to S3: {local_video_path}")
                        return False
                    
                    # Add to S3 cleanup list
                    s3_uris_to_cleanup.append(s3_uri)
                    
                    # Now download from S3 to ensure we have the latest version
                    # (This step might seem redundant but ensures consistent code flow)
                    local_video_path_from_s3 = self.s3_manager.download_file(s3_uri)
                    if not local_video_path_from_s3:
                        if self.logger:
                            self.logger.error(f"Failed to download video from S3: {s3_uri}")
                        return False
                    
                    # Add to cleanup list
                    temp_files_to_cleanup.append(local_video_path_from_s3)
                    
                    # Upload to Twitter
                    media_id = self._upload_media_to_twitter(local_video_path_from_s3)
                    media_handled = True
                    
                # Priority 2: Check if we have a media_path to process
                if not media_handled and item.get('media_path'):
                    media_path = item.get('media_path')
                    
                    if self.logger:
                        self.logger.info(f"Processing media path: {media_path}")
                    
                    # Check if this is an S3 URI
                    if self.s3_manager.is_s3_uri(media_path):
                        if self.logger:
                            self.logger.info(f"S3 URI detected: {media_path}")
                        
                        # Remember this S3 URI for potential cleanup
                        s3_uris_to_cleanup.append(media_path)
                        
                        # Download from S3
                        local_path = self.s3_manager.download_file(media_path)
                        if not local_path:
                            if self.logger:
                                self.logger.error(f"Failed to download media from S3: {media_path}")
                            return False
                        
                        # Add to cleanup list
                        temp_files_to_cleanup.append(local_path)
                        
                        # Upload to Twitter
                        media_id = self._upload_media_to_twitter(local_path)
                        media_handled = True
                        
                    else:
                        # Local file path
                        if not os.path.exists(media_path):
                            if self.logger:
                                self.logger.error(f"Media file not found: {media_path}")
                            return False
                        
                        # Upload to Twitter
                        media_id = self._upload_media_to_twitter(media_path)
                        media_handled = True
                
                # Post the tweet (with or without media)
                if media_id:
                    if self.logger:
                        self.logger.info(f"Posting tweet with media ID: {media_id}")
                    result = self.poster.post_tweet(tweet_text, [media_id])
                else:
                    if self.logger:
                        self.logger.info("Posting tweet without media")
                    result = self.poster.post_tweet(tweet_text)
                
                # Process result
                if result:
                    if self.logger:
                        self.logger.info(f"Posted tweet successfully: {tweet_text}")
                    
                    # Mark the item as posted in Google Sheets
                    self.source.mark_as_posted(item)
                    
                    # Clean up S3 if configured to do so
                    if self.delete_after_upload:
                        for s3_uri in s3_uris_to_cleanup:
                            if self.logger:
                                self.logger.info(f"Deleting video from S3: {s3_uri}")
                            self.s3_manager.delete_file(s3_uri)
                    
                    return True
                else:
                    if self.logger:
                        self.logger.error(f"Failed to post tweet: {tweet_text}")
                    return False
                    
            finally:
                # Always clean up temporary files
                for temp_file in temp_files_to_cleanup:
                    try:
                        if temp_file and os.path.exists(temp_file):
                            os.remove(temp_file)
                            if self.logger:
                                self.logger.debug(f"Removed temporary file: {temp_file}")
                    except Exception as e:
                        if self.logger:
                            self.logger.warning(f"Failed to remove temporary file {temp_file}: {str(e)}")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error processing content item: {str(e)}")
            return False
            
    def _upload_media_to_twitter(self, file_path):
        """
        Upload media to Twitter.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            str: Media ID if successful, None otherwise
        """
        try:
            # Determine media type based on file extension
            file_ext = os.path.splitext(file_path)[1].lower()
            media_type = None
            
            if file_ext in ['.mp4', '.mov']:
                media_type = 'video/mp4'
            elif file_ext in ['.png']:
                media_type = 'image/png'
            elif file_ext in ['.jpg', '.jpeg']:
                media_type = 'image/jpeg'
            elif file_ext in ['.gif']:
                media_type = 'image/gif'
            else:
                if self.logger:
                    self.logger.error(f"Unsupported media format: {file_ext}")
                return None
            
            # For video content, use the chunked upload process
            if media_type.startswith('video/'):
                if self.logger:
                    self.logger.info(f"Uploading video to Twitter: {file_path}")
                
                # Use default user for OAuth token
                user_id = self.config.get('oauth', {}).get('default_user_id', 'default_user')
                
                # Upload the video
                media_id = self.poster.upload_video(
                    file_path=file_path,
                    media_type=media_type,
                    user_id=user_id
                )
                
                if not media_id:
                    if self.logger:
                        self.logger.error(f"Failed to upload video to Twitter: {file_path}")
                    return None
                
                return media_id
                
            else:
                # For future implementation of image upload
                if self.logger:
                    self.logger.warning(f"Image upload not yet implemented: {file_path}")
                return None
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error uploading media to Twitter: {str(e)}")
            return None
            
    def _setup_schedule(self):
        """
        Set up the posting schedule based on configuration.
        """
        if self.schedule_mode == 'interval':
            # Schedule at regular intervals
            if self.logger:
                self.logger.info(f"Setting up schedule to post every {self.schedule_interval} minutes")
                
            schedule.every(self.schedule_interval).minutes.do(self.post_scheduled_tweet)
            
        elif self.schedule_mode == 'specific_times':
            # Schedule at specific times
            if self.logger:
                self.logger.info(f"Setting up schedule to post at specific times: {', '.join(self.schedule_times)}")
                
            for post_time in self.schedule_times:
                schedule.every().day.at(post_time).do(self.post_scheduled_tweet)
                
        else:
            if self.logger:
                self.logger.warning(f"Unknown schedule mode: {self.schedule_mode}. Using default interval of 60 minutes")
                
            schedule.every(60).minutes.do(self.post_scheduled_tweet)
    
    def post_scheduled_tweet(self):
        """
        Post a scheduled tweet.
        
        Returns:
            bool: True if posted successfully, False otherwise
        """
        if self.logger:
            self.logger.info("Running scheduled tweet post")
            
        try:
            # Get content from Google Sheets
            content_items = self.source.fetch_content()
            
            if not content_items:
                if self.logger:
                    self.logger.warning("No content available for posting")
                return False
                
            # Get the first item that hasn't been posted yet
            content_item = content_items[0]
            
            # Process and post the content
            success = self._process_content_item(content_item)
            
            return success
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error posting scheduled tweet: {str(e)}")
            return False
    
    def run_once(self):
        """
        Run the scheduler once and exit.
        """
        if self.logger:
            self.logger.info("Running scheduler once")
            
        return self.post_scheduled_tweet()
    
    def start(self):
        """
        Start the scheduler and run continuously.
        """
        if self.logger:
            self.logger.info("Starting scheduler. Press Ctrl+C to exit")
            
        # Run the scheduler loop
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                if self.logger:
                    self.logger.info("Scheduler stopped by user")
                break
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(60)  # Sleep longer on error to avoid rapid retries 