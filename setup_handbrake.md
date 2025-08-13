# HandBrake CLI Setup Instructions

## Download HandBrake CLI

1. Visit: https://handbrake.fr/downloads.php
2. Look for "Windows CLI" section
3. Download the ZIP file (NOT the regular HandBrake.exe installer)

## Install HandBrake CLI

1. Extract the ZIP file to: `C:\HandBrake\`
2. You should have: `C:\HandBrake\HandBrakeCLI.exe`

## Add to System PATH

### Method 1: Windows Settings
1. Press `Win + R`, type `sysdm.cpl`, press Enter
2. Click "Environment Variables..."
3. Under "System variables", find and select "Path"
4. Click "Edit..." then "New"
5. Add: `C:\HandBrake\` (or wherever you extracted it)
6. Click "OK" on all dialogs
7. **Restart Command Prompt/Terminal**

### Method 2: PowerShell (Admin)
```powershell
# Run PowerShell as Administrator
$env:PATH += ";C:\HandBrake\"
[Environment]::SetEnvironmentVariable("PATH", $env:PATH, [EnvironmentVariableTarget]::Machine)
```

## Test Installation

Open a NEW Command Prompt and run:
```cmd
HandBrakeCLI --version
```

You should see version information like:
```
HandBrake 1.x.x (CLI)
```

## Alternative: Portable Setup

If you don't want to modify PATH, you can:

1. Place `HandBrakeCLI.exe` directly in your project folder:
   `C:\Users\pablo\Downloads\Facebook-Video-Download-Upload-autoupload-fix\Facebook-Video-Download-Upload-autoupload-fix\HandBrakeCLI.exe`

2. The script will find it automatically in the current directory.