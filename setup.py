#!/usr/bin/env python3
from setuptools import setup, find_packages
import os
import re

# Read version from the __init__.py file
VERSION = "2.0.0"
with open("spotify_burner.py") as f:
    content = f.read()
    match = re.search(r'VERSION = ["\']([^"\']+)["\']', content)
    if match:
        VERSION = match.group(1)

# Read description from README.md
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Define dependencies
install_requires = [
    "spotipy>=2.23.0",
    "spotdl>=4.2.1",
    "colorama>=0.4.6",
    "rich>=13.5.2",
    "requests>=2.31.0",
    "Pillow>=10.0.1",
    "python-dotenv>=1.0.0",
    "tqdm>=4.66.1",
    "concurrent-log-handler>=0.9.24",
    "yt-dlp>=2023.7.6",
]

# Define conditional dependencies
extras_require = {
    'windows': ["pywin32>=305", "comtypes>=1.2.0"],
    'dev': [
        "pytest>=7.4.0",
        "pytest-cov>=4.1.0",
        "pytest-mock>=3.11.1",
        "pytest-timeout>=2.1.0",
        "black>=23.7.0",
        "isort>=5.12.0",
        "flake8>=6.1.0",
    ]
}

# Setup configuration
setup(
    name="spotify-album-burner",
    version=VERSION,
    author="Spotify Album Burner Team",
    author_email="example@example.com",
    description="Search, download, and burn music from Spotify",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/username/spotify-burner",
    py_modules=["spotify_burner"],  # Main module is a single file
    entry_points={
        "console_scripts": [
            "spotify-burner=spotify_burner:main",
        ],
    },
    install_requires=install_requires,
    extras_require=extras_require,
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Video",
    ],
    keywords="spotify, music, download, burn, cd, dvd",
)