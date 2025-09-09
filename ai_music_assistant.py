#!/usr/bin/env python3
"""
AI Music Assistant Module

This module provides multimodal AI capabilities for music discovery,
including image analysis, text extraction, and music recommendation
using Llama 3.2 Vision and other AI models.
"""

import os
import io
import json
import base64
import logging
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

# AI Provider imports (optional)
OLLAMA_AVAILABLE = False
OPENAI_AVAILABLE = False
ANTHROPIC_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    pass

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    pass

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    pass

logger = logging.getLogger("spotify_burner.ai_assistant")

class AIMusicAssistant:
    """AI-powered music discovery assistant with multimodal capabilities."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the AI Music Assistant.
        
        Args:
            config: Configuration dictionary containing AI settings
        """
        self.config = config or {}
        self.provider = self.config.get('ai_provider', 'ollama').lower()
        self.model = self.config.get('ai_model', 'llama3.2-vision:latest')
        self.enable_vision = self.config.get('ai_enable_vision', True)
        
        # Initialize provider clients
        self.ollama_client = None
        self.openai_client = None
        self.anthropic_client = None
        
        self._initialize_providers()
        
    def _initialize_providers(self):
        """Initialize AI provider clients based on configuration."""
        try:
            if self.provider == 'ollama' and OLLAMA_AVAILABLE:
                self.ollama_client = ollama
                logger.info("Initialized Ollama client")
                
            elif self.provider == 'openai' and OPENAI_AVAILABLE:
                api_key = os.getenv('OPENAI_API_KEY')
                if api_key:
                    self.openai_client = openai.OpenAI(api_key=api_key)
                    logger.info("Initialized OpenAI client")
                else:
                    logger.warning("OpenAI API key not found in environment variables")
                    
            elif self.provider == 'anthropic' and ANTHROPIC_AVAILABLE:
                api_key = os.getenv('ANTHROPIC_API_KEY')
                if api_key:
                    self.anthropic_client = anthropic.Anthropic(api_key=api_key)
                    logger.info("Initialized Anthropic client")
                else:
                    logger.warning("Anthropic API key not found in environment variables")
                    
        except Exception as e:
            logger.error(f"Error initializing AI provider '{self.provider}': {e}")
    
    def is_available(self) -> bool:
        """Check if AI functionality is available."""
        if not Image:
            return False
            
        if self.provider == 'ollama':
            return OLLAMA_AVAILABLE and self.ollama_client is not None
        elif self.provider == 'openai':
            return OPENAI_AVAILABLE and self.openai_client is not None
        elif self.provider == 'anthropic':
            return ANTHROPIC_AVAILABLE and self.anthropic_client is not None
            
        return False
    
    def get_availability_status(self) -> Dict[str, Any]:
        """Get detailed availability status for debugging."""
        return {
            "pillow_available": Image is not None,
            "ollama_available": OLLAMA_AVAILABLE,
            "openai_available": OPENAI_AVAILABLE,
            "anthropic_available": ANTHROPIC_AVAILABLE,
            "current_provider": self.provider,
            "provider_client_initialized": self.is_available(),
            "vision_enabled": self.enable_vision,
            "model": self.model
        }
    
    def analyze_image(self, image_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """Analyze an image for musical content and context.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing analysis results or None if failed
        """
        if not self.is_available() or not self.enable_vision:
            logger.warning("AI vision functionality not available")
            return None
            
        try:
            # Load and validate image
            image_path = Path(image_path)
            if not image_path.exists():
                logger.error(f"Image file not found: {image_path}")
                return None
                
            # Process image based on provider
            if self.provider == 'ollama':
                return self._analyze_with_ollama(image_path)
            elif self.provider == 'openai':
                return self._analyze_with_openai(image_path)
            elif self.provider == 'anthropic':
                return self._analyze_with_anthropic(image_path)
                
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return None
            
        return None
    
    def _analyze_with_ollama(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze image using Ollama with Llama 3.2 Vision."""
        try:
            prompt = """Analyze this image for musical content. Look for:
1. Album covers, band logos, or artist names
2. Concert posters or music event information
3. Musical instruments or equipment
4. Song lyrics or music sheets
5. Music-related text or branding

Provide a structured response with:
- detected_artists: List of any artist names found
- detected_albums: List of any album names found  
- detected_songs: List of any song titles found
- music_genre: Likely music genre based on visual style
- search_keywords: Relevant keywords for music search
- confidence: Confidence level (0.0-1.0)
- description: Brief description of what was found

Respond in valid JSON format only."""

            # Convert image to base64 for Ollama
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            response = self.ollama_client.generate(
                model=self.model,
                prompt=prompt,
                images=[image_data]
            )
            
            # Parse JSON response
            result = json.loads(response['response'])
            result['provider'] = 'ollama'
            result['model'] = self.model
            
            return result
            
        except Exception as e:
            logger.error(f"Ollama analysis error: {e}")
            return None
    
    def _analyze_with_openai(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze image using OpenAI GPT-4 Vision."""
        try:
            # Convert image to base64
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this image for musical content. Look for album covers, artist names, concert posters, instruments, or any music-related information. Respond in JSON format with: detected_artists (list), detected_albums (list), detected_songs (list), music_genre (string), search_keywords (list), confidence (0.0-1.0), description (string)."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            # Parse JSON response
            result = json.loads(response.choices[0].message.content)
            result['provider'] = 'openai'
            result['model'] = 'gpt-4-vision-preview'
            
            return result
            
        except Exception as e:
            logger.error(f"OpenAI analysis error: {e}")
            return None
    
    def _analyze_with_anthropic(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze image using Anthropic Claude 3 Vision."""
        try:
            # Convert image to base64
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
                
            # Detect image format
            image_format = image_path.suffix.lower().replace('.', '')
            if image_format == 'jpg':
                image_format = 'jpeg'
            
            message = self.anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": f"image/{image_format}",
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": "Analyze this image for musical content. Look for album covers, artist names, concert posters, instruments, or any music-related information. Respond in JSON format with: detected_artists (list), detected_albums (list), detected_songs (list), music_genre (string), search_keywords (list), confidence (0.0-1.0), description (string)."
                            }
                        ]
                    }
                ]
            )
            
            # Parse JSON response
            result = json.loads(message.content[0].text)
            result['provider'] = 'anthropic'
            result['model'] = 'claude-3-sonnet'
            
            return result
            
        except Exception as e:
            logger.error(f"Anthropic analysis error: {e}")
            return None
    
    def generate_search_queries(self, analysis_result: Dict[str, Any]) -> List[str]:
        """Generate Spotify search queries based on image analysis.
        
        Args:
            analysis_result: Result from analyze_image()
            
        Returns:
            List of search query strings
        """
        if not analysis_result:
            return []
            
        queries = []
        
        # Artist-specific queries
        for artist in analysis_result.get('detected_artists', []):
            queries.append(f'artist:"{artist}"')
            
        # Album-specific queries
        for album in analysis_result.get('detected_albums', []):
            queries.append(f'album:"{album}"')
            
        # Song-specific queries
        for song in analysis_result.get('detected_songs', []):
            queries.append(f'track:"{song}"')
            
        # Keyword-based queries
        keywords = analysis_result.get('search_keywords', [])
        if keywords:
            queries.append(' '.join(keywords[:3]))  # Top 3 keywords
            
        # Genre-based query
        genre = analysis_result.get('music_genre')
        if genre:
            queries.append(f'genre:"{genre}"')
            
        # Remove duplicates and limit results
        queries = list(dict.fromkeys(queries))[:5]
        
        return queries
    
    def analyze_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Analyze text for musical content and generate search suggestions.
        
        Args:
            text: Text to analyze (from OCR, user input, etc.)
            
        Returns:
            Analysis results similar to image analysis
        """
        if not self.is_available():
            return None
            
        try:
            if self.provider == 'ollama':
                return self._analyze_text_with_ollama(text)
            elif self.provider == 'openai':
                return self._analyze_text_with_openai(text)
            elif self.provider == 'anthropic':
                return self._analyze_text_with_anthropic(text)
                
        except Exception as e:
            logger.error(f"Error analyzing text: {e}")
            return None
            
        return None
    
    def _analyze_text_with_ollama(self, text: str) -> Optional[Dict[str, Any]]:
        """Analyze text using Ollama."""
        try:
            prompt = f"""Analyze this text for musical content: "{text}"

Look for artist names, album titles, song names, genre references, or music-related information.

Respond in valid JSON format with:
- detected_artists: List of artist names found
- detected_albums: List of album names found
- detected_songs: List of song titles found
- music_genre: Likely music genre
- search_keywords: Relevant keywords for music search
- confidence: Confidence level (0.0-1.0)
- description: Brief description of findings"""

            response = self.ollama_client.generate(
                model=self.model,
                prompt=prompt
            )
            
            result = json.loads(response['response'])
            result['provider'] = 'ollama'
            result['model'] = self.model
            
            return result
            
        except Exception as e:
            logger.error(f"Ollama text analysis error: {e}")
            return None
    
    def _analyze_text_with_openai(self, text: str) -> Optional[Dict[str, Any]]:
        """Analyze text using OpenAI."""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "user",
                        "content": f"""Analyze this text for musical content: "{text}"

Look for artist names, album titles, song names, or music-related information. Respond in JSON format with: detected_artists (list), detected_albums (list), detected_songs (list), music_genre (string), search_keywords (list), confidence (0.0-1.0), description (string)."""
                    }
                ],
                max_tokens=300
            )
            
            result = json.loads(response.choices[0].message.content)
            result['provider'] = 'openai'
            result['model'] = 'gpt-3.5-turbo'
            
            return result
            
        except Exception as e:
            logger.error(f"OpenAI text analysis error: {e}")
            return None
    
    def _analyze_text_with_anthropic(self, text: str) -> Optional[Dict[str, Any]]:
        """Analyze text using Anthropic Claude."""
        try:
            message = self.anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Analyze this text for musical content: "{text}"

Look for artist names, album titles, song names, or music-related information. Respond in JSON format with: detected_artists (list), detected_albums (list), detected_songs (list), music_genre (string), search_keywords (list), confidence (0.0-1.0), description (string)."""
                    }
                ]
            )
            
            result = json.loads(message.content[0].text)
            result['provider'] = 'anthropic'
            result['model'] = 'claude-3-haiku'
            
            return result
            
        except Exception as e:
            logger.error(f"Anthropic text analysis error: {e}")
            return None
    
    def extract_text_from_image(self, image_path: Union[str, Path]) -> Optional[str]:
        """Extract text from image using OCR (placeholder for OCR functionality).
        
        Args:
            image_path: Path to image file
            
        Returns:
            Extracted text or None if failed
        """
        # This is a placeholder - in a full implementation, you would use
        # OCR libraries like pytesseract or cloud OCR APIs
        logger.info(f"OCR extraction requested for {image_path}")
        return None
    
    def supported_file_types(self) -> List[str]:
        """Get list of supported file types for analysis."""
        image_types = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        text_types = ['.txt', '.md', '.pdf'] if self.is_available() else []
        
        return image_types + text_types