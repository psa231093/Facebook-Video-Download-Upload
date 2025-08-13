#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Facebook Video Downloader using yt-dlp
"""

import os
import sys
import subprocess
import json
import re
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform.startswith('win'):
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import DOWNLOAD_CONFIG, AUTH_CONFIG, ADVANCED_CONFIG, FACEBOOK_CONFIG


class FacebookDownloader:
    def __init__(self, config=None):
        self.config = config or DOWNLOAD_CONFIG
        self.output_dir = Path(self.config["output_dir"])
        self.output_dir.mkdir(exist_ok=True)
        
    def check_ytdlp(self):
        """Check if yt-dlp is installed"""
        try:
            subprocess.run(["yt-dlp", "--version"], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def install_ytdlp(self):
        """Install yt-dlp via pip"""
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp"], 
                         check=True)
            print("yt-dlp installed successfully!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to install yt-dlp: {e}")
            return False
    
    def download_video(self, url, quality=None, format_selector=None):
        """Download a single Facebook video"""
        if not self.check_ytdlp():
            print("yt-dlp not found. Installing...")
            if not self.install_ytdlp():
                return False
        
        quality = quality or self.config["quality"]
        format_selector = format_selector or self.config["format"]
        
        # Pre-download validation: Get video info to verify what we're about to download
        print(f"[VALIDATE] Checking video URL: {url}")
        try:
            # Extract video ID from URL for comparison
            import re
            video_id_match = re.search(r'[?&]v=(\d+)', url) or re.search(r'/videos/(\d+)', url)
            expected_video_id = video_id_match.group(1) if video_id_match else None
            
            if expected_video_id:
                print(f"[VALIDATE] Expected video ID from URL: {expected_video_id}")
                
                # Get actual video metadata
                info_cmd = ["yt-dlp", "--get-id", "--get-title", url]
                info_result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
                
                if info_result.returncode == 0:
                    lines = info_result.stdout.strip().split('\n')
                    if len(lines) >= 2:
                        actual_title = lines[0]
                        actual_video_id = lines[1]
                        
                        print(f"[VALIDATE] Video title: {actual_title}")
                        print(f"[VALIDATE] Actual video ID: {actual_video_id}")
                        
                        # Check if video IDs match
                        if expected_video_id != actual_video_id:
                            print(f"[WARNING] Video ID mismatch!")
                            print(f"          Expected: {expected_video_id}")
                            print(f"          Actual: {actual_video_id}")
                            print(f"          This may indicate Facebook is serving different content than requested.")
                        else:
                            print(f"[VALIDATE] Video ID verification passed")
                else:
                    print(f"[WARNING] Could not verify video info: {info_result.stderr}")
            else:
                print(f"[WARNING] Could not extract video ID from URL for validation")
                
        except Exception as e:
            print(f"[WARNING] Pre-download validation failed: {e}")
        
        # yt-dlp options for Facebook
        options = [
            "yt-dlp",
            "--output", str(self.output_dir / self.config["filename_template"]),
            "--format", f"{quality}[ext={format_selector}]/{quality}",
            "--restrict-filenames",  # Restrict filenames to ASCII characters only
        ]
        
        if self.config["save_metadata"]:
            options.append("--write-info-json")
        
        if self.config["download_thumbnail"]:
            options.append("--write-thumbnail")
            
        if self.config["max_filesize"] > 0:
            options.extend(["--max-filesize", f"{self.config['max_filesize']}M"])
            
        if ADVANCED_CONFIG["rate_limit"]:
            options.extend(["--limit-rate", str(ADVANCED_CONFIG["rate_limit"])])
            
        if ADVANCED_CONFIG["retries"] > 0:
            options.extend(["--retries", str(ADVANCED_CONFIG["retries"])])
            
        if ADVANCED_CONFIG["verbose"]:
            options.append("--verbose")
            
        options.extend(ADVANCED_CONFIG["extra_args"])
        options.append(url)
        
        try:
            print(f"[DOWNLOAD] Starting download: {url}")
            
            # Get list of video files before download to compare
            output_dir = Path(self.config["output_dir"])
            video_extensions = ["*.mp4", "*.mkv", "*.webm"]
            files_before = set()
            for ext in video_extensions:
                files_before.update(output_dir.glob(ext))
            
            result = subprocess.run(options, capture_output=True, text=True)
            
            # Get list of video files after download
            files_after = set()
            for ext in video_extensions:
                files_after.update(output_dir.glob(ext))
            
            # Check if any NEW video files were created OR if the video already exists
            new_files = files_after - files_before
            
            # Check if yt-dlp indicates the file already exists
            already_exists = "has already been downloaded" in result.stdout if result.stdout else False
            
            if result.returncode == 0:
                if new_files:
                    print("Download completed successfully!")
                    print(f"[DOWNLOAD] New files created: {[f.name for f in new_files]}")
                    
                    # Process the most recent video file with HandBrake
                    latest_video = max(new_files, key=lambda x: x.stat().st_mtime)
                    success, processed_path = self.process_downloaded_video(str(latest_video), apply_handbrake=False)
                    
                    if success:
                        print(f"SUCCESS: Video processing completed: {processed_path}")
                    else:
                        print(f"WARNING:  Video processing failed: {processed_path}")
                        print("Original video is still available for use.")
                        
                elif already_exists:
                    print("Download completed successfully (file already exists)!")
                    print(f"[DOWNLOAD] Video was already downloaded previously")
                    
                    # Find existing video and process it if not already processed
                    existing_files = files_after
                    if existing_files:
                        latest_video = max(existing_files, key=lambda x: x.stat().st_mtime)
                        modified_name = f"modified_{latest_video.name}"
                        modified_path = latest_video.parent / modified_name
                        
                        if not modified_path.exists():
                            print(f"PROGRESS: Processing existing video with HandBrake...")
                            success, processed_path = self.process_downloaded_video(str(latest_video), apply_handbrake=False)
                            
                            if success:
                                print(f"SUCCESS: Video processing completed: {processed_path}")
                            else:
                                print(f"WARNING:  Video processing failed: {processed_path}")
                        else:
                            print(f"FILE: Modified version already exists: {modified_path}")
                else:
                    print("Download completed successfully!")
                return True
            elif new_files:
                # New files were created despite error code
                print("Download completed successfully (despite error code)!")
                print(f"[DOWNLOAD] New files created: {[f.name for f in new_files]}")
                if result.stderr:
                    print(f"Warning: {result.stderr}")
                
                # Process the most recent video file with HandBrake
                latest_video = max(new_files, key=lambda x: x.stat().st_mtime)
                success, processed_path = self.process_downloaded_video(str(latest_video), apply_handbrake=False)
                
                if success:
                    print(f"SUCCESS: Video processing completed: {processed_path}")
                else:
                    print(f"WARNING:  Video processing failed: {processed_path}")
                    print("Original video is still available for use.")
                    
                return True
            elif already_exists:
                # File already exists - this is still a success
                print("Download completed successfully (file already exists)!")
                print(f"[DOWNLOAD] Video was already downloaded previously")
                return True
            else:
                # No new files were created and no indication of existing file - download failed
                print(f"[ERROR] Download failed: No new video files were created")
                if result.stderr:
                    print(f"[ERROR] yt-dlp stderr: {result.stderr}")
                if result.stdout:
                    print(f"[ERROR] yt-dlp stdout: {result.stdout}")
                return False
                    
        except Exception as e:
            print(f"Download failed with exception: {e}")
            return False
    
    def download_with_cookies(self, url, cookies_file=None, quality=None, format_selector=None):
        """Download Facebook video using cookies for authentication"""
        if not self.check_ytdlp():
            print("yt-dlp not found. Installing...")
            if not self.install_ytdlp():
                return False
        
        cookies_file = cookies_file or AUTH_CONFIG["cookies_file"]
        
        if not Path(cookies_file).exists():
            print(f"Cookies file not found: {cookies_file}")
            return False
        
        quality = quality or self.config["quality"]
        format_selector = format_selector or self.config["format"]
        
        # Pre-download validation: Get video info to verify what we're about to download
        print(f"[VALIDATE] Checking video URL with cookies: {url}")
        try:
            # Extract video ID from URL for comparison
            import re
            video_id_match = re.search(r'[?&]v=(\d+)', url) or re.search(r'/videos/(\d+)', url)
            expected_video_id = video_id_match.group(1) if video_id_match else None
            
            if expected_video_id:
                print(f"[VALIDATE] Expected video ID from URL: {expected_video_id}")
                
                # Get actual video metadata
                info_cmd = ["yt-dlp", "--cookies", cookies_file, "--get-id", "--get-title", url]
                info_result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
                
                if info_result.returncode == 0:
                    lines = info_result.stdout.strip().split('\n')
                    if len(lines) >= 2:
                        actual_title = lines[0]
                        actual_video_id = lines[1]
                        
                        print(f"[VALIDATE] Video title: {actual_title}")
                        print(f"[VALIDATE] Actual video ID: {actual_video_id}")
                        
                        # Check if video IDs match
                        if expected_video_id != actual_video_id:
                            print(f"[WARNING] Video ID mismatch!")
                            print(f"          Expected: {expected_video_id}")
                            print(f"          Actual: {actual_video_id}")
                            print(f"          This may indicate Facebook is serving different content than requested.")
                        else:
                            print(f"[VALIDATE] Video ID verification passed")
                else:
                    print(f"[WARNING] Could not verify video info: {info_result.stderr}")
            else:
                print(f"[WARNING] Could not extract video ID from URL for validation")
                
        except Exception as e:
            print(f"[WARNING] Pre-download validation failed: {e}")
        
        options = [
            "yt-dlp",
            "--cookies", cookies_file,
            "--output", str(self.output_dir / self.config["filename_template"]),
            "--format", f"{quality}[ext={format_selector}]/{quality}",
            "--restrict-filenames",  # Restrict filenames to ASCII characters only
        ]
        
        if self.config["save_metadata"]:
            options.append("--write-info-json")
        
        if self.config["download_thumbnail"]:
            options.append("--write-thumbnail")
            
        if self.config["max_filesize"] > 0:
            options.extend(["--max-filesize", f"{self.config['max_filesize']}M"])
            
        if ADVANCED_CONFIG["rate_limit"]:
            options.extend(["--limit-rate", str(ADVANCED_CONFIG["rate_limit"])])
            
        if ADVANCED_CONFIG["retries"] > 0:
            options.extend(["--retries", str(ADVANCED_CONFIG["retries"])])
            
        if ADVANCED_CONFIG["verbose"]:
            options.append("--verbose")
            
        if AUTH_CONFIG["user_agent"]:
            options.extend(["--user-agent", AUTH_CONFIG["user_agent"]])
            
        options.extend(ADVANCED_CONFIG["extra_args"])
        options.append(url)
        
        try:
            print(f"[DOWNLOAD] Starting authenticated download: {url}")
            
            # Get list of video files before download to compare
            output_dir = Path(self.config["output_dir"])
            video_extensions = ["*.mp4", "*.mkv", "*.webm"]
            files_before = set()
            for ext in video_extensions:
                files_before.update(output_dir.glob(ext))
            
            result = subprocess.run(options, capture_output=True, text=True)
            
            # Get list of video files after download
            files_after = set()
            for ext in video_extensions:
                files_after.update(output_dir.glob(ext))
            
            # Check if any NEW video files were created OR if the video already exists
            new_files = files_after - files_before
            
            # Check if yt-dlp indicates the file already exists
            already_exists = "has already been downloaded" in result.stdout if result.stdout else False
            
            if result.returncode == 0:
                if new_files:
                    print("Download completed successfully!")
                    print(f"[DOWNLOAD] New files created: {[f.name for f in new_files]}")
                    
                    # Process the most recent video file with HandBrake
                    latest_video = max(new_files, key=lambda x: x.stat().st_mtime)
                    success, processed_path = self.process_downloaded_video(str(latest_video), apply_handbrake=False)
                    
                    if success:
                        print(f"SUCCESS: Video processing completed: {processed_path}")
                    else:
                        print(f"WARNING:  Video processing failed: {processed_path}")
                        print("Original video is still available for use.")
                        
                elif already_exists:
                    print("Download completed successfully (file already exists)!")
                    print(f"[DOWNLOAD] Video was already downloaded previously")
                    
                    # Find existing video and process it if not already processed
                    existing_files = files_after
                    if existing_files:
                        latest_video = max(existing_files, key=lambda x: x.stat().st_mtime)
                        modified_name = f"modified_{latest_video.name}"
                        modified_path = latest_video.parent / modified_name
                        
                        if not modified_path.exists():
                            print(f"PROGRESS: Processing existing video with HandBrake...")
                            success, processed_path = self.process_downloaded_video(str(latest_video), apply_handbrake=False)
                            
                            if success:
                                print(f"SUCCESS: Video processing completed: {processed_path}")
                            else:
                                print(f"WARNING:  Video processing failed: {processed_path}")
                        else:
                            print(f"FILE: Modified version already exists: {modified_path}")
                else:
                    print("Download completed successfully!")
                return True
            elif new_files:
                # New files were created despite error code
                print("Download completed successfully (despite error code)!")
                print(f"[DOWNLOAD] New files created: {[f.name for f in new_files]}")
                if result.stderr:
                    print(f"Warning: {result.stderr}")
                
                # Process the most recent video file with HandBrake
                latest_video = max(new_files, key=lambda x: x.stat().st_mtime)
                success, processed_path = self.process_downloaded_video(str(latest_video), apply_handbrake=False)
                
                if success:
                    print(f"SUCCESS: Video processing completed: {processed_path}")
                else:
                    print(f"WARNING:  Video processing failed: {processed_path}")
                    print("Original video is still available for use.")
                    
                return True
            elif already_exists:
                # File already exists - this is still a success
                print("Download completed successfully (file already exists)!")
                print(f"[DOWNLOAD] Video was already downloaded previously")
                return True
            else:
                # No new files were created and no indication of existing file - download failed
                print(f"[ERROR] Authenticated download failed: No new video files were created")
                if result.stderr:
                    print(f"[ERROR] yt-dlp stderr: {result.stderr}")
                if result.stdout:
                    print(f"[ERROR] yt-dlp stdout: {result.stdout}")
                return False
        except Exception as e:
            print(f"Authenticated download failed with exception: {e}")
            return False
    
    def get_video_list(self, page_url, cookies_file=None, max_videos=None):
        """Get list of videos from a Facebook page/profile"""
        print(f"\n[VIDEO_LIST] GET_VIDEO_LIST CALLED")
        print(f"[VIDEO_LIST] Parameters:")
        print(f"   - Page URL: {page_url}")
        print(f"   - Cookies file: {cookies_file}")
        print(f"   - Max videos: {max_videos}")
        
        if not self.check_ytdlp():
            print("[ERROR] yt-dlp not found. Installing...")
            if not self.install_ytdlp():
                print("[ERROR] Failed to install yt-dlp")
                return []
            print("[SUCCESS] yt-dlp installed successfully")
        else:
            print("[SUCCESS] yt-dlp is available")
        
        print(f"[VIDEO_LIST] Starting video list extraction from: {page_url}")
        
        # Try multiple extraction methods
        extraction_methods = [
            self._extract_with_flat_playlist,
            self._extract_with_json_dump,
            self._extract_with_alternative_urls
        ]
        
        for method_name, method in [(m.__name__, m) for m in extraction_methods]:
            print(f"\nCONFIG: Trying {method_name}...")
            try:
                videos = method(page_url, cookies_file, max_videos)
                if videos:
                    print(f"SUCCESS: {method_name} succeeded - found {len(videos)} videos")
                    print("LIST: Video list preview:")
                    for i, video in enumerate(videos[:3]):  # Show first 3
                        print(f"   {i+1}. {video['title'][:50]}...")
                        print(f"      URL: {video['url']}")
                    if len(videos) > 3:
                        print(f"   ... and {len(videos) - 3} more videos")
                    return videos
                else:
                    print(f"ERROR: {method_name} found no videos")
            except Exception as e:
                print(f"ERROR: {method_name} failed: {e}")
                import traceback
                print(f"🔍 Error details:")
                for line in traceback.format_exc().split('\n'):
                    if line.strip():
                        print(f"   {line}")
                continue
        
        print("ERROR: ALL EXTRACTION METHODS FAILED")
        print("💡 This usually means:")
        print("   - The page requires authentication (cookies)")
        print("   - The page structure isn't supported by yt-dlp")
        print("   - The page has no videos or restricted access")
        print("   - Facebook has changed their page format")
        return []
    
    def _extract_with_flat_playlist(self, page_url, cookies_file=None, max_videos=None):
        """Extract videos using flat playlist method"""
        print(f"  CONFIG: Setting up flat playlist extraction...")
        options = [
            "yt-dlp",
            "--flat-playlist",
            "--print", "url",
            "--print", "title",
            "--no-warnings"
        ]
        
        if cookies_file and Path(cookies_file).exists():
            print(f"  COOKIES: Using cookies file: {cookies_file}")
            options.extend(["--cookies", cookies_file])
        else:
            print(f"  PUBLIC: No cookies - public access only")
        
        if max_videos:
            print(f"  STATS: Limiting to {max_videos} videos")
            options.extend(["--playlist-end", str(max_videos)])
            
        if ADVANCED_CONFIG["retries"] > 0:
            print(f"  PROGRESS: Setting retries to {ADVANCED_CONFIG['retries']}")
            options.extend(["--retries", str(ADVANCED_CONFIG["retries"])])
            
        options.append(page_url)
        
        print(f"  START: Running command: {' '.join(options[:5])}... {page_url}")
        
        try:
            result = subprocess.run(options, capture_output=True, text=True, timeout=120)
            print(f"  STATS: Command completed with return code: {result.returncode}")
            
            if result.returncode != 0:
                print(f"  ERROR: yt-dlp failed with stderr:")
                for line in result.stderr.strip().split('\n'):
                    if line.strip():
                        print(f"     {line}")
                raise Exception(f"yt-dlp failed: {result.stderr.strip()}")
            
            print(f"  LIST: Raw output length: {len(result.stdout)} characters")
            lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            print(f"  LIST: Parsed {len(lines)} non-empty lines")
            
            videos = []
            
            # Parse alternating URL and title lines
            for i in range(0, len(lines), 2):
                if i + 1 < len(lines):
                    url = lines[i].strip()
                    title = lines[i + 1].strip()
                    if url and title and url.startswith('https://'):
                        videos.append({
                            'url': url,
                            'title': title
                        })
                        print(f"    SUCCESS: Found video: {title[:30]}...")
                    else:
                        print(f"    WARNING:  Skipped line pair - URL: '{url[:30]}...', Title: '{title[:30]}...'")
            
            print(f"  STATS: Extracted {len(videos)} valid videos")
            return videos
            
        except subprocess.TimeoutExpired:
            print(f"  TIME: Command timed out after 120 seconds")
            raise Exception("yt-dlp command timed out")
        except Exception as e:
            print(f"  EXCEPTION: Exception during subprocess: {e}")
            raise
    
    def _extract_with_json_dump(self, page_url, cookies_file=None, max_videos=None):
        """Extract videos using JSON dump method"""
        options = [
            "yt-dlp",
            "--dump-json",
            "--flat-playlist",
            "--no-warnings"
        ]
        
        if cookies_file and Path(cookies_file).exists():
            options.extend(["--cookies", cookies_file])
        
        if max_videos:
            options.extend(["--playlist-end", str(max_videos)])
            
        options.append(page_url)
        
        result = subprocess.run(options, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            raise Exception(f"yt-dlp JSON dump failed: {result.stderr.strip()}")
        
        videos = []
        lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        
        for line in lines:
            try:
                import json
                entry = json.loads(line)
                if entry.get('url') and entry.get('title'):
                    videos.append({
                        'url': entry['url'],
                        'title': entry['title']
                    })
            except json.JSONDecodeError:
                continue
        
        return videos
    
    def _extract_with_alternative_urls(self, page_url, cookies_file=None, max_videos=None):
        """Try alternative URL formats"""
        # Generate alternative URLs
        alternative_urls = []
        
        if '/videos/' in page_url:
            # Try without /videos/
            alternative_urls.append(page_url.replace('/videos/', '/'))
        else:
            # Try with /videos/
            if not page_url.endswith('/'):
                page_url += '/'
            alternative_urls.append(page_url + 'videos/')
        
        # Try mobile version
        if page_url.startswith('https://www.facebook.com/'):
            alternative_urls.append(page_url.replace('https://www.facebook.com/', 'https://m.facebook.com/'))
        
        for alt_url in alternative_urls:
            print(f"  Trying alternative URL: {alt_url}")
            try:
                videos = self._extract_with_flat_playlist(alt_url, cookies_file, max_videos)
                if videos:
                    return videos
            except Exception as e:
                print(f"  Alternative URL failed: {e}")
                continue
        
        return []
    
    def batch_download(self, page_url, cookies_file=None, max_videos=None, progress_callback=None):
        """Download all videos from a Facebook page/profile"""
        print(f"\nBATCH: BATCH_DOWNLOAD CALLED")
        print(f"BATCH: Parameters:")
        print(f"BATCH:    - Page URL: {page_url}")
        print(f"BATCH:    - Cookies file: {cookies_file}")
        print(f"BATCH:    - Max videos: {max_videos}")
        print(f"BATCH:    - Has progress callback: {progress_callback is not None}")
        
        print(f"BATCH: Calling get_video_list()...")
        videos = self.get_video_list(page_url, cookies_file, max_videos)
        
        if not videos:
            print("ERROR: BATCH_DOWNLOAD FAILED: No videos found or failed to fetch video list")
            print("STATS: Returning: success=False, results=[]")
            return False, []
        
        print(f"SUCCESS: Video list obtained successfully: {len(videos)} videos")
        print(f"START: Starting batch download of {len(videos)} videos...")
        
        successful_downloads = []
        failed_downloads = []
        
        for i, video in enumerate(videos):
            print(f"\n[{i+1}/{len(videos)}] Downloading: {video['title']}")
            
            if progress_callback:
                progress_callback(i, len(videos), video['title'])
            
            try:
                if cookies_file:
                    success = self.download_with_cookies(video['url'], cookies_file)
                else:
                    success = self.download_video(video['url'])
                
                if success:
                    successful_downloads.append(video)
                    print(f"✓ Successfully downloaded: {video['title']}")
                else:
                    failed_downloads.append(video)
                    print(f"✗ Failed to download: {video['title']}")
                    
            except Exception as e:
                failed_downloads.append(video)
                print(f"✗ Error downloading {video['title']}: {e}")
        
        print(f"\nBatch download complete!")
        print(f"✓ Successful: {len(successful_downloads)}")
        print(f"✗ Failed: {len(failed_downloads)}")
        
        return len(successful_downloads) > 0, {
            'successful': successful_downloads,
            'failed': failed_downloads,
            'total': len(videos)
        }
    
    def clean_facebook_title(self, title):
        """Clean up Facebook video title by removing views, reactions metadata and account name"""
        import re
        
        if not title:
            return title
            
        # Remove patterns like "1.6M views · 62K reactions |" from the beginning
        # Pattern matches: numbers + unit + "views" + optional "·" + numbers + unit + "reactions" + "|"
        pattern = r'^[\d.,]+[KMB]?\s*views\s*[·•]\s*[\d.,]+[KMB]?\s*reactions\s*[|｜]\s*'
        cleaned_title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        # Also remove pattern without reactions: "1.6M views |"
        pattern2 = r'^[\d.,]+[KMB]?\s*views\s*[|｜]\s*'
        cleaned_title = re.sub(pattern2, '', cleaned_title, flags=re.IGNORECASE)
        
        # Remove account name at the end (everything after the last | or ｜ separator)
        # This removes patterns like "| La Barbería Espiritual" at the end
        if '|' in cleaned_title:
            # Split by last occurrence of | or ｜ and keep only the first part
            parts = cleaned_title.rsplit('|', 1)
            if len(parts) > 1:
                cleaned_title = parts[0]
        elif '｜' in cleaned_title:
            # Handle Unicode separator
            parts = cleaned_title.rsplit('｜', 1)
            if len(parts) > 1:
                cleaned_title = parts[0]
        
        # Clean up any leading/trailing whitespace
        cleaned_title = cleaned_title.strip()
        
        return cleaned_title

    def extract_video_title_from_metadata(self, video_path):
        """Extract the original video title from yt-dlp metadata JSON file"""
        import json
        
        video_path = Path(video_path)
        # Look for corresponding .info.json file
        json_path = video_path.with_suffix('.info.json')
        
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    # Get the original title from metadata
                    original_title = metadata.get('title', '')
                    if original_title:
                        # Clean up the title to remove views/reactions metadata
                        cleaned_title = self.clean_facebook_title(original_title)
                        try:
                            print(f"[INFO] Original title: {original_title[:100]}...")
                            print(f"[INFO] Cleaned title: {cleaned_title[:100]}...")
                        except UnicodeEncodeError:
                            print("[INFO] Extracted and cleaned title (contains Unicode characters)")
                        return cleaned_title
                    else:
                        print(f"[WARN] No title found in metadata file")
            except Exception as e:
                try:
                    print(f"[WARN] Error reading metadata file: {e}")
                except UnicodeEncodeError:
                    print("[WARN] Error reading metadata file (Unicode error)")
        else:
            try:
                print(f"[WARN] No metadata file found: {json_path}")
            except UnicodeEncodeError:
                print("[WARN] No metadata file found")
        
        # Fallback to filename without extension
        fallback_title = video_path.stem
        try:
            print(f"[INFO] Using fallback title: {fallback_title}")
        except UnicodeEncodeError:
            print("[INFO] Using fallback title (contains Unicode characters)")
        return fallback_title

    def extract_video_description_from_metadata(self, video_path):
        """Extract the original video description from yt-dlp metadata JSON file"""
        import json
        
        video_path = Path(video_path)
        # Look for corresponding .info.json file
        json_path = video_path.with_suffix('.info.json')
        
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    # Get the original description from metadata
                    original_description = metadata.get('description', '')
                    if original_description:
                        try:
                            print(f"[INFO] Original description: {original_description[:100]}...")
                        except UnicodeEncodeError:
                            print("[INFO] Extracted description (contains Unicode characters)")
                        return original_description
                    else:
                        print(f"[WARN] No description found in metadata file")
            except Exception as e:
                try:
                    print(f"[WARN] Error reading description from metadata file: {e}")
                except UnicodeEncodeError:
                    print("[WARN] Error reading description from metadata file (Unicode error)")
        else:
            try:
                print(f"[WARN] No metadata file found for description: {json_path}")
            except UnicodeEncodeError:
                print("[WARN] No metadata file found for description")
        
        # Return empty string if no description found
        return ""
    
    def generate_facebook_preview(self, video_path, user_title_prefix="", user_description=""):
        """Generate Facebook upload preview data without actually uploading"""
        import json
        from pathlib import Path
        
        preview_data = {
            'video_path': video_path,
            'original_title': '',
            'original_description': '',
            'cleaned_title': '',
            'final_title': '',
            'final_description': '',
            'title_prefix': user_title_prefix,
            'video_info': {},
            'thumbnail_url': '',
            'file_size': 0,
            'duration': 0
        }
        
        try:
            video_file = Path(video_path)
            if video_file.exists():
                # Get file size
                preview_data['file_size'] = video_file.stat().st_size
                
                # Extract video title from metadata
                original_title = self.extract_video_title_from_metadata(video_path)
                preview_data['original_title'] = original_title
                preview_data['cleaned_title'] = original_title
                
                # Extract video description from metadata
                original_description = self.extract_video_description_from_metadata(video_path)
                preview_data['original_description'] = original_description
                
                # Apply title prefix if provided
                final_title = original_title
                if user_title_prefix:
                    final_title = f"{user_title_prefix}{original_title}"
                elif FACEBOOK_CONFIG.get('default_title_prefix'):
                    final_title = f"{FACEBOOK_CONFIG['default_title_prefix']}{original_title}"
                
                preview_data['final_title'] = final_title
                
                # Process description - prioritize user input, then original description, then default
                final_description = ""
                if user_description:
                    final_description = user_description
                elif original_description:
                    final_description = original_description
                else:
                    final_description = FACEBOOK_CONFIG.get('default_description', '')
                
                preview_data['final_description'] = final_description
                
                # Try to get additional video metadata
                json_file = video_file.with_suffix('.info.json')
                if json_file.exists():
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            preview_data['video_info'] = {
                                'duration': metadata.get('duration', 0),
                                'uploader': metadata.get('uploader', ''),
                                'view_count': metadata.get('view_count', 0),
                                'thumbnail': metadata.get('thumbnail', ''),
                                'webpage_url': metadata.get('webpage_url', '')
                            }
                            preview_data['duration'] = metadata.get('duration', 0)
                            preview_data['thumbnail_url'] = metadata.get('thumbnail', '')
                    except Exception as e:
                        print(f"[WARN] Could not load metadata for preview: {e}")
                
                print(f"[INFO] Generated Facebook preview for: {video_path}")
                print(f"[INFO] Final title: {final_title[:50]}..." if len(final_title) > 50 else f"[INFO] Final title: {final_title}")
                
                return True, preview_data
                
            else:
                return False, f"Video file not found: {video_path}"
                
        except Exception as e:
            return False, f"Error generating preview: {str(e)}"
    
    def post_download_actions(self, video_path, video_title="", video_description="", auto_upload=None, scheduled_publish_time=None):
        """Handle actions after a video is downloaded"""
        print(f"\nPOST: POST-DOWNLOAD ACTIONS")
        print(f"POST: Video: {video_path}")
        print(f"POST: Title: {video_title}")
        print(f"POST: Description: {video_description}")
        
        # Check if auto-upload is enabled
        if auto_upload is None:
            auto_upload = FACEBOOK_CONFIG.get('auto_upload_enabled', False)
        
        if not auto_upload:
            print(f"PAUSED:  Auto-upload disabled, skipping Facebook upload")
            return True, "Auto-upload disabled"
        
        # Check if we have Facebook credentials
        access_token = os.getenv('FACEBOOK_ACCESS_TOKEN') or FACEBOOK_CONFIG.get('access_token')
        if not access_token:
            print(f"ERROR: No Facebook access token configured")
            return False, "No Facebook access token"
        
        try:
            from facebook_uploader import FacebookUploader
            
            # Initialize Facebook uploader
            uploader = FacebookUploader(
                access_token=access_token,
                user_id=FACEBOOK_CONFIG['user_id']
            )
            
            # Extract original video title from metadata if not provided
            if not video_title:
                video_title = self.extract_video_title_from_metadata(video_path)
            
            # Prepare title with prefix if configured
            title = video_title or "Downloaded Video"
            if FACEBOOK_CONFIG.get('default_title_prefix'):
                title = f"{FACEBOOK_CONFIG['default_title_prefix']}{title}"
            
            # Prepare description - prioritize user input, then original description, then default
            description = ""
            if video_description:
                description = video_description
            else:
                # Try to extract original video description
                original_description = self.extract_video_description_from_metadata(video_path)
                if original_description:
                    description = original_description
                else:
                    description = FACEBOOK_CONFIG.get('default_description', '')
            
            print(f"FACEBOOK: Starting Facebook upload...")
            print(f"[DEBUG] Final title: '{title}'")
            print(f"[DEBUG] Final description: '{description}'")
            print(f"[DEBUG] Title length: {len(title)}")
            print(f"[DEBUG] Description length: {len(description)}")
            success, result = uploader.upload_video(
                video_path=video_path,
                title=title,
                description=description,
                scheduled_publish_time=scheduled_publish_time
            )
            
            if success:
                print(f"SUCCESS: Facebook upload successful!")
                return True, result
            else:
                # Handle Unicode characters in error messages safely
                try:
                    error_msg = str(result).encode('utf-8', errors='replace').decode('utf-8')
                    print(f"ERROR: Facebook upload failed: {error_msg}")
                except (UnicodeEncodeError, AttributeError):
                    print("ERROR: Facebook upload failed: (error message contains special characters)")
                return False, result
                
        except ImportError as e:
            print(f"ERROR: Facebook uploader not available: {e}")
            return False, "Facebook uploader not available"
        except Exception as e:
            print(f"EXCEPTION: Exception during Facebook upload: {e}")
            return False, str(e)

    def check_handbrake_cli(self):
        """Check if HandBrakeCLI is installed and available"""
        # Try multiple possible locations for HandBrake CLI
        possible_paths = [
            r"C:\Users\pablo\Downloads\HandBrakeCLI-1.10.0-win-x86_64\HandBrakeCLI.exe",  # Full path - try first
            "HandBrakeCLI",  # System PATH
            "./HandBrakeCLI.exe",  # Current directory (Windows)
            "HandBrakeCLI.exe",  # Current directory (Windows)
        ]
        
        for handbrake_path in possible_paths:
            try:
                result = subprocess.run([handbrake_path, "--version"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    print(f"HANDBRAKE: HandBrakeCLI found: {result.stdout.split()[0]}")
                    # Store the working path for later use
                    self.handbrake_path = handbrake_path
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                continue
        
        print(f"HANDBRAKE: HandBrakeCLI not found in any of the expected locations.")
        print("HANDBRAKE: Tried:")
        for path in possible_paths:
            print(f"HANDBRAKE: - {path}")
        return False

    def transcode_video_with_handbrake(self, input_path, output_path=None, progress_callback=None):
        """
        Transcode video using HandBrake CLI to avoid Facebook duplicate detection
        
        Parameters:
        - Resolution: 720p (1280x720)
        - Frame rate: 24fps 
        - Encoder: H.264
        - Constant frame rate
        """
        if not self.check_handbrake_cli():
            return False, "HandBrakeCLI not available"
        
        input_file = Path(input_path)
        if not input_file.exists():
            return False, f"Input file not found: {input_path}"
        
        # Generate output filename if not provided
        if output_path is None:
            # Create shorter filename to avoid Windows path length limits
            base_name = input_file.stem
            if len(base_name) > 50:
                # Truncate long filenames but keep the unique identifier at the end
                if '[' in base_name and ']' in base_name:
                    # Extract the ID part (e.g., [1993618894721565])
                    id_part = base_name[base_name.rfind('['):]
                    short_name = f"modified_{base_name[:30]}_{id_part}"
                else:
                    short_name = f"modified_{base_name[:50]}"
            else:
                short_name = f"modified_{base_name}"
            
            output_path = input_file.parent / f"{short_name}{input_file.suffix}"
        
        output_file = Path(output_path)
        
        print(f"HANDBRAKE: Starting HandBrake transcoding...")
        print(f"HANDBRAKE: Input: {input_file}")
        print(f"HANDBRAKE: Output: {output_file}")
        
        # HandBrake CLI command with specified parameters (simplified for compatibility)
        handbrake_cmd = [
            getattr(self, 'handbrake_path', 'HandBrakeCLI'),  # Use stored path or fallback
            "--input", str(input_file),
            "--output", str(output_file),
            "--width", "1280",          # 720p width
            "--height", "720",          # 720p height
            "--rate", "24",             # 24fps frame rate
            "--cfr",                    # Constant frame rate
            "--encoder", "x264",        # H.264 encoder
            "--quality", "22"           # Good quality setting (RF)
        ]
        
        try:
            print(f"HANDBRAKE: Running HandBrake command...")
            if progress_callback:
                progress_callback(0, "Starting HandBrake transcoding...")
            
            # Start the HandBrake process
            process = subprocess.Popen(
                handbrake_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            # Monitor progress if callback provided
            if progress_callback:
                self._monitor_handbrake_progress(process, progress_callback)
            else:
                # Simple wait for completion
                process.wait()
            
            # Check if process completed successfully
            if process.returncode == 0:
                if output_file.exists():
                    file_size = output_file.stat().st_size
                    print(f"HANDBRAKE: HandBrake transcoding completed successfully!")
                    print(f"HANDBRAKE: Output file size: {file_size / 1024 / 1024:.2f} MB")
                    return True, str(output_file)
                else:
                    return False, "Output file was not created"
            else:
                stdout_output = process.stdout.read() if process.stdout else ""
                stderr_output = process.stderr.read() if process.stderr else ""
                error_msg = f"HandBrake process failed with return code {process.returncode}"
                print(f"HANDBRAKE: {error_msg}")
                if stdout_output:
                    print(f"HANDBRAKE: STDOUT: {stdout_output}")
                if stderr_output:
                    print(f"HANDBRAKE: STDERR: {stderr_output}")
                return False, f"{error_msg}. STDERR: {stderr_output[:200]}"
                
        except Exception as e:
            error_msg = f"HandBrake transcoding failed: {str(e)}"
            print(f"HANDBRAKE: {error_msg}")
            return False, error_msg

    def _monitor_handbrake_progress(self, process, progress_callback):
        """Monitor HandBrake progress and call progress callback"""
        try:
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                
                # Parse HandBrake progress output
                # HandBrake outputs lines like: "Encoding: task 1 of 1, 45.67 % (127.45 fps, avg 125.32 fps, ETA 00h15m42s)"
                if "Encoding:" in line and "%" in line:
                    try:
                        # Extract percentage
                        percent_match = re.search(r'(\d+\.\d+)\s*%', line)
                        if percent_match:
                            progress_percent = float(percent_match.group(1))
                            
                            # Extract ETA if available
                            eta_match = re.search(r'ETA\s+(\d+h\d+m\d+s)', line)
                            eta_str = eta_match.group(1) if eta_match else "Unknown"
                            
                            # Extract FPS if available
                            fps_match = re.search(r'(\d+\.\d+)\s*fps', line)
                            fps_str = fps_match.group(1) if fps_match else "Unknown"
                            
                            status_msg = f"Transcoding: {progress_percent:.1f}% (FPS: {fps_str}, ETA: {eta_str})"
                            progress_callback(progress_percent, status_msg)
                            
                    except (ValueError, AttributeError) as e:
                        # Continue if we can't parse progress
                        pass
                
                # Print output for debugging
                print(f"[HandBrake] {line.strip()}")
            
            # Wait for process to complete
            process.wait()
            
        except Exception as e:
            print(f"ERROR: Error monitoring HandBrake progress: {e}")
            process.wait()

    def process_downloaded_video(self, video_path, apply_handbrake=False, progress_callback=None):
        """
        Process a downloaded video with HandBrake to modify it for Facebook re-upload
        
        Args:
            video_path: Path to the downloaded video file
            apply_handbrake: Whether to apply HandBrake transcoding (default: True)
            progress_callback: Optional callback function for progress updates
            
        Returns:
            tuple: (success, processed_video_path_or_error_message)
        """
        if not apply_handbrake:
            print(f"PAUSED: HandBrake processing disabled")
            return True, video_path
        
        print(f"PROCESS: Processing downloaded video for Facebook re-upload...")
        print(f"PROCESS: Original video: {video_path}")
        
        # Transcode with HandBrake
        success, result = self.transcode_video_with_handbrake(
            input_path=video_path,
            progress_callback=progress_callback
        )
        
        if success:
            print(f"SUCCESS: Video processing completed successfully!")
            print(f"FILE: Modified video: {result}")
            return True, result
        else:
            print(f"ERROR: Video processing failed: {result}")
            return False, result


def main():
    """Main function for command line usage"""
    if len(sys.argv) < 2:
        print("Usage: python facebook_downloader.py <facebook_video_url> [cookies_file]")
        print("Example: python facebook_downloader.py https://www.facebook.com/watch/?v=123456789")
        print("With cookies: python facebook_downloader.py https://www.facebook.com/watch/?v=123456789 cookies.txt")
        sys.exit(1)
    
    url = sys.argv[1]
    cookies_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    downloader = FacebookDownloader()
    
    if cookies_file:
        success = downloader.download_with_cookies(url, cookies_file)
    else:
        success = downloader.download_video(url)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()