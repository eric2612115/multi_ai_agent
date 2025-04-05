#!/usr/bin/env python
"""
AI Models Example

This script demonstrates how to use the restructured AI model interfaces
to generate text, embeddings, and other AI capabilities.
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add the src_new directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the necessary modules
from ai.factory import (
    get_text_generation_model,
    get_embedding_model,
    get_web_extraction_model,
    get_available_models
)

from common.config import get_settings


async def test_text_generation():
    """Test text generation with different models."""
    print("\n=== Testing Text Generation ===")
    
    # Get available model types
    available_models = get_available_models()
    print(f"Available models: {', '.join(available_models.keys())}")
    
    # Test each model that supports text generation
    for model_type, capabilities in available_models.items():
        if "text_generation" in capabilities:
            print(f"\nTesting {model_type.upper()} model:")
            try:
                # Get the model
                model = get_text_generation_model(model_type)
                
                # Generate text
                prompt = "Write a short paragraph about artificial intelligence."
                print(f"Prompt: {prompt}")
                response = await model.generate_text(prompt, max_tokens=100)
                print(f"Response:\n{response}")
                
                # Try chat interface
                messages = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "What is the capital of France?"}
                ]
                print("\nChat test:")
                print(f"Messages: {messages}")
                chat_response = await model.chat(messages, max_tokens=50)
                print(f"Response:\n{chat_response}")
                
            except Exception as e:
                print(f"Error testing {model_type}: {str(e)}")
    

async def test_embeddings():
    """Test embedding generation."""
    print("\n=== Testing Embeddings ===")
    
    # Get available model types
    available_models = get_available_models()
    
    # Test each model that supports embeddings
    for model_type, capabilities in available_models.items():
        if "embedding" in capabilities:
            print(f"\nTesting {model_type.upper()} model for embeddings:")
            try:
                # Get the model
                model = get_embedding_model(model_type)
                
                # Generate embedding
                text = "This is a test of the embedding feature."
                print(f"Text: {text}")
                embedding = await model.generate_embedding(text)
                
                # Print only part of the embedding for brevity
                first_five = embedding[:5]
                print(f"Embedding (first 5 of {len(embedding)} dimensions): {first_five}")
                
                # Get embedding dimension
                print(f"Embedding dimensions: {model.embedding_dimensions}")
                
            except Exception as e:
                print(f"Error testing {model_type} embeddings: {str(e)}")


async def test_web_extraction():
    """Test web extraction capabilities."""
    print("\n=== Testing Web Extraction ===")
    
    # Get available model types
    available_models = get_available_models()
    
    # Test each model that supports web extraction
    for model_type, capabilities in available_models.items():
        if "web_extraction" in capabilities:
            print(f"\nTesting {model_type.upper()} model for web extraction:")
            try:
                # Get the model
                model = get_web_extraction_model(model_type)
                
                # Extract content from a URL
                url = "https://en.wikipedia.org/wiki/Artificial_intelligence"
                objective = "Find the definition of artificial intelligence and its main applications."
                print(f"URL: {url}")
                print(f"Objective: {objective}")
                
                content = await model.extract_content(url, objective)
                
                # Print a summary of the extracted content
                if isinstance(content, dict):
                    if "text" in content:
                        print(f"Extracted text (first 200 chars): {content['text'][:200]}...")
                    elif "extracted_data" in content:
                        print(f"Extracted data: {content['extracted_data']}")
                    else:
                        print(f"Extraction keys: {', '.join(content.keys())}")
                else:
                    print(f"Extracted content type: {type(content)}")
                
            except Exception as e:
                print(f"Error testing {model_type} web extraction: {str(e)}")


async def main():
    """Run all tests."""
    print("AI Models Example")
    print("=================")
    
    # Load environment variables
    load_dotenv()
    
    # Show current settings
    settings = get_settings()
    print(f"Default AI service: {settings.ai.default_service}")
    print(f"Embedding dimensions: {settings.ai.embedding_dimensions}")
    
    # Run tests
    await test_text_generation()
    await test_embeddings()
    await test_web_extraction()


if __name__ == "__main__":
    asyncio.run(main())
