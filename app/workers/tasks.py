from pathlib import Path
from app.workers.celery_app import celery_app
from app.api.schemas import TaskStatus, IngestType
from app.services.ingestion_orchestrator import (
    process_audio_source, 
    process_image_source
)

# A helper to update task state (used by the orchestrator via task_self)
def update_task_state(task, status: TaskStatus, details: str, progress: float = 0.0):
    """Helper function to update Celery task state and metadata."""
    meta = {
        'status': status.value,
        'details': details,
        'progress_percent': progress,
    }
    # Using task.update_state is essential for reporting status back to Redis/FastAPI
    task.update_state(state=status.value, meta=meta)

# --- The Main Ingestion Tasks ---

@celery_app.task(bind=True, name="app.workers.tasks.ingest_video")
def ingest_video(self, file_path: str, source_id: str, metadata: dict):
    """
    Celery task to process a video file.
    Routes to the orchestrator for audio extraction, transcription, and indexing.
    """
    task_id = self.request.id
    print(f"[TASK {task_id}] Received video: {file_path}")
    
    try:
        update_task_state(self, TaskStatus.PROCESSING, "Starting video ingestion pipeline...", 5.0)
        
        language_code = metadata.get("language", "ta-IN")
        original_file_path = Path(file_path)
        file_name = original_file_path.name

        # Call the main orchestrator (PASSING self as the task_self argument)
        artifacts = process_audio_source(
            task_self=self, # <--- CRITICAL FIX: Passing the task instance
            source_id=source_id,
            original_file_path=original_file_path,
            file_name=file_name,
            doc_type=IngestType.VIDEO,
            language=language_code
        )
        
        # --- Final Success ---
        meta = {
            'status': TaskStatus.SUCCESS.value,
            'details': "Video processed and indexed successfully (Multimodal).",
            'progress_percent': 100.0,
            'artifacts': artifacts
        }
        self.update_state(state=TaskStatus.SUCCESS.value, meta=meta)
        return meta

    except Exception as e:
        print(f"[TASK {task_id}] FAILED: {e}")
        meta = {
            'status': TaskStatus.FAILURE.value,
            'details': f"Failed to process video: {str(e)}",
            'progress_percent': 0.0,
            'errors': str(e)
        }
        self.update_state(state=TaskStatus.FAILURE.value, meta=meta)
        raise

@celery_app.task(bind=True, name="app.workers.tasks.ingest_audio")
def ingest_audio(self, file_path: str, source_id: str, metadata: dict):
    """
    Celery task to process an audio file.
    Routes to the orchestrator for transcription and indexing.
    """
    task_id = self.request.id
    print(f"[TASK {task_id}] Received audio: {file_path}")
    
    try:
        update_task_state(self, TaskStatus.PROCESSING, "Starting audio ingestion pipeline...", 5.0)
        
        language_code = metadata.get("language", "ta-IN")
        original_file_path = Path(file_path)
        file_name = original_file_path.name

        # Call the main orchestrator (PASSING self as the task_self argument)
        artifacts = process_audio_source(
            task_self=self, # <--- CRITICAL FIX: Passing the task instance
            source_id=source_id,
            original_file_path=original_file_path,
            file_name=file_name,
            doc_type=IngestType.AUDIO,
            language=language_code
        )
        
        # --- Final Success ---
        meta = {
            'status': TaskStatus.SUCCESS.value,
            'details': "Audio processed and indexed successfully.",
            'progress_percent': 100.0,
            'artifacts': artifacts
        }
        self.update_state(state=TaskStatus.SUCCESS.value, meta=meta)
        return meta

    except Exception as e:
        print(f"[TASK {task_id}] FAILED: {e}")
        meta = {
            'status': TaskStatus.FAILURE.value,
            'details': f"Failed to process audio: {str(e)}",
            'errors': str(e)
        }
        self.update_state(state=TaskStatus.FAILURE.value, meta=meta)
        raise

@celery_app.task(bind=True, name="app.workers.tasks.ingest_image")
def ingest_image(self, file_path: str, source_id: str, metadata: dict):
    """
    Celery task to process an image file.
    Routes to the (placeholder) orchestrator for image analysis.
    """
    task_id = self.request.id
    print(f"[TASK {task_id}] Received image: {file_path}")
    
    try:
        update_task_state(self, TaskStatus.PROCESSING, "Starting image pipeline...", 5.0)
        
        original_file_path = Path(file_path)
        file_name = original_file_path.name

        # Call the main image orchestrator (PASSING self as the task_self argument)
        artifacts = process_image_source(
            task_self=self, # <--- CRITICAL FIX: Passing the task instance
            source_id=source_id,
            original_file_path=original_file_path,
            file_name=file_name,
            doc_type=IngestType.IMAGE
        )
        
        # --- Final Success ---
        meta = {
            'status': TaskStatus.SUCCESS.value,
            'details': "Image processed successfully (placeholder).",
            'progress_percent': 100.0,
            'artifacts': artifacts
        }
        self.update_state(state=TaskStatus.SUCCESS.value, meta=meta)
        return meta

    except Exception as e:
        print(f"[TASK {task_id}] FAILED: {e}")
        meta = {
            'status': TaskStatus.FAILURE.value,
            'details': f"Failed to process image: {str(e)}",
            'errors': str(e)
        }
        self.update_state(state=TaskStatus.FAILURE.value, meta=meta)
        raise