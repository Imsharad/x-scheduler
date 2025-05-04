"""
Main module for the X/Twitter Scheduler.

This module provides the entry point for the application.
"""
import argparse
import logging
import os
from .config import ConfigLoader
from .poster import TwitterPoster
from .scheduler import Scheduler
from .google_sheet_source import GoogleSheetSource
from .processor import ContentProcessor


def setup_logging():
    """
    Set up logging for the application.
    """
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'x_scheduler.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('x_scheduler')


def main():
    """
    Main entry point for the application.
    """
    parser = argparse.ArgumentParser(description='X/Twitter Scheduler')
    parser.add_argument('--setup-oauth', action='store_true', help='Start OAuth 2.0 web server for authorization')
    parser.add_argument('--run-once', action='store_true', help='Run the scheduler once and exit')
    parser.add_argument('--config', type=str, default='src/cfg/config.yaml', help='Path to configuration file')
    parser.add_argument('--post', type=str, help='Post a single tweet with the given text')
    parser.add_argument('--upload-video', type=str, help='Path to video file to upload')
    parser.add_argument('--video-tweet', type=str, help='Text to include with uploaded video. Required with --upload-video')
    parser.add_argument('--port', type=int, default=5000, help='Port for OAuth web server (default: 5000)')

    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging()
    logger.info("Starting X-Scheduler")
    
    # Load configuration
    config_loader = ConfigLoader(config_path=args.config)
    config = config_loader.config
    
    # Initialize Twitter poster
    twitter_credentials = config_loader.get_api_credentials()
    oauth_credentials = config_loader.get_oauth2_credentials()
    
    poster = TwitterPoster(twitter_credentials, logger, oauth_credentials)
    
    # Check if we need to start the OAuth 2.0 web server
    if args.setup_oauth:
        logger.info("Starting OAuth 2.0 web server for Twitter API authorization")
        poster.start_oauth_web_server(port=args.port, debug=True)
        return
    
    # Check if we need to post a single tweet
    if args.post:
        logger.info(f"Posting single tweet: {args.post}")
        result = poster.post_tweet(args.post)
        if result:
            logger.info(f"Tweet posted successfully! ID: {result.get('id')}")
        else:
            logger.error("Failed to post tweet.")
        return

    # Check if we need to upload a video and post a tweet with it
    if args.upload_video:
        if not args.video_tweet:
            logger.error("You must provide tweet text with --video-tweet when using --upload-video")
            return
            
        logger.info(f"Uploading video: {args.upload_video}")
        media_id = poster.upload_video(args.upload_video)
        
        if media_id:
            logger.info(f"Video uploaded successfully! Media ID: {media_id}")
            
            # Post tweet with video
            logger.info(f"Posting tweet with video: {args.video_tweet}")
            result = poster.post_tweet(args.video_tweet, [media_id])
            
            if result:
                logger.info(f"Tweet with video posted successfully! ID: {result.get('id')}")
            else:
                logger.error("Failed to post tweet with video.")
        else:
            logger.error("Failed to upload video.")
        return
    
    # Initialize Google Sheets content source
    logger.info("Initializing Google Sheets content source")
    source = GoogleSheetSource(
        credentials_file=config.get('google_sheet', {}).get('credentials_path'),
        sheet_id=config.get('google_sheet', {}).get('sheet_id'),
        worksheet_name=config.get('google_sheet', {}).get('worksheet_name', 'main'),
        logger=logger
    )
    
    # Initialize content processor
    processor = ContentProcessor(logger)
    
    # Initialize scheduler
    scheduler = Scheduler(
        poster=poster,
        source=source,
        processor=processor,
        config=config,
        logger=logger
    )
    
    # Start the scheduler
    if args.run_once:
        logger.info("Running scheduler once and exiting")
        scheduler.run_once()
    else:
        logger.info("Starting scheduler")
        scheduler.start()


if __name__ == "__main__":
    main() 