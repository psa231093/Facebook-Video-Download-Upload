@echo off
echo Installing Python packages for Facebook Video Downloader...
echo.

echo Trying different Python commands...
echo.

echo Method 1: Using 'python'
python -m pip install --upgrade pip
python -m pip install flask yt-dlp
if %errorlevel% == 0 (
    echo Success with 'python' command!
    goto :success
)

echo.
echo Method 2: Using 'py'  
py -m pip install --upgrade pip
py -m pip install flask yt-dlp
if %errorlevel% == 0 (
    echo Success with 'py' command!
    goto :success
)

echo.
echo Method 3: Direct pip (if available)
pip install flask yt-dlp
if %errorlevel% == 0 (
    echo Success with 'pip' command!
    goto :success
)

echo.
echo ❌ All methods failed!
echo.
echo Please try these manual steps:
echo 1. Install Python from https://python.org/downloads/
echo 2. Make sure to check "Add Python to PATH" during installation
echo 3. Restart your command prompt
echo 4. Try running this script again
echo.
goto :end

:success
echo.
echo ✅ Packages installed successfully!
echo.
echo Now you can run the server by:
echo 1. Double-clicking 'start_server.bat'
echo 2. Or running: python app.py
echo.

:end
echo Press any key to close...
pause > nul