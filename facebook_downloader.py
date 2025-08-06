#!/usr/bin/env python3
"""
Facebook Video Downloader using yt-dlp
"""

import os
import sys
import subprocess
from pathlib import Path

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
        
        # yt-dlp options for Facebook
        options = [
            "yt-dlp",
            "--output", str(self.output_dir / self.config["filename_template"]),
            "--format", f"{quality}[ext={format_selector}]/{quality}",
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
            print(f"Downloading: {url}")
            result = subprocess.run(options, capture_output=True, text=True)
            
            # Check if download actually succeeded by looking for created files
            # yt-dlp sometimes returns non-zero exit codes even on successful downloads
            if result.returncode == 0:
                print("Download completed successfully!")
                return True
            else:
                # Check if any video files were created despite the error
                import glob
                output_dir = Path(self.config["output_dir"])
                video_files = list(output_dir.glob("*.mp4")) + list(output_dir.glob("*.mkv")) + list(output_dir.glob("*.webm"))
                
                if video_files:
                    # Files were created, so download likely succeeded despite error code
                    print("Download completed successfully (despite error code)!")
                    if result.stderr:
                        print(f"Warning: {result.stderr}")
                    return True
                else:
                    print(f"Download failed: {result.stderr if result.stderr else 'Unknown error'}")
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
        
        options = [
            "yt-dlp",
            "--cookies", cookies_file,
            "--output", str(self.output_dir / self.config["filename_template"]),
            "--format", f"{quality}[ext={format_selector}]/{quality}",
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
            print(f"Downloading with authentication: {url}")
            result = subprocess.run(options, check=True, capture_output=True, text=True)
            print("Download completed successfully!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Download failed: {e}")
            print(f"Error output: {e.stderr}")
            return False
    
    def get_video_list(self, page_url, cookies_file=None, max_videos=None):
        """Get list of videos from a Facebook page/profile"""
        print(f"\n🎬 GET_VIDEO_LIST CALLED")
        print(f"📝 Parameters:")
        print(f"   - Page URL: {page_url}")
        print(f"   - Cookies file: {cookies_file}")
        print(f"   - Max videos: {max_videos}")
        
        if not self.check_ytdlp():
            print("❌ yt-dlp not found. Installing...")
            if not self.install_ytdlp():
                print("❌ Failed to install yt-dlp")
                return []
            print("✅ yt-dlp installed successfully")
        else:
            print("✅ yt-dlp is available")
        
        print(f"🔍 Starting video list extraction from: {page_url}")
        
        # Try multiple extraction methods
        extraction_methods = [
            self._extract_with_flat_playlist,
            self._extract_with_json_dump,
            self._extract_with_alternative_urls
        ]
        
        for method_name, method in [(m.__name__, m) for m in extraction_methods]:
            print(f"\n🔧 Trying {method_name}...")
            try:
                videos = method(page_url, cookies_file, max_videos)
                if videos:
                    print(f"✅ {method_name} succeeded - found {len(videos)} videos")
                    print("📋 Video list preview:")
                    for i, video in enumerate(videos[:3]):  # Show first 3
                        print(f"   {i+1}. {video['title'][:50]}...")
                        print(f"      URL: {video['url']}")
                    if len(videos) > 3:
                        print(f"   ... and {len(videos) - 3} more videos")
                    return videos
                else:
                    print(f"❌ {method_name} found no videos")
            except Exception as e:
                print(f"❌ {method_name} failed: {e}")
                import traceback
                print(f"🔍 Error details:")
                for line in traceback.format_exc().split('\n'):
                    if line.strip():
                        print(f"   {line}")
                continue
        
        print("❌ ALL EXTRACTION METHODS FAILED")
        print("💡 This usually means:")
        print("   - The page requires authentication (cookies)")
        print("   - The page structure isn't supported by yt-dlp")
        print("   - The page has no videos or restricted access")
        print("   - Facebook has changed their page format")
        return []
    
    def _extract_with_flat_playlist(self, page_url, cookies_file=None, max_videos=None):
        """Extract videos using flat playlist method"""
        print(f"  🔧 Setting up flat playlist extraction...")
        options = [
            "yt-dlp",
            "--flat-playlist",
            "--print", "url",
            "--print", "title",
            "--no-warnings"
        ]
        
        if cookies_file and Path(cookies_file).exists():
            print(f"  🍪 Using cookies file: {cookies_file}")
            options.extend(["--cookies", cookies_file])
        else:
            print(f"  🔓 No cookies - public access only")
        
        if max_videos:
            print(f"  📊 Limiting to {max_videos} videos")
            options.extend(["--playlist-end", str(max_videos)])
            
        if ADVANCED_CONFIG["retries"] > 0:
            print(f"  🔄 Setting retries to {ADVANCED_CONFIG['retries']}")
            options.extend(["--retries", str(ADVANCED_CONFIG["retries"])])
            
        options.append(page_url)
        
        print(f"  🚀 Running command: {' '.join(options[:5])}... {page_url}")
        
        try:
            result = subprocess.run(options, capture_output=True, text=True, timeout=120)
            print(f"  📊 Command completed with return code: {result.returncode}")
            
            if result.returncode != 0:
                print(f"  ❌ yt-dlp failed with stderr:")
                for line in result.stderr.strip().split('\n'):
                    if line.strip():
                        print(f"     {line}")
                raise Exception(f"yt-dlp failed: {result.stderr.strip()}")
            
            print(f"  📋 Raw output length: {len(result.stdout)} characters")
            lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            print(f"  📋 Parsed {len(lines)} non-empty lines")
            
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
                        print(f"    ✅ Found video: {title[:30]}...")
                    else:
                        print(f"    ⚠️  Skipped line pair - URL: '{url[:30]}...', Title: '{title[:30]}...'")
            
            print(f"  📊 Extracted {len(videos)} valid videos")
            return videos
            
        except subprocess.TimeoutExpired:
            print(f"  ⏰ Command timed out after 120 seconds")
            raise Exception("yt-dlp command timed out")
        except Exception as e:
            print(f"  💥 Exception during subprocess: {e}")
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
        print(f"\n🎬 BATCH_DOWNLOAD CALLED")
        print(f"📝 Parameters:")
        print(f"   - Page URL: {page_url}")
        print(f"   - Cookies file: {cookies_file}")
        print(f"   - Max videos: {max_videos}")
        print(f"   - Has progress callback: {progress_callback is not None}")
        
        print(f"📋 Calling get_video_list()...")
        videos = self.get_video_list(page_url, cookies_file, max_videos)
        
        if not videos:
            print("❌ BATCH_DOWNLOAD FAILED: No videos found or failed to fetch video list")
            print("📊 Returning: success=False, results=[]")
            return False, []
        
        print(f"✅ Video list obtained successfully: {len(videos)} videos")
        print(f"🚀 Starting batch download of {len(videos)} videos...")
        
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
    
    def post_download_actions(self, video_path, video_title="", video_description="", auto_upload=None):
        """Handle actions after a video is downloaded"""
        print(f"\n🎬 POST-DOWNLOAD ACTIONS")
        print(f"📝 Video: {video_path}")
        print(f"📝 Title: {video_title}")
        print(f"📝 Description: {video_description}")
        
        # Check if auto-upload is enabled
        if auto_upload is None:
            auto_upload = FACEBOOK_CONFIG.get('auto_upload_enabled', False)
        
        if not auto_upload:
            print(f"⏸️  Auto-upload disabled, skipping Facebook upload")
            return True, "Auto-upload disabled"
        
        # Check if we have Facebook credentials
        access_token = os.getenv('FACEBOOK_ACCESS_TOKEN') or FACEBOOK_CONFIG.get('access_token')
        if not access_token:
            print(f"❌ No Facebook access token configured")
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
            
            print(f"📤 Starting Facebook upload...")
            print(f"[DEBUG] Final title: '{title}'")
            print(f"[DEBUG] Final description: '{description}'")
            print(f"[DEBUG] Title length: {len(title)}")
            print(f"[DEBUG] Description length: {len(description)}")
            success, result = uploader.upload_video(
                video_path=video_path,
                title=title,
                description=description
            )
            
            if success:
                print(f"✅ Facebook upload successful!")
                return True, result
            else:
                print(f"❌ Facebook upload failed: {result}")
                return False, result
                
        except ImportError as e:
            print(f"❌ Facebook uploader not available: {e}")
            return False, "Facebook uploader not available"
        except Exception as e:
            print(f"💥 Exception during Facebook upload: {e}")
            return False, str(e)


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