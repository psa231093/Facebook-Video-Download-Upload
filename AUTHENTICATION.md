# Facebook Authentication for Video Downloads

To download private or account-specific videos from Facebook, you'll need to authenticate using cookies.

## Method 1: Browser Extension (Recommended)

1. Install a browser extension like "Get cookies.txt LOCALLY" for Chrome/Firefox
2. Login to Facebook in your browser
3. Navigate to any Facebook page
4. Click the extension icon and export cookies as `cookies.txt`
5. Save the file in this directory

## Method 2: Manual Cookie Extraction

1. Login to Facebook in your browser
2. Open Developer Tools (F12)
3. Go to Application/Storage tab → Cookies → https://www.facebook.com
4. Copy all cookies to a text file in Netscape format

## Cookie File Format

The cookies.txt file should be in Netscape format:
```
# Netscape HTTP Cookie File
.facebook.com	TRUE	/	FALSE	1234567890	cookie_name	cookie_value
```

## Usage

Once you have your cookies file:

```bash
# Download with authentication
python facebook_downloader.py "https://www.facebook.com/watch/?v=123456789" cookies.txt

# Download without authentication (public videos only)
python facebook_downloader.py "https://www.facebook.com/watch/?v=123456789"
```

## Security Note

- Keep your cookies.txt file secure and don't share it
- The cookies contain your login session information
- Consider regenerating cookies periodically for security