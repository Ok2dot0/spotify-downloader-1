import os
import tempfile
import requests
from io import BytesIO
from PIL import Image
from spotify_burner import SpotifyBurner

app = SpotifyBurner()

# Test with a random image from picsum.photos
print('\nTesting with random image from picsum.photos:')
try:
    # Download the random image
    response = requests.get('https://picsum.photos/200')
    if response.status_code == 200:
        # Save to temp file
        temp_dir = tempfile.gettempdir()
        temp_image_path = os.path.join(temp_dir, "random_test_image.jpg")
        with open(temp_image_path, 'wb') as f:
            f.write(response.content)
        
        # Generate ASCII art
        random_art = app._generate_ascii_art_from_image(temp_image_path, width=60)
        print(random_art)
    else:
        print(f"Failed to download image: HTTP {response.status_code}")
except Exception as e:
    print(f"Error testing random image: {e}")

# Test fallback art
print('\nTesting fallback music note art:')
fallback_art = app._generate_fallback_album_art(width=40)
print(fallback_art)

