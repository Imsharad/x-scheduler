"""
Video Downloader Module.

This module provides functionality to download videos from various platforms using yt-dlp.
"""
import os
import uuid
import logging
import subprocess
import tempfile
from typing import Optional, Dict, Any, Tuple


class VideoDownloader:
    """
    Handles downloading videos from various platforms using yt-dlp.
    """
    
    def __init__(self, max_filesize_mb: int = 140, max_duration_seconds: int = 140, logger=None):
        """
        Initialize the video downloader.
        
        Args:
            max_filesize_mb (int): Maximum filesize in MB for downloaded videos
            max_duration_seconds (int): Maximum duration in seconds for downloaded videos
            logger: Logger instance (optional)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.max_filesize_mb = max_filesize_mb
        self.max_duration_seconds = max_duration_seconds
        
        # Check if yt-dlp is installed
        self._check_ytdlp_installed()
    
    def _check_ytdlp_installed(self) -> bool:
        """
        Check if yt-dlp is installed.
        
        Returns:
            bool: True if installed, False otherwise
        """
        try:
            result = subprocess.run(
                ["yt-dlp", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                self.logger.info(f"yt-dlp version: {result.stdout.strip()}")
                return True
            else:
                self.logger.warning("yt-dlp not found. Please install it using 'pip install yt-dlp'")
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking yt-dlp installation: {str(e)}")
            return False
    
    def download_video(self, url: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Download a video from the given URL using yt-dlp.
        
        Args:
            url (str): URL of the video to download
            output_path (str, optional): Path where to save the downloaded video.
                If not provided, a temporary path will be generated.
                
        Returns:
            str: Path to the downloaded video file if successful, None otherwise
            
        Note:
            The function applies limitations on filesize and duration.
        """
        try:
            # Generate a temporary output path if not provided
            if not output_path:
                # Create a temporary directory to avoid name conflicts
                temp_dir = tempfile.mkdtemp(prefix="x_scheduler_")
                output_path = os.path.join(temp_dir, f"{uuid.uuid4()}.mp4")
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            self.logger.info(f"Downloading video from {url} to {output_path}")
            
            # Build yt-dlp command with options
            cmd = [
                "yt-dlp",
                
                # Output options
                "-o", output_path,
                
                # Format selection (best mp4 format)
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                
                # Max filesize (in bytes)
                "--max-filesize", f"{self.max_filesize_mb}M",
                
                # Max duration (in seconds)
                "--match-filter", f"duration <= {self.max_duration_seconds}",
                
                # Post-processing options
                # Ensure output is mp4
                "--merge-output-format", "mp4",
                # Ensure proper encoding for Twitter
                "--postprocessor-args", "ffmpeg:-c:v libx264 -c:a aac -ar 44100",
                
                # General options
                "--no-playlist",  # Don't download playlists
                "--no-warnings",  # Reduce output verbosity
                "--no-progress",  # Don't show progress bar
                
                # Add the URL at the end
                url
            ]
            
            # Run the command
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            # Check if download was successful
            if result.returncode == 0:
                # Verify the file exists and has size
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.logger.info(f"Video downloaded successfully to {output_path}")
                    
                    # Add file metadata
                    metadata = self._get_video_metadata(output_path)
                    self.logger.info(f"Video metadata: {metadata}")
                    
                    return output_path
                else:
                    self.logger.error(f"Download appeared successful but file is missing or empty")
                    return None
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                
                # Check for specific errors
                if "File is larger than max-filesize" in error_msg:
                    self.logger.error(f"Video exceeds max filesize of {self.max_filesize_mb}MB")
                elif "Duration exceeded" in error_msg:
                    self.logger.error(f"Video exceeds max duration of {self.max_duration_seconds} seconds")
                else:
                    self.logger.error(f"Failed to download video from {url}: {error_msg}")
                
                return None
                
        except Exception as e:
            self.logger.error(f"Error downloading video from {url}: {str(e)}")
            
            # Clean up any partial download
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
                
            return None
    
    def _get_video_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Get metadata for a video file using ffprobe.
        
        Args:
            file_path (str): Path to the video file
            
        Returns:
            dict: Video metadata
        """
        metadata = {
            "filesize_mb": os.path.getsize(file_path) / (1024 * 1024),
            "path": file_path
        }
        
        try:
            # Use ffprobe to get video duration and format
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                metadata["duration_seconds"] = duration
                
            # Get video dimensions
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                dimensions = result.stdout.strip()
                metadata["dimensions"] = dimensions
                
        except Exception as e:
            self.logger.warning(f"Error getting video metadata: {str(e)}")
            
        return metadata 