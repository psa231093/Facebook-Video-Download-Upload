"""
Configuration settings for Facebook video downloader
"""

# Download settings
DOWNLOAD_CONFIG = {
    # Output directory for downloaded videos
    "output_dir": "downloads",
    
    # Video quality options: "best", "worst", "720p", "1080p", etc.
    "quality": "best",
    
    # Preferred format: "mp4", "webm", "mkv", etc.
    "format": "mp4",
    
    # Whether to download thumbnails
    "download_thumbnail": True,
    
    # Whether to save video metadata as JSON
    "save_metadata": True,
    
    # Filename template (yt-dlp format) - using ID to avoid special character issues
    "filename_template": "%(title).200s [%(id)s].%(ext)s",
    
    # Maximum file size in MB (0 = no limit)
    "max_filesize": 0,
}

# Authentication settings
AUTH_CONFIG = {
    # Default cookies file path
    "cookies_file": "cookies.txt",
    
    # User agent string (optional)
    "user_agent": None,
    
    # Additional headers (optional)
    "headers": {},
}

# Advanced yt-dlp options
ADVANCED_CONFIG = {
    # Rate limiting (downloads per second)
    "rate_limit": None,
    
    # Retry attempts
    "retries": 3,
    
    # Enable verbose output
    "verbose": False,
    
    # Additional yt-dlp arguments
    "extra_args": [],
}

# Facebook API settings
FACEBOOK_CONFIG = {
    # Facebook access token (get from developers.facebook.com)
    "access_token": "EAA8X9ZAQ74NcBPPHynIHvEpER97TXIvYoTRw7VRb3Aohi2w4KR341TGeZBlcEHc27ZBXHO4nZBZCZCPNefzNEgk9Gf9zp0cqIrpYyOuXU0P6FTATdxJZC5XaNKIM6JXkOYO4wlbX5okBsLGLPjaCGcHNtbZADR4bZBUmIG8lZB7ZBra1XF8XTVLtFu796DT7yfZCLQFv1SLjbK0kQ71QszIH8nZAH",
    
    # Your Facebook page ID (La Barbería Espiritual)
    "user_id": "188380891769503",
    
    # Auto-upload settings
    "auto_upload_enabled": True,  # Set to True to enable auto-upload
    
    # Default video settings
    "default_title_prefix": "",  # Optional prefix for video titles
    "default_description": "Uploaded via Facebook Video Downloader",
    
    # Upload settings
    "max_file_size_mb": 1024,  # Max file size for Facebook upload (1GB)
}