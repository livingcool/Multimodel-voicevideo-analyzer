import cv2
from pathlib import Path
from app.config import get_settings

class VideoProcessingError(Exception):
    """Custom exception for video processing failures."""
    pass

def extract_key_frames(input_path: Path, output_dir: Path) -> Path:
    """
    Extracts frames from a video at a fixed interval and saves them as JPEGs.
    
    Args:
        input_path: Path to the original video file (.mp4).
        output_dir: The directory to save the extracted frames.
        
    Returns:
        The path to the output directory containing the frames.
    """
    settings = get_settings()
    interval = settings.VIDEO_FRAME_INTERVAL_SEC
    
    print(f"[VideoService] Extracting frames from {input_path.name} every {interval} seconds...")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise VideoProcessingError(f"Could not open video file: {input_path}")
        
    # Get the frame rate and total number of frames
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        raise VideoProcessingError("Could not determine video frame rate (FPS).")

    # Calculate the number of frames to skip per interval
    frame_skip = int(fps * interval)
    frame_count = 0
    frames_extracted = 0

    while True:
        # Set the current frame position
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count)
        
        ret, frame = cap.read()
        
        if not ret:
            # End of video stream
            break
            
        # Get timestamp in seconds for the saved frame
        current_time_sec = frame_count / fps
        
        # Construct output file name
        frame_filename = f"frame_{frames_extracted:04d}_{int(current_time_sec)}s.jpg"
        frame_output_path = output_dir / frame_filename
        
        # Save the frame
        cv2.imwrite(str(frame_output_path), frame)
        
        frames_extracted += 1
        frame_count += frame_skip
        
    cap.release()
    
    print(f"[VideoService] Extracted {frames_extracted} keyframes to {output_dir}")
    return output_dir