#!/usr/bin/env python3
"""Test script for new Google GenAI SDK"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_google_genai():
    """Test the new google-genai SDK"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in .env file")
        return
    
    try:
        from google import genai
        print("✅ Successfully imported new google-genai SDK")
        
        # Create client
        client = genai.Client(api_key=api_key)
        print("✅ Successfully created Gemini client")
        
        # Test model listing (optional)
        try:
            models = client.models.list()
            print(f"✅ Available models: {[m.name for m in models][:3]}...")
        except:
            print("ℹ️  Model listing not available or requires different permissions")
        
        # Test generation
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-001")
        print(f"🔧 Using model: {model_name}")
        
        response = client.models.generate_content(
            model=model_name,
            contents="Say 'Hello from the new Google GenAI SDK!' in exactly 5 words.",
            config={"temperature": 0.7}
        )
        
        print(f"✅ Response: {response.text}")
        print("\n🎉 New Google GenAI SDK is working correctly!")
        
    except ImportError as e:
        print(f"❌ Failed to import google-genai: {e}")
        print("Please run: pip install google-genai")
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        print(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    test_google_genai()