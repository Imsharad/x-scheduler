"""
Video Validator Module.

This module provides functionality to validate video files to ensure they meet Twitter's requirements.
"""
import os
import json
import subprocess
from typing import Dict, Optional, Any, Tuple

class VideoValidator:
    """
    Validates video files to ensure they meet Twitter's requirements.
    """
    
    # Twitter video requirements
    ALLOWED_MIME_TYPES = ["video/mp4"]
    MAX_DURATION_SECONDS = 140  # Twitter allows up to 140 seconds
    MAX_SIZE_BYTES = 512 * 1024 * 1024  # 512 MB (Twitter limit)
    MIN_WIDTH = 32
    MAX_WIDTH = 1920
    MIN_HEIGHT = 32
    MAX_HEIGHT = 1080
    MIN_ASPECT_RATIO = 1 / 3  # Minimum aspect ratio (width/height)
    MAX_ASPECT_RATIO = 3      # Maximum aspect ratio (width/height)
    ALLOWED_FRAME_RATES = [24, 25, 30, 60]  # Common frame rates
    
    def __init__(self, strict_mode=False, logger=None):
        """
        Initialize the video validator.
        
        Args:
            strict_mode (bool): Whether to enforce strict validation rules
            logger: Logger instance
        """
        self.strict_mode = strict_mode
        self.logger = logger
    
    def validate(self, file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate a video file against Twitter's requirements.
        
        Args:
            file_path (str): Path to the video file
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (validation result, validation details)
        """
        if not os.path.exists(file_path):
            if self.logger:
                self.logger.error(f"File not found: {file_path}")
            return False, {"error": "File not found"}
        
        # Get file size
        file_size = os.path.getsize(file_path)
        if file_size > self.MAX_SIZE_BYTES:
            if self.logger:
                self.logger.error(f"File too large: {file_size} bytes (max: {self.MAX_SIZE_BYTES} bytes)")
            return False, {"error": "File too large"}
        
        # Get video metadata using ffprobe
        metadata = self._get_video_metadata(file_path)
        if not metadata:
            if self.logger:
                self.logger.error(f"Failed to get video metadata: {file_path}")
            return False, {"error": "Failed to get video metadata"}
        
        # Check if this is a video file
        video_stream = self._find_video_stream(metadata)
        if not video_stream:
            if self.logger:
                self.logger.error(f"No video stream found: {file_path}")
            return False, {"error": "No video stream found"}
        
        # Check video duration
        duration = float(video_stream.get("duration", 0))
        if duration > self.MAX_DURATION_SECONDS:
            if self.logger:
                self.logger.error(f"Video too long: {duration} seconds (max: {self.MAX_DURATION_SECONDS} seconds)")
            return False, {"error": "Video too long"}
        
        # Check video dimensions
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        
        if width < self.MIN_WIDTH or width > self.MAX_WIDTH:
            if self.logger:
                self.logger.error(f"Invalid width: {width} (min: {self.MIN_WIDTH}, max: {self.MAX_WIDTH})")
            return False, {"error": "Invalid width"}
        
        if height < self.MIN_HEIGHT or height > self.MAX_HEIGHT:
            if self.logger:
                self.logger.error(f"Invalid height: {height} (min: {self.MIN_HEIGHT}, max: {self.MAX_HEIGHT})")
            return False, {"error": "Invalid height"}
        
        # Check aspect ratio
        aspect_ratio = width / height if height > 0 else 0
        if aspect_ratio < self.MIN_ASPECT_RATIO or aspect_ratio > self.MAX_ASPECT_RATIO:
            if self.logger:
                self.logger.error(f"Invalid aspect ratio: {aspect_ratio} (min: {self.MIN_ASPECT_RATIO}, max: {self.MAX_ASPECT_RATIO})")
            if self.strict_mode:
                return False, {"error": "Invalid aspect ratio"}
            else:
                if self.logger:
                    self.logger.warning(f"Invalid aspect ratio: {aspect_ratio}, but continuing in non-strict mode")
        
        # Check frame rate in strict mode only
        if self.strict_mode:
            frame_rate_str = video_stream.get("r_frame_rate", "0/1")
            try:
                num, den = map(int, frame_rate_str.split('/'))
                frame_rate = num / den if den > 0 else 0
                
                # Check if frame rate is close to one of the allowed values
                if not any(abs(frame_rate - allowed) < 0.1 for allowed in self.ALLOWED_FRAME_RATES):
                    if self.logger:
                        self.logger.warning(f"Unusual frame rate: {frame_rate} fps")
            except (ValueError, ZeroDivisionError):
                if self.logger:
                    self.logger.warning(f"Could not parse frame rate: {frame_rate_str}")
        
        # All checks passed
        validation_details = {
            "size_bytes": file_size,
            "duration_seconds": duration,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "codec": video_stream.get("codec_name")
        }
        
        if self.logger:
            self.logger.info(f"Video validation successful: {file_path}")
            self.logger.debug(f"Validation details: {validation_details}")
        
        return True, validation_details
    
    def _get_video_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get video metadata using ffprobe.
        
        Args:
            file_path (str): Path to the video file
            
        Returns:
            Optional[Dict[str, Any]]: Video metadata or None if failed
        """
        try:
            # Check if ffprobe exists
            try:
                subprocess.run(["ffprobe", "-version"], capture_output=True, check=True, timeout=5)
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                if self.logger:
                    self.logger.error("ffprobe command not found or not working. Cannot validate video.")
                return None
            
            # Run ffprobe to get video metadata
            ffprobe_cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "stream=index,codec_type,codec_name,width,height,duration,r_frame_rate:format=duration",
                "-of", "json",
                file_path
            ]
            
            result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True, timeout=30)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            if self.logger:
                self.logger.error(f"ffprobe failed with code {e.returncode}: {e.stderr}")
            return None
        except json.JSONDecodeError as e:
            if self.logger:
                self.logger.error(f"Failed to parse ffprobe output: {e}")
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting video metadata: {str(e)}")
            return None
    
    def _find_video_stream(self, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find the primary video stream in the metadata.
        
        Args:
            metadata (Dict[str, Any]): Video metadata from ffprobe
            
        Returns:
            Optional[Dict[str, Any]]: Video stream data or None if not found
        """
        if not metadata or "streams" not in metadata:
            return None
        
        # Find the first video stream
        for stream in metadata["streams"]:
            if stream.get("codec_type") == "video":
                return stream
        
        return None 