#!/usr/bin/env python3
"""
Simple HandBrake integration without Unicode issues
"""

import subprocess
import os
from pathlib import Path

class SimpleHandBrake:
    def __init__(self):
        self.handbrake_path = r"C:\Users\pablo\Downloads\HandBrakeCLI-1.10.0-win-x86_64\HandBrakeCLI.exe"
    
    def is_available(self):
        """Check if HandBrake CLI is available"""
        try:
            if Path(self.handbrake_path).exists():
                print(f"HANDBRAKE: Found HandBrake at {self.handbrake_path}")
                return True
            else:
                print(f"HANDBRAKE: HandBrake not found at {self.handbrake_path}")
                return False
        except Exception as e:
            print(f"HANDBRAKE: Error checking HandBrake: {e}")
            return False
    
    def process_video(self, input_path):
        """Process video with HandBrake - simple version"""
        if not self.is_available():
            return False, "HandBrake CLI not found"
        
        input_file = Path(input_path)
        if not input_file.exists():
            return False, f"Input file not found: {input_path}"
        
        # Handle long filenames by using a shorter temporary name for processing
        original_filename = input_file.name
        if len(original_filename) > 150:  # Windows has 260 char limit, HandBrake seems to have issues with very long names
            print(f"HANDBRAKE: Long filename detected ({len(original_filename)} chars), using temporary name")
            
            # Create a shorter temporary filename for processing
            import hashlib
            file_hash = hashlib.md5(original_filename.encode()).hexdigest()[:8]
            temp_input = input_file.parent / f"temp_handbrake_input_{file_hash}.mp4"
            temp_output = input_file.parent / f"temp_handbrake_output_{file_hash}.mp4"
            
            # Copy original to temp location
            import shutil
            try:
                shutil.copy2(input_file, temp_input)
                print(f"HANDBRAKE: Created temporary input: {temp_input.name}")
            except Exception as e:
                return False, f"Failed to create temporary file: {e}"
            
            # Process the temp file
            success, result = self._process_file(temp_input, temp_output)
            
            # Clean up and move result back
            try:
                temp_input.unlink(missing_ok=True)  # Remove temp input
                if success and temp_output.exists():
                    # Create final output filename
                    final_output = input_file.parent / f"{input_file.stem}_processed.mp4"
                    shutil.move(temp_output, final_output)
                    print(f"HANDBRAKE: Moved result to: {final_output.name}")
                    return True, str(final_output)
                else:
                    temp_output.unlink(missing_ok=True)  # Clean up temp output if failed
                    return False, result
            except Exception as e:
                return False, f"Failed to handle temporary files: {e}"
        else:
            # Normal processing for shorter filenames
            output_file = input_file.parent / f"{input_file.stem}_processed.mp4"
            return self._process_file(input_file, output_file)
    
    def _process_file(self, input_file, output_file):
        """Internal method to process a file with HandBrake"""
        
        print(f"HANDBRAKE: Starting processing...")
        print(f"HANDBRAKE: Input: {input_file}")
        print(f"HANDBRAKE: Output: {output_file}")
        
        # HandBrake command optimized for Facebook upload (smaller file size)
        cmd = [
            self.handbrake_path,
            "--input", str(input_file),
            "--output", str(output_file),
            "--width", "1280",
            "--height", "720",
            "--rate", "24",
            "--cfr",
            "--encoder", "x264",
            "--quality", "28",  # Higher number = smaller file size (was 22)
            "--encoder-preset", "fast",  # Faster encoding, smaller files
            "--vb", "1500"  # Video bitrate 1.5Mbps for Facebook compatibility
        ]
        
        try:
            print("HANDBRAKE: Running HandBrake command...")
            print(f"HANDBRAKE: Command: {' '.join(cmd)}")
            
            # Run HandBrake
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            print(f"HANDBRAKE: Return code: {result.returncode}")
            
            if result.stdout:
                print(f"HANDBRAKE: stdout: {result.stdout}")
            if result.stderr:
                print(f"HANDBRAKE: stderr: {result.stderr}")
            
            if result.returncode == 0:
                if output_file.exists():
                    print(f"HANDBRAKE: SUCCESS - Output file created: {output_file}")
                    return True, str(output_file)
                else:
                    print("HANDBRAKE: FAILED - No output file created")
                    return False, "No output file created"
            else:
                print(f"HANDBRAKE: FAILED - Return code: {result.returncode}")
                return False, f"HandBrake failed with code {result.returncode}: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            print("HANDBRAKE: TIMEOUT - HandBrake processing took too long")
            return False, "HandBrake processing timeout"
        except Exception as e:
            print(f"HANDBRAKE: EXCEPTION - {e}")
            return False, f"HandBrake exception: {e}"