# 🎥 Facebook Video Downloader & Auto-Uploader

A powerful web-based tool to download Facebook videos and automatically re-upload them to your Facebook page or profile with custom titles and descriptions.

## ✨ Features

### 📹 Video Download
- **Single Video Download**: Download individual Facebook videos
- **Batch Download**: Download multiple videos at once
- **Private Video Support**: Use cookies for authentication to download private content
- **High Quality**: Downloads best available quality (MP4, MKV, WebM)
- **Metadata**: Saves video thumbnails and metadata

### 🚀 Facebook Auto-Upload
- **Automatic Upload**: Instantly upload downloaded videos to your Facebook page/profile
- **Custom Titles**: Add prefixes and custom titles to uploaded videos
- **Custom Descriptions**: Set personalized descriptions for each upload
- **Progress Tracking**: Real-time progress indicators for uploads
- **Error Handling**: Comprehensive error reporting and recovery

### 🌐 Web Interface
- **Modern UI**: Clean, responsive web interface
- **Real-time Progress**: Live progress tracking for downloads and uploads
- **Batch Statistics**: Detailed stats for batch operations
- **File Management**: Browse and download saved videos
- **Two Modes**: Single video and batch download modes

## 🚀 Quick Start

### Prerequisites
- Python 3.7 or higher
- Git (for cloning)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/facebook-video-downloader.git
   cd facebook-video-downloader
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Facebook API:**
   - Copy `.env.example` to `.env`
   - Add your Facebook access token and user/page ID
   - See [FACEBOOK_SETUP.md](FACEBOOK_SETUP.md) for detailed setup instructions

4. **Start the server:**
   ```bash
   python app.py
   ```

5. **Open in browser:**
   ```
   http://localhost:5000
   ```

## 📝 Configuration

### Environment Variables (.env)
```env
# Facebook API Credentials
FACEBOOK_ACCESS_TOKEN=your_access_token_here
FACEBOOK_USER_ID=your_user_or_page_id
FACEBOOK_AUTO_UPLOAD=true
```

### Configuration File (config.py)
```python
FACEBOOK_CONFIG = {
    "access_token": "your_token_here",
    "user_id": "your_page_id",
    "auto_upload_enabled": True,
    "default_title_prefix": "[Downloaded] ",
    "default_description": "Uploaded via Facebook Video Downloader"
}
```

## 🎯 Usage

### Single Video Download
1. Go to the **Single Video** tab
2. Paste a Facebook video URL
3. (Optional) Enable Facebook auto-upload
4. Add custom title prefix and description
5. Click **Download Video**

### Batch Download
1. Go to the **Batch Download** tab
2. Paste multiple Facebook video URLs (one per line)
3. Configure Facebook upload settings
4. Click **Start Batch Download**

### Private Videos
1. Check **"Use authentication"**
2. Paste your Facebook cookies in Netscape format
3. See [AUTHENTICATION.md](AUTHENTICATION.md) for cookie extraction guide

## 🛠️ Technical Details

### Architecture
- **Backend**: Flask (Python)
- **Video Processing**: yt-dlp
- **Facebook API**: Graph API v18.0
- **Frontend**: HTML/CSS/JavaScript
- **Storage**: Local file system

### Video Upload Process
1. **Initialize**: Create upload session with Facebook
2. **Transfer**: Upload video file data in chunks
3. **Publish**: Publish video with title and description

### Supported Formats
- **Input**: Facebook video URLs
- **Output**: MP4, MKV, WebM
- **Quality**: Best available (up to 1080p)

## 🔐 Security & Privacy

### Data Protection
- **No Server Storage**: Cookies and tokens are not stored on the server
- **Local Processing**: All video processing happens locally
- **Secure API**: Uses official Facebook Graph API
- **Environment Variables**: Sensitive data stored in `.env` files

### Token Security
- Keep your Facebook access token secure
- Don't commit tokens to version control
- Regenerate tokens periodically
- Use page tokens for better security

## 🐛 Troubleshooting

### Common Issues

**"No Facebook access token configured"**
- Add your token to `.env` or `config.py`
- Ensure token has required permissions

**"Upload failed" / "API request failed"**
- Check if token is expired
- Verify page permissions
- Ensure video file size is under 1GB

**"pip not recognized"**
- Use `python -m pip install -r requirements.txt`
- Or run the provided `install_packages.bat`

## ⚠️ Disclaimer

This tool is for educational and personal use only. Users are responsible for complying with Facebook's Terms of Service and applicable laws. The developers are not responsible for any misuse of this software.

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloading functionality
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Facebook Graph API](https://developers.facebook.com/docs/graph-api) - Video upload functionality

---

**Made with ❤️ for content creators and social media managers**