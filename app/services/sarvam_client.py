from pathlib import Path
from typing import Dict, Any, Optional
from app.config import Settings, get_settings

try:
    from sarvamai import SarvamAI
except ImportError:
    print("SarvamAI SDK not found. Please run: pip install sarvamai")
    SarvamAI = None

class SarvamClient:
    """
    A client to interact with the Sarvam AI API for transcription
    using their official Python SDK.
    """
    
    def __init__(self, settings: Settings):
        self.api_key = settings.SARVAM_API_KEY
        
        if not SarvamAI:
             raise ImportError("SarvamAI SDK not installed.")
        
        if not self.api_key or "YOUR_SARVAM_API_KEY" in self.api_key:
            print("WARNING: SARVAM_API_KEY is not set. Sarvam client will not work.")
            self.client = None
        else:
            self.client = SarvamAI(
                api_subscription_key=self.api_key,
            )

    def transcribe_audio_file(
        self, 
        file_path: Path, 
        language_code: str = "en-IN" # Use an appropriate code e.g., "hi-IN", "ta-IN"
    ) -> Dict[str, Any]:
        """
        Submits an audio file for transcription.
        
        The Sarvam SDK's `transcribe` method appears to be synchronous,
        meaning it will wait for the result and handle any polling internally.
        This is perfect for a Celery task.
        """
        
        if not self.client:
             raise Exception("Sarvam transcription failed: SARVAM_API_KEY is not configured.")

        print(f"[SarvamClient] Submitting {file_path.name} for transcription...")

        try:
            with open(file_path, "rb") as audio_file:
                # Call the Sarvam SDK
                response = self.client.speech_to_text.transcribe(
                    file=audio_file,
                    model="saarika:v2.5",       # From their docs
                    language_code=language_code # e.g., 'hi-IN'
                )
            
            # The SDK returns a Pydantic model. Convert it to a dict
            # for standard JSON serialization in our system.
            if response:
                print(f"[SarvamClient] Transcription successful for {file_path.name}.")
                # Assuming the response object has a `.model_dump()` or similar
                if hasattr(response, 'model_dump'):
                    return response.model_dump()
                # Fallback for other object types
                return response.__dict__
            else:
                raise Exception("Sarvam returned an empty response.")

        except Exception as e:
            print(f"Error during Sarvam transcription: {str(e)}")
            raise

# --- Singleton setup for Dependency Injection ---

_sarvam_client: Optional[SarvamClient] = None

def get_sarvam_client() -> SarvamClient:
    """
    Dependency injector for FastAPI to get a singleton SarvamClient.
    """
    global _sarvam_client
    if _sarvam_client is None:
        settings = get_settings()
        _sarvam_client = SarvamClient(settings)
    return _sarvam_client