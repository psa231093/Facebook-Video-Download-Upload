#!/usr/bin/env python3
"""
Startup script for Facebook Video Downloader Web Interface
"""

import sys
import subprocess
import os
from pathlib import Path

def check_dependencies():
    """Check and install required dependencies"""
    try:
        import flask
        print("✓ Flask is installed")
    except ImportError:
        print("Installing Flask...")
        subprocess.run([sys.executable, "-m", "pip", "install", "flask"], check=True)
        print("✓ Flask installed successfully")
    
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        print("✓ yt-dlp is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Installing yt-dlp...")
        subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp"], check=True)
        print("✓ yt-dlp installed successfully")

def main():
    """Main startup function"""
    print("=" * 60)
    print("🎥 Facebook Video Downloader - Web Interface")
    print("=" * 60)
    
    # Check dependencies
    print("\nChecking dependencies...")
    try:
        check_dependencies()
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        print("Please install manually: pip install flask yt-dlp")
        input("Press Enter to continue anyway...")
    
    # Create downloads directory
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)
    print(f"✓ Downloads directory ready: {downloads_dir.absolute()}")
    
    print("\n" + "=" * 60)
    print("🚀 Starting web server...")
    print("📱 Access the interface at: http://localhost:5000")
    print("🛑 Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Start the Flask app
    try:
        from app import app
        app.run(debug=False, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        print("Make sure all files are in place and try again.")

if __name__ == "__main__":
    main()