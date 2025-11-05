import uuid
import json
from pathlib import Path
from fastapi import (
    APIRouter, 
    Depends, 
    UploadFile, 
    File, 
    Form, 
    HTTPException, 
    status,
    Request
)
from app.config import Settings, get_settings
from app.api.schemas import IngestResponse, IngestType
from app.workers.celery_app import celery_app
from app.workers.tasks import ingest_video, ingest_audio, ingest_image

router = APIRouter()

# --- Helper to select the correct task ---

TASK_MAP = {
    IngestType.VIDEO: ingest_video,
    IngestType.AUDIO: ingest_audio,
    IngestType.IMAGE: ingest_image,
    # IngestType.TEXT: ingest_text (if you add it)
}

@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_ingest_task(
    request: Request,
    type: IngestType = Form(..., description="The type of media being uploaded"),
    file: UploadFile = File(..., description="The media file to process"),
    source_id: str = Form(None, description="Optional unique ID for the source (e.g., a meeting ID)"),
    metadata: str = Form("{}", description="JSON string of arbitrary metadata"),
    settings: Settings = Depends(get_settings)
):
    """
    Accepts a media file and queues it for asynchronous processing.
    """
    
    # 1. Generate a unique ID if not provided
    if not source_id:
        source_id = str(uuid.uuid4())
    
    # 2. Ensure upload directory exists
    upload_dir = settings.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. Create a safe file path
    # We use the source_id to guarantee a unique, conflict-free name
    file_extension = Path(file.filename).suffix
    saved_file_path = upload_dir / f"{source_id}{file_extension}"
    
    # 4. Save the uploaded file
    try:
        with open(saved_file_path, "wb") as buffer:
            buffer.write(await file.read())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}"
        )
        
    # 5. Parse metadata
    try:
        metadata_dict = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metadata must be a valid JSON string."
        )

    # 6. Select and dispatch the correct Celery task
    task_function = TASK_MAP.get(type)
    if not task_function:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ingestion type '{type.value}' is not supported."
        )

    # Dispatch the task
    task = task_function.delay(
        file_path=str(saved_file_path),
        source_id=source_id,
        metadata=metadata_dict
    )

    # 7. Return the task ID and a URL to poll for status
    status_url = request.url_for("get_task_status", task_id=task.id)
    
    return IngestResponse(
        task_id=task.id,
        status_url=str(status_url)
    )