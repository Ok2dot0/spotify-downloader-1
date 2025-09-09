#!/usr/bin/env python3
"""
Demo script showing AI Music Discovery features.
This demonstrates what the AI functionality would do with actual AI providers.
"""

from ai_music_assistant import AIMusicAssistant
from pathlib import Path
import json

def demo_ai_features():
    """Demonstrate AI music discovery capabilities."""
    
    print("🎵 AI Music Discovery Demo")
    print("=" * 40)
    
    # Initialize AI Assistant
    assistant = AIMusicAssistant()
    
    print(f"\n📊 AI Status:")
    status = assistant.get_availability_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Demo 1: Text Analysis
    print(f"\n📝 Demo: Text Analysis")
    print("-" * 25)
    
    sample_texts = [
        "I love listening to Taylor Swift's Folklore album, especially the song Cardigan",
        "Looking for some good 80s rock music like Queen or AC/DC",
        "Need relaxing jazz piano music for studying",
        "Country music recommendations like Johnny Cash or Willie Nelson"
    ]
    
    for i, text in enumerate(sample_texts, 1):
        print(f"\n{i}. Input: \"{text[:50]}...\"")
        
        # Simulate what the AI would return
        mock_result = simulate_text_analysis(text)
        queries = assistant.generate_search_queries(mock_result)
        
        print(f"   → Generated {len(queries)} search queries:")
        for query in queries:
            print(f"     • {query}")
    
    # Demo 2: Image Analysis Simulation
    print(f"\n🖼️  Demo: Image Analysis (Simulated)")
    print("-" * 35)
    
    image_scenarios = [
        {
            "filename": "taylor_swift_folklore_cover.jpg",
            "description": "Album cover of Taylor Swift's Folklore",
            "detected": {
                'detected_artists': ['Taylor Swift'],
                'detected_albums': ['Folklore'],
                'music_genre': 'indie folk',
                'search_keywords': ['folklore', 'taylor swift', 'indie'],
                'confidence': 0.95
            }
        },
        {
            "filename": "concert_poster_queen.jpg", 
            "description": "Vintage Queen concert poster",
            "detected": {
                'detected_artists': ['Queen'],
                'music_genre': 'rock',
                'search_keywords': ['queen', 'bohemian rhapsody', 'rock', 'freddie mercury'],
                'confidence': 0.88
            }
        },
        {
            "filename": "vinyl_collection.jpg",
            "description": "Photo of vinyl record collection",
            "detected": {
                'detected_artists': ['The Beatles', 'Pink Floyd', 'Led Zeppelin'],
                'music_genre': 'classic rock',
                'search_keywords': ['vinyl', 'classic rock', '70s music'],
                'confidence': 0.75
            }
        }
    ]
    
    for scenario in image_scenarios:
        print(f"\n📷 Image: {scenario['filename']}")
        print(f"   Description: {scenario['description']}")
        
        queries = assistant.generate_search_queries(scenario['detected'])
        
        print(f"   → AI would detect: {scenario['detected']['detected_artists']}")
        print(f"   → Generated {len(queries)} search queries:")
        for query in queries:
            print(f"     • {query}")
    
    # Demo 3: Integration with Spotify Search
    print(f"\n🔍 Demo: Integration Flow")
    print("-" * 25)
    print("1. User uploads image or enters text")
    print("2. AI analyzes content for musical information")  
    print("3. AI generates optimized Spotify search queries")
    print("4. App searches Spotify using generated queries")
    print("5. User selects from results to download")
    print("6. Music downloads using existing functionality")
    
    print(f"\n📋 Supported Features:")
    print("✅ Multiple AI providers (Ollama, OpenAI, Anthropic)")
    print("✅ Image analysis with Llama 3.2 Vision")
    print("✅ Text analysis for music discovery")
    print("✅ Smart search query generation")
    print("✅ Seamless integration with existing app")
    print("✅ Graceful fallback when AI unavailable")
    
    print(f"\n🎛️  Configuration Options:")
    print("• AI_PROVIDER: ollama, openai, anthropic")
    print("• AI_MODEL: llama3.2-vision:latest, gpt-4-vision-preview, claude-3-sonnet")
    print("• AI_ENABLE_VISION: true/false")
    print("• Confidence thresholds and file size limits")

def simulate_text_analysis(text: str) -> dict:
    """Simulate what AI text analysis would return."""
    text_lower = text.lower()
    
    result = {
        'detected_artists': [],
        'detected_albums': [],
        'detected_songs': [],
        'music_genre': '',
        'search_keywords': [],
        'confidence': 0.7
    }
    
    # Simple keyword detection (real AI would be much more sophisticated)
    if 'taylor swift' in text_lower:
        result['detected_artists'].append('Taylor Swift')
        if 'folklore' in text_lower:
            result['detected_albums'].append('Folklore')
        if 'cardigan' in text_lower:
            result['detected_songs'].append('Cardigan')
        result['music_genre'] = 'pop'
        
    elif any(word in text_lower for word in ['queen', 'ac/dc']):
        result['detected_artists'].extend(['Queen', 'AC/DC'])
        result['music_genre'] = 'rock'
        result['search_keywords'] = ['80s', 'rock', 'classic']
        
    elif 'jazz' in text_lower:
        result['music_genre'] = 'jazz'
        result['search_keywords'] = ['jazz', 'piano', 'instrumental']
        
    elif any(word in text_lower for word in ['country', 'johnny cash', 'willie nelson']):
        result['detected_artists'].extend(['Johnny Cash', 'Willie Nelson'])
        result['music_genre'] = 'country'
        result['search_keywords'] = ['country', 'classic']
    
    # Extract general keywords
    words = text_lower.split()
    music_keywords = [w for w in words if w in ['music', 'song', 'album', 'artist', 'listening', 'rock', 'pop', 'jazz', 'country']]
    result['search_keywords'].extend(music_keywords)
    
    # Remove duplicates
    result['search_keywords'] = list(set(result['search_keywords']))
    
    return result

if __name__ == "__main__":
    demo_ai_features()