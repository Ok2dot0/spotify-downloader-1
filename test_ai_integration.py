#!/usr/bin/env python3
"""
Simple test to verify AI integration works correctly.
"""

import os
import sys
from pathlib import Path

def test_ai_integration():
    """Test AI integration without full app initialization."""
    
    print("🧪 Testing AI Music Assistant Integration")
    print("=" * 50)
    
    # Test 1: AI Assistant Module Import
    print("\n1. Testing AI Assistant Import...")
    try:
        from ai_music_assistant import AIMusicAssistant
        print("✅ AI Music Assistant imported successfully")
    except Exception as e:
        print(f"❌ AI import failed: {e}")
        return False
    
    # Test 2: Basic AI Assistant Initialization
    print("\n2. Testing AI Assistant Initialization...")
    try:
        assistant = AIMusicAssistant()
        print("✅ AI Assistant initialized")
        
        # Check availability
        is_available = assistant.is_available()
        print(f"   Available: {is_available}")
        
        status = assistant.get_availability_status()
        print("   Status:")
        for key, value in status.items():
            print(f"     {key}: {value}")
            
    except Exception as e:
        print(f"❌ AI initialization failed: {e}")
        return False
    
    # Test 3: Supported File Types
    print("\n3. Testing Supported File Types...")
    try:
        supported = assistant.supported_file_types()
        print(f"✅ Supported types: {supported}")
    except Exception as e:
        print(f"❌ File types check failed: {e}")
        return False
    
    # Test 4: Configuration Handling
    print("\n4. Testing Configuration...")
    try:
        config = {
            'ai_provider': 'ollama',
            'ai_model': 'llama3.2-vision:latest',
            'ai_enable_vision': True
        }
        assistant_with_config = AIMusicAssistant(config)
        print("✅ Configuration handling works")
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False
    
    # Test 5: Mock Analysis (without actual AI providers)
    print("\n5. Testing Mock Analysis...")
    try:
        # This should fail gracefully since no providers are installed
        result = assistant.analyze_text("test music text")
        print(f"✅ Text analysis handling: {result is None}")
        
        # Test with non-existent image
        result = assistant.analyze_image("nonexistent.jpg")
        print(f"✅ Image analysis handling: {result is None}")
        
    except Exception as e:
        print(f"❌ Mock analysis failed: {e}")
        return False
    
    # Test 6: Query Generation
    print("\n6. Testing Query Generation...")
    try:
        # Test with mock analysis result
        mock_result = {
            'detected_artists': ['Test Artist'],
            'detected_albums': ['Test Album'],
            'detected_songs': ['Test Song'],
            'music_genre': 'rock',
            'search_keywords': ['music', 'test'],
            'confidence': 0.8
        }
        
        queries = assistant.generate_search_queries(mock_result)
        print(f"✅ Generated {len(queries)} queries: {queries}")
        
    except Exception as e:
        print(f"❌ Query generation failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All AI integration tests passed!")
    return True

if __name__ == "__main__":
    success = test_ai_integration()
    sys.exit(0 if success else 1)