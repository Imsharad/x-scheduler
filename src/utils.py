"""
Utility functions for the Twitter automation pipeline.

This module provides utility functions for logging, retry logic, etc.
"""
import logging
import time
import functools
import os
from pathlib import Path
import subprocess
import json
from math import gcd
import requests
from datetime import datetime, timezone


def setup_logging(log_file=None, log_level=None):
    """
    Set up logging configuration.
    
    Args:
        log_file (str, optional): Path to the log file.
        log_level (str, optional): Logging level (DEBUG, INFO, etc.).
            Defaults to DEBUG.
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    # Determine project root
    project_root = Path(__file__).resolve().parent.parent
    
    # Set defaults if not provided
    if log_file is None:
        log_file = Path(__file__).resolve().parent / 'log' / 'pipeline.log'
    else:
        log_file = Path(log_file)
        
    # Create log directory if it doesn't exist
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Set default log level if not provided or invalid
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'DEBUG')
        
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.DEBUG)
    
    # Configure logging
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('twitter_automation')


def retry(max_tries=3, delay=1, backoff=2, exceptions=(Exception,), logger=None):
    """
    Retry decorator with exponential backoff, handling 429 rate limits specifically.

    Args:
        max_tries (int): Maximum number of retry attempts.
        delay (int): Initial delay between retries in seconds (used for non-429 errors).
        backoff (int): Backoff multiplier (used for non-429 errors).
        exceptions (tuple): Exceptions to catch and retry on (excluding HTTPError 429 handled separately).
        logger (logging.Logger, optional): Logger to use for logging retries.

    Returns:
        function: Decorated function with retry logic.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = max_tries, delay

            # Use default logger if not provided
            _logger = logger if logger else globals().get('logger')
            if not _logger: # Fallback if global logger isn't set up yet
                 _logger = logging.getLogger('twitter_automation_retry')
                 _logger.warning("Global logger not found in retry decorator, using temporary one.")


            while mtries > 0:
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.HTTPError as e:
                    mtries -= 1
                    if mtries == 0:
                        _logger.error(f"{func.__name__} failed after {max_tries} tries due to HTTPError: {e.response.status_code} {e.response.reason}. Response: {e.response.text}")
                        raise

                    wait_time = mdelay # Default wait time is exponential backoff

                    if e.response.status_code == 429:
                        _logger.warning(f"{func.__name__} hit rate limit (429).")
                        # Try to use the reset header
                        reset_header = e.response.headers.get('x-ratelimit-reset')
                        if reset_header:
                            try:
                                reset_timestamp = int(reset_header)
                                reset_dt = datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)
                                now_dt = datetime.now(timezone.utc)
                                wait_time_from_header = (reset_dt - now_dt).total_seconds()

                                if wait_time_from_header > 0:
                                    # Add a small buffer (e.g., 1 second)
                                    wait_time = wait_time_from_header + 1
                                    _logger.warning(f"Rate limit reset at {reset_dt.isoformat()}. Waiting for {wait_time:.2f} seconds.")
                                else:
                                    # Reset time is in the past, try immediate retry or minimal delay
                                    wait_time = 1 # Use a small delay
                                    _logger.warning(f"Rate limit reset time {reset_dt.isoformat()} is in the past. Retrying after {wait_time} second.")

                            except (ValueError, TypeError) as parse_err:
                                _logger.warning(f"Could not parse 'x-ratelimit-reset' header ('{reset_header}'): {parse_err}. Falling back to exponential backoff ({wait_time}s).")
                                # Fallback to exponential backoff handled below
                        else:
                            _logger.warning(f"'x-ratelimit-reset' header not found. Falling back to exponential backoff ({wait_time}s).")
                            # Fallback to exponential backoff handled below
                    else:
                        # For other HTTP errors, use standard exponential backoff
                         _logger.warning(f"{func.__name__} failed with HTTPError {e.response.status_code}, retrying in {wait_time}s... ({max_tries - mtries}/{max_tries})")


                    time.sleep(wait_time)
                    # Only apply exponential backoff if we didn't calculate from header or for non-429 errors
                    if e.response.status_code != 429 or not reset_header:
                         mdelay *= backoff


                except exceptions as e:
                    mtries -= 1
                    if mtries == 0:
                        _logger.error(f"{func.__name__} failed after {max_tries} tries with {type(e).__name__}: {str(e)}")
                        raise

                    _logger.warning(f"{func.__name__} failed with {type(e).__name__}, retrying in {mdelay}s... ({max_tries - mtries}/{max_tries})")
                    time.sleep(mdelay)
                    mdelay *= backoff

            # This part should ideally not be reached if max_tries > 0
            # If it is reached (e.g., max_tries=0 initially), call the function once.
            return func(*args, **kwargs)
        return wrapper
    return decorator


def create_file_if_not_exists(file_path):
    """
    Create a file if it doesn't exist.
    
    Args:
        file_path (str or Path): Path to the file to create.
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not file_path.exists():
        file_path.touch()


def get_video_metadata(video_path):
    """
    Gets video metadata using ffprobe.

    Args:
        video_path (str): The path to the video file.

    Returns:
        dict: A dictionary containing video metadata (streams, format).
              Returns an empty dict if ffprobe fails or file not found.
    """
    if not os.path.exists(video_path):
        logger.error(f"Metadata Error: Video file not found at {video_path}")
        return {}

    try:
        # Check for ffprobe existence silently for this getter function
        try:
            subprocess.run(["ffprobe", "-version"], capture_output=True, check=True, text=True, timeout=5)
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
             logger.error("ffprobe command not found or not working. Cannot get video metadata.")
             return {}

        ffprobe_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name,profile,width,height,pix_fmt,duration,r_frame_rate,avg_frame_rate,bit_rate,has_b_frames,closed_gop,field_order,channels,channel_layout:format=size,duration,bit_rate",
            "-of", "json",
            video_path
        ]
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True, timeout=30)
        metadata = json.loads(result.stdout)
        logger.debug(f"Successfully retrieved metadata for {video_path}")
        return metadata

    except subprocess.CalledProcessError as e:
        logger.error(f"ffprobe failed for {video_path}: {e.stderr}")
        return {}
    except subprocess.TimeoutExpired:
        logger.error(f"ffprobe timed out for {video_path}")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Failed to parse ffprobe JSON output for {video_path}")
        return {}
    except Exception as e:
        logger.error(f"An unexpected error occurred getting metadata for {video_path}: {e}")
        return {}


def validate_video_for_twitter(video_path, metadata=None):
    """
    Validates a video file against Twitter's specifications using ffprobe metadata.

    Requires ffprobe (part of FFmpeg) to be installed and in the system PATH.

    Args:
        video_path (str): The path to the video file (used for context in logs).
        metadata (dict, optional): Pre-fetched metadata from get_video_metadata.
                                   If None, it will be fetched internally.

    Returns:
        tuple: (bool, str) indicating if the video is valid and a message.
               Returns (True, "Valid") if compliant, or (False, "Reason for failure") if not.
    """
    if metadata is None:
        metadata = get_video_metadata(video_path)
        if not metadata:
            # get_video_metadata logs the error
            return False, f"Validation Error: Could not retrieve metadata for {video_path}"

    # --- Extract streams and format info ---
    video_streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
    audio_streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "audio"]
    format_info = metadata.get("format", {})

    if not video_streams:
        return False, "Validation Error: No video stream found in metadata."
    video_info = video_streams[0] # Use the first video stream

    audio_info = {}
    if audio_streams:
        audio_info = audio_streams[0] # Use the first audio stream
        logger.debug(f"Audio stream found: {audio_info.get('codec_name')}")
    else:
        logger.info(f"No audio stream found for {video_path}. This is acceptable by Twitter.")


    # --- Start Validation Checks ---
    logger.info(f"Starting validation for {video_path} using provided metadata.")
    # logger.debug(f"Video Info: {video_info}")
    # logger.debug(f"Audio Info: {audio_info}")
    # logger.debug(f"Format Info: {format_info}")

    # 1. File Size (Max 512 MB)
    max_size_bytes = 512 * 1024 * 1024
    file_size_str = format_info.get("size")
    if file_size_str:
        try:
            file_size = int(file_size_str)
            if file_size > max_size_bytes:
                return False, f"Validation Error: File size ({file_size / (1024*1024):.2f} MB) exceeds 512 MB limit."
            logger.debug(f"File size check passed: {file_size / (1024*1024):.2f} MB")
        except ValueError:
             logger.warning(f"Could not parse file size '{file_size_str}' from metadata.")
             # Cannot definitively fail here, but log it
    else:
        logger.warning("File size not found in format metadata.")
         # Cannot definitively fail here


    # 2. Duration (Min 0.5s, Max 140s)
    min_duration = 0.5
    max_duration = 140.0
    duration_str = video_info.get("duration") or format_info.get("duration") # Check stream then format
    if duration_str:
        try:
            duration = float(duration_str)
            if not (min_duration <= duration <= max_duration):
                return False, f"Validation Error: Duration ({duration:.2f}s) must be between {min_duration}s and {max_duration}s."
            logger.debug(f"Duration check passed: {duration:.2f}s")
        except ValueError:
            logger.warning(f"Could not parse duration '{duration_str}' from metadata.")
            # Cannot definitively fail here
    else:
        logger.warning("Duration not found in video stream or format metadata.")
        # Cannot definitively fail here


    # 3. Dimensions (Min 32x32, Max 1280x1024 or 1024x1280)
    min_dim = 32
    max_width = 1920 # Increased based on current Twitter docs (was 1280)
    max_height = 1200 # Increased based on current Twitter docs (was 1024)
    width = video_info.get("width")
    height = video_info.get("height")
    if width is not None and height is not None:
        try:
            width, height = int(width), int(height)
            if width < min_dim or height < min_dim:
                return False, f"Validation Error: Dimensions ({width}x{height}) must be at least {min_dim}x{min_dim}."
            # Twitter docs state max width/height, implies aspect ratio isn't strictly limited beyond this anymore
            if width > max_width or height > max_height:
                 return False, f"Validation Error: Dimensions ({width}x{height}) exceed maximum allowed ({max_width}x{max_height})."
            # Old check: if not ((width <= 1280 and height <= 1024) or (width <= 1024 and height <= 1280)):
            #    return False, f"Validation Error: Dimensions ({width}x{height}) must be within 1280x1024 or 1024x1280."
            logger.debug(f"Dimensions check passed: {width}x{height}")
        except ValueError:
            logger.warning(f"Could not parse width '{width}' or height '{height}'.")
             # Cannot definitively fail here
    else:
        logger.warning("Width or height not found in video stream metadata.")
        # Cannot definitively fail here


    # 4. Aspect Ratio (Between 1:3 and 3:1) - Less strict now, but good heuristic
    min_aspect = 1 / 3.0
    max_aspect = 3.0
    if width is not None and height is not None and height != 0: # Avoid division by zero
         try:
             width, height = int(width), int(height) # Ensure they are ints again
             aspect_ratio = width / height
             if not (min_aspect <= aspect_ratio <= max_aspect):
                 # Warning instead of failure, as Twitter seems more flexible now
                 logger.warning(f"Aspect ratio ({aspect_ratio:.2f}) is outside the recommended 1:3 to 3:1 range.")
                 # return False, f"Validation Error: Aspect ratio ({aspect_ratio:.2f}) must be between 1:3 ({min_aspect:.2f}) and 3:1 ({max_aspect:.2f})."
             else:
                  logger.debug(f"Aspect ratio check passed: {aspect_ratio:.2f}")
         except ValueError:
             pass # Already warned above


    # 5. Frame Rate (Max 60 FPS)
    max_fps = 60.0
    frame_rate_str = video_info.get("r_frame_rate") # Real frame rate preferred
    if not frame_rate_str or frame_rate_str == "0/0":
        frame_rate_str = video_info.get("avg_frame_rate") # Fallback to average

    if frame_rate_str and "/" in frame_rate_str:
        try:
            num, den = map(int, frame_rate_str.split('/'))
            if den != 0:
                frame_rate = num / den
                if frame_rate > max_fps:
                    return False, f"Validation Error: Frame rate ({frame_rate:.2f} FPS) exceeds {max_fps} FPS limit."
                logger.debug(f"Frame rate check passed: {frame_rate:.2f} FPS")
            else:
                logger.warning(f"Invalid frame rate format '{frame_rate_str}'.")
        except ValueError:
            logger.warning(f"Could not parse frame rate '{frame_rate_str}'.")
            # Cannot definitively fail here
    else:
        logger.warning(f"Frame rate not found or in unexpected format in metadata ('{frame_rate_str}').")
        # Cannot definitively fail here


    # 6. Video Codec (H264 High Profile)
    codec_name = video_info.get("codec_name")
    profile = video_info.get("profile")
    if codec_name != "h264":
        return False, f"Validation Error: Video codec must be H264, but found '{codec_name}'."
    if profile and "High" not in profile: # Be slightly lenient ("High", "High 4:4:4 Predictive")
        logger.warning(f"Video profile is '{profile}'. Twitter strongly prefers 'High Profile'. Upload might fail.")
        # return False, f"Validation Error: Video profile must be High Profile, but found '{profile}'."
    logger.debug(f"Video codec check passed: {codec_name} {profile}")


    # 7. Pixel Format (yuv420p)
    pix_fmt = video_info.get("pix_fmt")
    if pix_fmt != "yuv420p":
         # Warning instead of failure, Twitter *might* transcode others like yuvj420p
         logger.warning(f"Pixel format is '{pix_fmt}'. Twitter prefers 'yuv420p'. Upload might fail or require transcoding.")
         # return False, f"Validation Error: Pixel format must be yuv420p, but found '{pix_fmt}'."
    else:
        logger.debug("Pixel format check passed: yuv420p")


    # 8. Audio Codec (AAC LC)
    if audio_info: # Only check if audio exists
        audio_codec = audio_info.get("codec_name")
        audio_profile = audio_info.get("profile")
        # Twitter docs specify "AAC", be more specific with "AAC LC" (Low Complexity)
        if audio_codec != "aac":
            return False, f"Validation Error: Audio codec must be AAC, but found '{audio_codec}'."
        if audio_profile and audio_profile != "LC":
            logger.warning(f"Audio profile is '{audio_profile}'. Twitter prefers 'LC' (Low Complexity).")
            # return False, f"Validation Error: Audio profile must be LC (Low Complexity), but found '{audio_profile}'."
        logger.debug(f"Audio codec check passed: {audio_codec} {audio_profile}")

        # 9. Audio Channels (Stereo or Mono)
        channels = audio_info.get("channels")
        channel_layout = audio_info.get("channel_layout")
        if channels is not None:
            try:
                channels = int(channels)
                if channels > 2:
                     return False, f"Validation Error: Audio must be Stereo (2 channels) or Mono (1 channel), but found {channels} channels."
                logger.debug(f"Audio channels check passed: {channels}")
            except ValueError:
                logger.warning(f"Could not parse audio channels '{channels}'.")
        elif channel_layout: # Fallback check on layout string
            if channel_layout not in ("mono", "stereo"):
                logger.warning(f"Audio channel layout is '{channel_layout}'. Recommend 'mono' or 'stereo'.")
                # return False, f"Validation Error: Audio channel layout must be mono or stereo, but found '{channel_layout}'."
            else:
                 logger.debug(f"Audio channel layout check passed: {channel_layout}")
        else:
            logger.warning("Audio channels/layout not found in audio stream metadata.")


    # 10. Closed GOP & Progressive Scan (No Interlacing)
    closed_gop_str = video_info.get("closed_gop") # Group of Pictures
    field_order = video_info.get("field_order") # For interlacing detection

    # closed_gop=1 means closed GOPs. Twitter wants this.
    if closed_gop_str is not None:
         try:
             closed_gop = int(closed_gop_str)
             if closed_gop == 0:
                 logger.warning("Video GOP is not closed. Twitter prefers closed GOP.")
                 # return False, "Validation Error: Video must have closed GOP."
             else:
                 logger.debug("Closed GOP check passed.")
         except ValueError:
              logger.warning(f"Could not parse closed_gop value '{closed_gop_str}'.")
    else:
         logger.warning("closed_gop information not found in metadata.")


    if field_order and field_order != "progressive":
        return False, f"Validation Error: Video must be progressive scan, not interlaced (found field order: '{field_order}')."
    logger.debug("Progressive scan check passed.")


    # 11. Must not have edit lists (moov atom at the beginning) - Hard to check reliably with ffprobe alone.
    # This is usually ensured by encoders like ffmpeg with `-movflags +faststart`.
    # We'll skip this check here as it's complex and often implicitly handled.
    logger.debug("Skipping edit list / moov atom check (assumed handled by encoding).")

    logger.info(f"Validation successful for {video_path}")
    return True, "Valid"


if __name__ == "__main__":
    # Test logging setup
    logger = setup_logging()
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message") 