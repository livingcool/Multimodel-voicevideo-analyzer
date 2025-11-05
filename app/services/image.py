import os
from pathlib import Path
from typing import Dict, List
from google import genai
from google.genai import types
from PIL import Image

from app.config import get_settings, LLMProvider # <--- THE FIX

class ImageProcessingError(Exception):
    """Custom exception for image processing failures."""
    pass

def analyze_frames_with_gemini(frames_dir: Path) -> Dict[str, str]:
    """
    Analyzes all images in a directory using Gemini Vision to generate captions/descriptions.
    
    Args:
        frames_dir: The directory containing the extracted JPEG frames.
        
    Returns:
        A dictionary mapping frame filename (e.g., 'frame_0001_30s.jpg') to its description.
    """
    settings = get_settings()
    
    if settings.LLM_PROVIDER != LLMProvider.GEMINI: # <--- THE CORRECT USAGE
        raise ImageProcessingError("Gemini Vision requires LLM_PROVIDER to be 'gemini'.")
        
    print(f"[ImageService] Analyzing frames in {frames_dir} using Gemini Vision...")
    
    try:
        # Initialize the client (reusing existing API key setup)
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        
        descriptions: Dict[str, str] = {}
        frame_files = sorted(list(frames_dir.glob("*.jpg")))
        
        for frame_path in frame_files:
            print(f"[ImageService] Analyzing {frame_path.name}...")
            
            # Open the image using PIL
            img = Image.open(frame_path)
            
            # The prompt to guide the vision model
            prompt = (
                "Provide a detailed, objective description of this video frame, "
                "noting any text, diagrams, key people, or slide content. "
                "Keep the description concise and factual."
            )
            
            # Call the multimodal Gemini model
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, img]
            )
            
            descriptions[frame_path.name] = response.text.strip()
            
        print(f"[ImageService] Successfully generated {len(descriptions)} frame descriptions.")
        return descriptions

    except Exception as e:
        print(f"[ImageService] FATAL: Gemini Vision analysis failed: {e}")
        raise ImageProcessingError(f"Gemini Vision failed: {e}")