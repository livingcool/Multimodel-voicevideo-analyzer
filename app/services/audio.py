import ffmpeg
import os
from pathlib import Path
from typing import List
from app.config import Settings, get_settings
import ffmpeg # <--- ADD THIS LINE HERE
# --- Constants ---
# Most ASR (Automatic Speech Recognition) models, including Sarvam's,
# are trained on 16kHz, single-channel (mono) audio.
REQUIRED_SAMPLE_RATE = 16000
REQUIRED_AUDIO_CHANNELS = 1
OUTPUT_FORMAT = "mp3" # Using mp3 for good compression

class AudioProcessingError(Exception):
    """Custom exception for audio processing failures."""
    pass

def prepare_audio_for_transcription(
    input_path: Path, 
    output_dir: Path,
    source_id: str
) -> Path:
    """
    Extracts audio from any media file, converts it to mono,
    resamples it to 16kHz, and saves it as an MP3.
    
    This function is synchronous and should be run inside a Celery task.
    
    Args:
        input_path: Path to the original media file (e.g., .mp4, .wav).
        output_dir: The directory to save the processed audio (e.g., data/transcripts).
        source_id: The unique ID for this file.
        
    Returns:
        The Path to the newly created audio file.
        
    Raises:
        AudioProcessingError: If ffmpeg fails.
    """
    output_filename = f"{source_id}_prepared.{OUTPUT_FORMAT}"
    output_path = output_dir / output_filename
    
    print(f"[AudioService] Preparing audio for {source_id}...")
    print(f"[AudioService]   Input: {input_path}")
    print(f"[AudioService]   Output: {output_path}")

    try:
        # Ensure the output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build the ffmpeg command using ffmpeg-python
        stream = ffmpeg.input(str(input_path))
        
        # Select only the audio stream ('a')
        # -ac: Set audio channels to 1 (mono)
        # -ar: Set audio rate (sample rate) to 16kHz
        # -f: Set output format to mp3
        stream = ffmpeg.output(
            stream.audio, 
            str(output_path), 
            ac=REQUIRED_AUDIO_CHANNELS,
            ar=REQUIRED_SAMPLE_RATE,
            f=OUTPUT_FORMAT
        )
        
        # Execute the command, overwriting any existing file
        # 'capture_stdout=True' and 'capture_stderr=True' are crucial
        # to get error details if it fails.
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        print(f"[AudioService] Successfully prepared audio: {output_path}")
        return output_path

    except ffmpeg.Error as e:
        # If ffmpeg fails, log the detailed error message
        error_message = e.stderr.decode() if e.stderr else "Unknown ffmpeg error"
        print(f"FATAL: ffmpeg processing failed for {input_path}.")
        print(f"ffmpeg error: {error_message}")
        raise AudioProcessingError(f"ffmpeg error: {error_message}")
    except Exception as e:
        print(f"An unexpected error occurred during audio prep: {e}")
        raise AudioProcessingError(str(e))
    
    
# app/services/audio.py (Add this function)

# app/services/audio.py (Update the split_audio_file function)

# app/services/audio.py
# app/services/audio.py (Final split_audio_file function)

def split_audio_file(input_path: Path, output_dir: Path, segment_duration_sec: int = 29) -> List[Path]:
    """
    Splits an audio file into smaller segments of 29 seconds maximum 
    to strictly conform to the 30-second API limit.
    """
    segment_output_dir = output_dir / "segments"
    segment_output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[AudioService] Splitting audio into {segment_duration_sec}s segments (FINAL FIX)...")
    
    try:
        output_pattern = str(segment_output_dir / f"{input_path.stem}_%03d.{input_path.suffix.lstrip('.')}")
        
        stream = ffmpeg.input(str(input_path))
        
        # Use strict flags to ensure compliance:
        # -map 0:a: Ensure we ONLY process the audio stream
        # -c:a libmp3lame: Force high-quality MP3 re-encode for compliance
        stream = ffmpeg.output(
            stream, 
            output_pattern,
            f='segment',
            segment_time=segment_duration_sec,
            map='0:a', 
            c='libmp3lame', # FIX: Use 'c' instead of 'c:a'
            ac=1, 
            ar=16000 
        )
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        return sorted(list(segment_output_dir.glob(f"{input_path.stem}_*.*")))
        
    except ffmpeg.Error as e:
        error_message = e.stderr.decode() if e.stderr else "Unknown ffmpeg error during splitting"
        print(f"FATAL: ffmpeg splitting failed: {error_message}")
        raise AudioProcessingError(f"ffmpeg splitting error: {error_message}")