"""
Simple script to test spotdl functionality directly.
Run this file to check if spotdl is properly installed and working.
"""

import os
import subprocess
import sys

def test_spotdl():
    print("Testing spotdl installation...")
    
    try:
        # Test if spotdl is installed
        version_process = subprocess.run(
            ["spotdl", "--version"],
            text=True,
            capture_output=True
        )
        
        if version_process.returncode == 0:
            print(f"✅ spotdl is installed: {version_process.stdout.strip()}")
        else:
            print(f"❌ spotdl check failed: {version_process.stderr.strip()}")
            print("Try installing spotdl with: pip install spotdl")
            return False
            
        # Create test directory
        test_dir = os.path.join("data", "test_download")
        os.makedirs(test_dir, exist_ok=True)
        print(f"Created test directory: {test_dir}")
        
        # Test download a short song (Spotify URI: 4cOdK2wGLETKBW3PvgPWqT - 'Für Elise')
        test_track = "4cOdK2wGLETKBW3PvgPWqT"
        test_url = f"https://open.spotify.com/track/{test_track}"
        
        print(f"Attempting to download test track: {test_url}")
        
        # Run download command
        download_process = subprocess.run(
            ["spotdl", "--output", test_dir, test_url],
            text=True,
            capture_output=True
        )
        
        # Check result
        if download_process.returncode == 0:
            print(f"✅ Test download succeeded!")
            print(f"Output: {download_process.stdout}")
            return True
        else:
            print(f"❌ Test download failed: {download_process.stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ spotdl command not found! Make sure spotdl is installed and in your PATH.")
        print("Install with: pip install spotdl")
        return False
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return False

if __name__ == "__main__":
    success = test_spotdl()
    if success:
        print("\nspotdl is working correctly! 🎉")
    else:
        print("\nThere are issues with your spotdl installation. Please fix them before using the downloader.")
        
    # Exit with appropriate status code
    sys.exit(0 if success else 1)
