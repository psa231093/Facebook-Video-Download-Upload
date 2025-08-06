#!/usr/bin/env python3
"""
Windows setup script for Facebook Video Downloader
"""

import sys
import subprocess
import os
from pathlib import Path

def check_python():
    """Check Python installation"""
    print("=== Checking Python Installation ===")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    
    # Check if we're using the Microsoft Store Python
    if "WindowsApps" in sys.executable:
        print("⚠️  You're using Microsoft Store Python")
        print("This might cause issues. Consider installing Python from python.org")
        print("But let's try to continue...")
    else:
        print("✓ Python looks good")
    
    return True

def install_packages():
    """Install required packages"""
    print("\n=== Installing Required Packages ===")
    
    packages = ["flask", "yt-dlp"]
    
    for package in packages:
        print(f"Installing {package}...")
        try:
            # Try different methods to install
            methods = [
                [sys.executable, "-m", "pip", "install", package],
                ["python", "-m", "pip", "install", package],
                ["py", "-m", "pip", "install", package]
            ]
            
            success = False
            for method in methods:
                try:
                    result = subprocess.run(method, 
                                          capture_output=True, text=True, 
                                          timeout=120)  # 2 minute timeout
                    if result.returncode == 0:
                        print(f"✓ {package} installed successfully")
                        success = True
                        break
                    else:
                        print(f"Method {method[0]} failed: {result.stderr}")
                except FileNotFoundError:
                    print(f"Method {method[0]} not found")
                    continue
                except subprocess.TimeoutExpired:
                    print(f"Method {method[0]} timed out")
                    continue
            
            if not success:
                print(f"❌ Failed to install {package}")
                print("Try installing manually:")
                print(f"1. Open Command Prompt as Administrator")
                print(f"2. Run: python -m pip install {package}")
                return False
                
        except Exception as e:
            print(f"❌ Error installing {package}: {e}")
            return False
    
    return True

def test_imports():
    """Test if we can import required modules"""
    print("\n=== Testing Imports ===")
    
    modules = [
        ("flask", "Flask web framework"),
        ("subprocess", "System commands"),
        ("pathlib", "File path handling")
    ]
    
    for module, description in modules:
        try:
            __import__(module)
            print(f"✓ {module} - {description}")
        except ImportError as e:
            print(f"❌ {module} - {e}")
            return False
    
    # Test yt-dlp
    try:
        result = subprocess.run([sys.executable, "-c", "import yt_dlp; print('yt-dlp imported')"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ yt-dlp - Video downloader")
        else:
            print(f"❌ yt-dlp import failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ yt-dlp test failed: {e}")
        return False
    
    return True

def create_batch_files():
    """Create easy-to-use batch files"""
    print("\n=== Creating Batch Files ===")
    
    # Update the existing batch file
    batch_content = f'''@echo off
echo Starting Facebook Video Downloader...
echo.
echo Using Python: {sys.executable}
echo.

"{sys.executable}" app.py

echo.
echo Server stopped. Press any key to close...
pause > nul
'''
    
    batch_path = Path("start_server.bat")
    with open(batch_path, 'w') as f:
        f.write(batch_content)
    
    print(f"✓ Updated {batch_path}")
    
    # Create installation batch
    install_batch = '''@echo off
echo Installing Python packages...
python -m pip install --upgrade pip
python -m pip install flask yt-dlp
echo.
echo Installation complete!
pause
'''
    
    install_path = Path("install_packages.bat")
    with open(install_path, 'w') as f:
        f.write(install_batch)
    
    print(f"✓ Created {install_path}")
    
    return True

def main():
    """Main setup function"""
    print("🔧 Windows Setup for Facebook Video Downloader")
    print("=" * 60)
    
    try:
        # Check Python
        if not check_python():
            return False
        
        # Install packages
        if not install_packages():
            print("\n❌ Package installation failed!")
            print("\nManual installation steps:")
            print("1. Open Command Prompt or PowerShell as Administrator")
            print("2. Run: python -m pip install flask yt-dlp")
            print("3. If that fails, try: py -m pip install flask yt-dlp")
            return False
        
        # Test imports
        if not test_imports():
            print("\n❌ Import tests failed!")
            return False
        
        # Create batch files
        create_batch_files()
        
        print("\n" + "=" * 60)
        print("🎉 Setup completed successfully!")
        print("\nHow to start the server:")
        print("1. Double-click 'start_server.bat'")
        print("2. Or run: python app.py")
        print("3. Open browser to: http://localhost:5000")
        print("\nIf you still have issues:")
        print("- Try running as Administrator")
        print("- Check Windows Defender/Antivirus isn't blocking")
        print("- Try: py app.py instead of python app.py")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    input("\nPress Enter to close...")
    sys.exit(0 if success else 1)