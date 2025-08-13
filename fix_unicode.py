#!/usr/bin/env python3
"""Fix all Unicode emoji issues in app.py"""

import re

def fix_unicode_in_file():
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace all emoji patterns with text equivalents
    replacements = {
        '📤': 'FACEBOOK:',
        '📹': 'VIDEO:',
        '📝': 'INFO:',
        '✅': 'SUCCESS:',
        '❌': 'ERROR:',
        '🎉': 'COMPLETE:',
        '🔄': 'PROGRESS:',
        '💥': 'EXCEPTION:',
        '⚠️': 'WARNING:',
        '🍪': 'COOKIES:',
        '🔓': 'PUBLIC:',
        '📊': 'STATS:',
        '📋': 'LIST:',
        '🎬': 'VIDEO:',
        '🧹': 'CLEANUP:',
        '⏸️': 'PAUSED:',
        '🚀': 'START:',
        '🔧': 'CONFIG:',
        '🎯': 'TARGET:',
        '📁': 'FILE:',
        '⏰': 'TIME:',
    }
    
    for emoji, replacement in replacements.items():
        content = content.replace(emoji, replacement)
    
    # Write back the cleaned content
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Fixed all Unicode emojis in app.py")

if __name__ == "__main__":
    fix_unicode_in_file()