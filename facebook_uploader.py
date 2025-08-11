#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Facebook Video Uploader using Graph API
"""

import os
import sys
import requests
import json
from pathlib import Path
import time

# Set UTF-8 encoding for Windows console
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

class FacebookUploader:
    def __init__(self, access_token, user_id):
        self.access_token = access_token
        self.user_id = user_id
        self.graph_api_url = "https://graph.facebook.com/v18.0"
        
    def upload_video(self, video_path, title="", description="", scheduled_publish_time=None):
        """Upload a video to Facebook profile with optional scheduling"""
        print(f"\n[UPLOAD] FACEBOOK VIDEO UPLOAD STARTED")
        print(f"[UPLOAD] Parameters:")
        print(f"   - Video path: {video_path}")
        # Handle Unicode characters safely
        try:
            title_display = title.encode('utf-8', errors='replace').decode('utf-8') if title else ''
            desc_display = description.encode('utf-8', errors='replace').decode('utf-8') if description else ''
            print(f"   - Title: {title_display}")
            print(f"   - Description: {desc_display}")
        except (UnicodeEncodeError, AttributeError):
            print("   - Title: (contains special characters)")
            print("   - Description: (contains special characters)")
        print(f"   - User ID: {self.user_id}")
        print(f"   - Scheduled publish time: {scheduled_publish_time}")
        print(f"[DEBUG] Title length: {len(title)}")
        print(f"[DEBUG] Description length: {len(description)}")
        print(f"[DEBUG] Title empty: {not bool(title.strip() if title else True)}")
        print(f"[DEBUG] Description empty: {not bool(description.strip() if description else True)}")
        print(f"[DEBUG] Is scheduled: {scheduled_publish_time is not None}")
        
        video_file = Path(video_path)
        if not video_file.exists():
            print(f"[ERROR] Video file not found: {video_path}")
            return False, "Video file not found"
        
        file_size = video_file.stat().st_size
        print(f"[UPLOAD] Video file size: {file_size} bytes ({file_size / (1024*1024):.1f} MB)")
        
        try:
            # Step 1: Initialize upload session
            print(f"[UPLOAD] Step 1: Initializing upload session...")
            init_response = self._initialize_upload(file_size)
            
            if not init_response:
                return False, "Failed to initialize upload session"
            
            upload_session_id = init_response.get('upload_session_id')
            video_id = init_response.get('video_id')
            
            print(f"✅ Upload session initialized:")
            print(f"   - Session ID: {upload_session_id}")
            print(f"   - Video ID: {video_id}")
            
            # Step 2: Upload video file
            print(f"📤 Step 2: Uploading video file...")
            upload_success = self._upload_video_file(video_file, upload_session_id)
            
            if not upload_success:
                return False, "Failed to upload video file"
            
            print(f"✅ Video file uploaded successfully")
            
            # Step 3: Publish video with title and description
            print(f"🚀 Step 3: Publishing video...")
            publish_response = self._publish_video(upload_session_id, title, description, scheduled_publish_time)
            
            if not publish_response:
                return False, "Failed to publish video"
            
            if scheduled_publish_time:
                print(f"✅ Video scheduled successfully!")
                print(f"📅 Video will be published at scheduled time")
            else:
                print(f"✅ Video published successfully!")
                
            print(f"📋 Video details:")
            print(f"   - Video ID: {video_id}")
            print(f"   - Title: {title}")
            
            result = {
                'video_id': video_id,
                'title': title,
                'description': description,
                'upload_session_id': upload_session_id,
                'scheduled': scheduled_publish_time is not None
            }
            
            # Only add Facebook URL for immediate posts
            if not scheduled_publish_time:
                facebook_url = f"https://www.facebook.com/{self.user_id}/videos/{video_id}"
                print(f"   - Facebook URL: {facebook_url}")
                result['facebook_url'] = facebook_url
            else:
                from datetime import datetime
                scheduled_date = datetime.fromtimestamp(scheduled_publish_time)
                print(f"   - Scheduled for: {scheduled_date.strftime('%Y-%m-%d at %H:%M')}")
                result['scheduled_time'] = scheduled_publish_time
            
            return True, result
            
        except Exception as e:
            print(f"💥 Exception during Facebook upload: {e}")
            import traceback
            traceback.print_exc()
            return False, f"Upload error: {str(e)}"
    
    def _initialize_upload(self, file_size):
        """Initialize video upload session"""
        url = f"{self.graph_api_url}/{self.user_id}/videos"
        
        data = {
            'upload_phase': 'start',
            'file_size': file_size,
            'access_token': self.access_token
        }
        
        print(f"🌐 Making API request to: {url}")
        print(f"📊 Request data: {data}")
        
        try:
            response = requests.post(url, data=data, timeout=30)
            print(f"📥 Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"📋 Response data: {result}")
                return result
            else:
                print(f"❌ API request failed:")
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"💥 Exception in initialize_upload: {e}")
            return None
    
    def _upload_video_file(self, video_file, upload_session_id):
        """Upload the actual video file"""
        url = f"{self.graph_api_url}/{self.user_id}/videos"
        
        print(f"📤 Uploading file: {video_file.name}")
        print(f"🔗 Upload session ID: {upload_session_id}")
        
        try:
            with open(video_file, 'rb') as video_data:
                files = {
                    'video_file_chunk': (video_file.name, video_data, 'video/mp4')
                }
                
                data = {
                    'upload_phase': 'transfer',
                    'upload_session_id': upload_session_id,
                    'start_offset': 0,
                    'access_token': self.access_token
                }
                
                print(f"🌐 Making upload request...")
                response = requests.post(url, files=files, data=data, timeout=300)  # 5 minute timeout
                print(f"📥 Upload response status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"📋 Upload response: {result}")
                    
                    # Check if upload was successful by looking at offsets
                    start_offset = int(result.get('start_offset', 0))
                    end_offset = int(result.get('end_offset', 0))
                    
                    if end_offset > 0:
                        print(f"✅ Upload successful - bytes transferred: {end_offset}")
                        return True
                    else:
                        print(f"❌ Upload failed - no bytes transferred")
                        return False
                else:
                    print(f"❌ Upload failed:")
                    print(f"   Status: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return False
                    
        except Exception as e:
            print(f"💥 Exception in upload_video_file: {e}")
            return False
    
    def _publish_video(self, upload_session_id, title, description="", scheduled_publish_time=None):
        """Publish the uploaded video with title and description"""
        url = f"{self.graph_api_url}/{self.user_id}/videos"
        
        data = {
            'upload_phase': 'finish',
            'upload_session_id': upload_session_id,
            'access_token': self.access_token
        }
        
        if title:
            data['title'] = title
            print(f"[DEBUG] Added title to data: '{title[:50]}...' (length: {len(title)})")
        else:
            print(f"[DEBUG] No title provided - title is empty or None")
            
        if description:
            data['description'] = description
            print(f"[DEBUG] Added description to data: '{description[:50]}...' (length: {len(description)})")
        else:
            print(f"[DEBUG] No description provided - description is empty or None")
            
        # Add scheduling if provided
        if scheduled_publish_time:
            # For scheduled posts, set published=false and scheduled_publish_time
            data['published'] = False
            data['scheduled_publish_time'] = scheduled_publish_time
            print(f"[DEBUG] Creating unpublished post with scheduled_publish_time: {scheduled_publish_time}")
            from datetime import datetime
            scheduled_date = datetime.fromtimestamp(scheduled_publish_time)
            print(f"[DEBUG] Scheduled for: {scheduled_date.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            # For immediate posts, set published=true (default behavior)
            data['published'] = True
            print(f"[DEBUG] Publishing immediately")
        
        # Safe logging of request data with Unicode handling
        try:
            # Create a safe copy of data for logging
            safe_data = data.copy()
            if 'title' in safe_data:
                safe_data['title'] = safe_data['title'].encode('utf-8', errors='replace').decode('utf-8')
            if 'description' in safe_data:
                safe_data['description'] = safe_data['description'].encode('utf-8', errors='replace').decode('utf-8')
            print(f"🚀 Publishing video with data: {safe_data}")
        except (UnicodeEncodeError, AttributeError):
            print("🚀 Publishing video with data (contains special characters)")
            print(f"[DEBUG] Data keys: {list(data.keys())}")
            if 'title' in data:
                print(f"[DEBUG] Title in data: Yes (length: {len(data['title'])})")
            if 'description' in data:
                print(f"[DEBUG] Description in data: Yes (length: {len(data['description'])})")
        
        try:
            # Ensure UTF-8 encoding for the request
            response = requests.post(url, data=data, timeout=60, headers={'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'})
            print(f"[API] Publish response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"[API] Publish response: {result}")
                
                # For scheduled posts, check if the response indicates success
                if scheduled_publish_time:
                    if 'id' in result:
                        print(f"[SUCCESS] Scheduled post created with ID: {result['id']}")
                    else:
                        print(f"[WARNING] Scheduled post response missing 'id' field")
                
                return result
            else:
                print(f"[ERROR] Publish failed:")
                print(f"        Status: {response.status_code}")
                print(f"        Response: {response.text}")
                
                # Try to parse error response
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error = error_data['error']
                        print(f"        Error Code: {error.get('code', 'Unknown')}")
                        print(f"        Error Message: {error.get('message', 'No message')}")
                        print(f"        Error Type: {error.get('type', 'Unknown')}")
                except:
                    print("        Could not parse error response as JSON")
                
                return None
                
        except Exception as e:
            print(f"[ERROR] Exception in publish_video: {e}")
            return None
    
    def test_connection(self):
        """Test Facebook API connection"""
        print(f"[TEST] Testing Facebook API connection...")
        
        url = f"{self.graph_api_url}/me"
        params = {
            'access_token': self.access_token,
            'fields': 'id,name'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            print(f"📥 Test response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Connection successful!")
                print(f"📋 User info: {result}")
                return True, result
            else:
                print(f"❌ Connection failed:")
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text}")
                return False, response.text
                
        except Exception as e:
            print(f"💥 Exception in test_connection: {e}")
            return False, str(e)
    
    def get_scheduled_posts(self):
        """Get scheduled posts from Facebook - only posts with valid future scheduled times"""
        print(f"📅 Getting scheduled posts...")
        
        url = f"{self.graph_api_url}/{self.user_id}/posts"
        params = {
            'access_token': self.access_token,
            'fields': 'id,message,created_time,updated_time,scheduled_publish_time,status_type,full_picture,picture',
            'is_published': 'false',  # Only get unpublished (scheduled) posts
            'limit': 50
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            print(f"📥 Scheduled posts response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                raw_posts = result.get('data', [])
                print(f"📊 Found {len(raw_posts)} unpublished posts")
                
                # Filter to only include posts with valid future scheduled times
                filtered_posts = []
                current_timestamp = time.time()
                
                for post in raw_posts:
                    scheduled_time = post.get('scheduled_publish_time')
                    
                    # Skip posts without scheduled_publish_time
                    if not scheduled_time:
                        print(f"⏭️  Skipping post {post.get('id', 'unknown')} - no scheduled_publish_time")
                        continue
                    
                    # Convert scheduled_publish_time to timestamp for validation
                    try:
                        if isinstance(scheduled_time, str):
                            # Parse ISO format datetime string
                            from datetime import datetime
                            dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                            scheduled_timestamp = dt.timestamp()
                        else:
                            scheduled_timestamp = float(scheduled_time)
                        
                        # Only include posts scheduled for the future (not 1969 or past dates)
                        if scheduled_timestamp > current_timestamp:
                            filtered_posts.append(post)
                            print(f"✅ Valid scheduled post: {post.get('id', 'unknown')} at {datetime.fromtimestamp(scheduled_timestamp)}")
                        else:
                            print(f"⏭️  Skipping post {post.get('id', 'unknown')} - scheduled time is in the past or invalid ({scheduled_time})")
                            
                    except (ValueError, TypeError) as e:
                        print(f"⏭️  Skipping post {post.get('id', 'unknown')} - invalid scheduled_publish_time format: {scheduled_time} ({e})")
                        continue
                
                # Return filtered results
                filtered_result = {
                    'data': filtered_posts,
                    'paging': result.get('paging', {})
                }
                
                print(f"✅ Successfully retrieved scheduled posts!")
                print(f"📊 Filtered to {len(filtered_posts)} posts with valid future scheduled times")
                return True, filtered_result
            else:
                print(f"❌ Failed to get scheduled posts:")
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text}")
                return False, response.text
                
        except Exception as e:
            print(f"💥 Exception in get_scheduled_posts: {e}")
            return False, str(e)
    
    def cancel_scheduled_post(self, post_id):
        """Cancel a scheduled Facebook post"""
        print(f"❌ Cancelling scheduled post: {post_id}")
        
        url = f"{self.graph_api_url}/{post_id}"
        params = {
            'access_token': self.access_token
        }
        
        try:
            response = requests.delete(url, params=params, timeout=30)
            print(f"📥 Cancel response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Successfully cancelled scheduled post!")
                print(f"📋 Response: {result}")
                return True, result
            else:
                print(f"❌ Failed to cancel scheduled post:")
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text}")
                return False, response.text
                
        except Exception as e:
            print(f"💥 Exception in cancel_scheduled_post: {e}")
            return False, str(e)
    
    def get_video_posts(self, limit=25):
        """Get video posts from Facebook (both published and scheduled)"""
        print(f"🎥 Getting video posts...")
        
        url = f"{self.graph_api_url}/{self.user_id}/videos"
        params = {
            'access_token': self.access_token,
            'fields': 'id,title,description,created_time,updated_time,scheduled_publish_time,status,source,picture',
            'limit': limit
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            print(f"📥 Video posts response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Successfully retrieved video posts!")
                print(f"📊 Found {len(result.get('data', []))} video posts")
                return True, result
            else:
                print(f"❌ Failed to get video posts:")
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text}")
                return False, response.text
                
        except Exception as e:
            print(f"💥 Exception in get_video_posts: {e}")
            return False, str(e)


def main():
    """Test function"""
    print("Facebook Video Uploader Test")
    print("This is a test of the Facebook video upload functionality")
    print("Make sure to set your access token and user ID in the code")

if __name__ == "__main__":
    main()