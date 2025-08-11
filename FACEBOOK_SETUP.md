# Facebook Auto-Upload Setup Guide

This guide will help you set up automatic Facebook video uploads after downloads.

## 🔧 Setup Steps

### 1. Get Facebook Access Token

1. Go to [Facebook for Developers](https://developers.facebook.com/)
2. Create a new app or use an existing one
3. Go to **Graph API Explorer**
4. Select your app
5. Generate an access token with these permissions:
   - `publish_video`
   - `pages_manage_posts` (if uploading to a page)
   - `user_videos` (for personal profile)

### 2. Configure Your Credentials

**Option A: Using .env file (Recommended)**
1. Copy `.env.example` to `.env`
2. Add your access token:
```
FACEBOOK_ACCESS_TOKEN=your_access_token_here
FACEBOOK_USER_ID=10162733735568382
FACEBOOK_AUTO_UPLOAD=true
```

**Option B: Using config.py**
1. Open `config.py`
2. Update the `FACEBOOK_CONFIG` section:
```python
FACEBOOK_CONFIG = {
    "access_token": "your_access_token_here",
    "user_id": "10162733735568382",
    "auto_upload_enabled": True,
    # ... other settings
}
```

### 3. Install Required Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `requests` - For Facebook API calls
- `python-dotenv` - For .env file support

### 4. Test the Setup

1. Start the server:
```bash
python app.py
```

2. Go to: `http://localhost:5000`

3. Click **"Batch Download"** tab

4. Check **"Automatically upload downloaded videos to Facebook"**

5. Add some Facebook video URLs and test

## 🎬 How It Works

### Workflow:
1. **Download** → Video downloaded from Facebook
2. **Process** → Video file detected in downloads folder
3. **Upload** → Video uploaded to your Facebook profile
4. **Complete** → Success/failure status reported

### Upload Process:
1. **Initialize** → Create upload session with Facebook
2. **Transfer** → Upload video file data
3. **Publish** → Publish video with title and description

## ⚙️ Configuration Options

### Web Interface Settings:
- ✅ **Auto-upload enabled** - Toggle automatic uploads
- 📝 **Title prefix** - Optional prefix for video titles
- 📄 **Description** - Custom description for uploaded videos

### Config File Settings:
```python
FACEBOOK_CONFIG = {
    "access_token": "",  # Your access token
    "user_id": "10162733735568382",  # Your user ID
    "auto_upload_enabled": False,  # Global enable/disable
    "default_title_prefix": "",  # Default title prefix
    "default_description": "Uploaded via Facebook Video Downloader",
    "max_file_size_mb": 1024,  # Max file size (1GB)
}
```

## 🔍 Troubleshooting

### Common Issues:

1. **"No Facebook access token"**
   - Add your token to `.env` or `config.py`
   - Make sure the token has required permissions

2. **"Upload failed"**
   - Check if the video file is too large (max 1GB)
   - Verify your access token is valid
   - Check server logs for detailed error messages

3. **"API request failed"**
   - Token might be expired
   - Check Facebook app permissions
   - Verify your user ID is correct

### Debug Mode:
Enable detailed logging by checking the server console output when uploads happen. Look for:
- 🚀 Upload initialization
- 📤 File transfer progress  
- ✅ Success confirmation
- ❌ Error details

## 🔐 Security Notes

- **Keep your access token secure** - Don't share it
- **Use .env file** - Don't commit tokens to version control
- **Token expiration** - Facebook tokens expire, you may need to refresh them
- **Permissions** - Only request necessary permissions

## 📊 Features

### Current Features:
- ✅ Automatic upload after download
- ✅ Custom video titles with prefix
- ✅ Custom video descriptions
- ✅ Progress tracking and status updates
- ✅ Error handling and reporting
- ✅ Web interface controls

### Upload Details:
- **Format support**: MP4, MKV, WebM
- **Max file size**: 1GB (Facebook limit)
- **Upload method**: Facebook Graph API v18.0
- **Privacy**: Videos uploaded to your profile/page
- **Title**: Customizable with prefix support
- **Description**: Configurable per upload

Your Facebook integration is now ready! Videos will be automatically uploaded to your Facebook profile after each successful download.