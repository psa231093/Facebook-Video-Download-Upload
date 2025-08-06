#!/usr/bin/env python3
"""
Facebook Video Uploader using Graph API
"""

import os
import requests
import json
from pathlib import Path
import time

class FacebookUploader:
    def __init__(self, access_token, user_id):
        self.access_token = access_token
        self.user_id = user_id
        self.graph_api_url = "https://graph.facebook.com/v18.0"
        
    def upload_video(self, video_path, title="", description=""):
        """Upload a video to Facebook profile"""
        print(f"\n📤 FACEBOOK VIDEO UPLOAD STARTED")
        print(f"📝 Parameters:")
        print(f"   - Video path: {video_path}")
        try:
            print(f"   - Title: {title}")
            print(f"   - Description: {description}")
        except UnicodeEncodeError:
            print("   - Title: (contains Unicode characters)")
            print("   - Description: (contains Unicode characters)")
        print(f"   - User ID: {self.user_id}")
        print(f"[DEBUG] Title length: {len(title)}")
        print(f"[DEBUG] Description length: {len(description)}")
        print(f"[DEBUG] Title empty: {not bool(title.strip() if title else True)}")
        print(f"[DEBUG] Description empty: {not bool(description.strip() if description else True)}")
        
        video_file = Path(video_path)
        if not video_file.exists():
            print(f"❌ Video file not found: {video_path}")
            return False, "Video file not found"
        
        file_size = video_file.stat().st_size
        print(f"📊 Video file size: {file_size} bytes ({file_size / (1024*1024):.1f} MB)")
        
        try:
            # Step 1: Initialize upload session
            print(f"🔧 Step 1: Initializing upload session...")
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
            publish_response = self._publish_video(upload_session_id, title, description)
            
            if not publish_response:
                return False, "Failed to publish video"
            
            print(f"✅ Video published successfully!")
            print(f"📋 Video details:")
            print(f"   - Video ID: {video_id}")
            print(f"   - Title: {title}")
            
            # Construct Facebook video URL
            facebook_url = f"https://www.facebook.com/{self.user_id}/videos/{video_id}"
            print(f"   - Facebook URL: {facebook_url}")
            
            return True, {
                'video_id': video_id,
                'title': title,
                'description': description,
                'upload_session_id': upload_session_id,
                'facebook_url': facebook_url
            }
            
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
    
    def _publish_video(self, upload_session_id, title, description=""):
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
        
        try:
            print(f"🚀 Publishing video with data: {data}")
        except UnicodeEncodeError:
            print("🚀 Publishing video with data (contains Unicode characters)")
            print(f"[DEBUG] Data keys: {list(data.keys())}")
            if 'title' in data:
                print(f"[DEBUG] Title in data: Yes (length: {len(data['title'])})")
            if 'description' in data:
                print(f"[DEBUG] Description in data: Yes (length: {len(data['description'])})")
        
        try:
            response = requests.post(url, data=data, timeout=60)
            print(f"📥 Publish response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"📋 Publish response: {result}")
                return result
            else:
                print(f"❌ Publish failed:")
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"💥 Exception in publish_video: {e}")
            return None
    
    def test_connection(self):
        """Test Facebook API connection"""
        print(f"🧪 Testing Facebook API connection...")
        
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


def main():
    """Test function"""
    print("Facebook Video Uploader Test")
    print("This is a test of the Facebook video upload functionality")
    print("Make sure to set your access token and user ID in the code")

if __name__ == "__main__":
    main()