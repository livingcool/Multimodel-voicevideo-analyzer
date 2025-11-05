import uuid
from enum import Enum  # <--- THIS WAS THE MISSING LINE
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal

# --- Enums for controlled vocabularies ---

class IngestType(str, Enum):
    """Enumeration for the types of content that can be ingested."""
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    TEXT = "text" # Added for completeness, e.g., .txt or .md files

class TaskStatus(str, Enum):
    """Enumeration for the status of a background task."""
    PENDING = "pending"
    RECEIVED = "received"
    STARTED = "started"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILURE = "failure"

# --- Schemas for /ingest ---

class IngestResponse(BaseModel):
    """
    Response model after submitting a file for ingestion.
    Returns a task ID to poll for status.
    """
    task_id: str = Field(..., description="The unique ID for the background ingestion task.")
    status_url: str = Field(..., description="The URL to poll for task status.")
    message: str = "File received and queued for processing."

# --- Schemas for /task/{task_id} ---

class ArtifactModel(BaseModel):
    """Represents a processed artifact, e.g., a transcript or extracted frame."""
    type: str = Field(..., description="Type of artifact (e.g., 'transcript', 'frame')")
    path: str = Field(..., description="Storage path of the artifact")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Any associated metadata")

class TaskStatusResponse(BaseModel):
    """
    Response model for checking the status of an ingestion task.
    """
    task_id: str
    status: TaskStatus
    progress_percent: float = Field(default=0.0, description="Estimated progress (0.0 to 100.0)")
    details: Optional[str] = Field(None, description="Current processing step or error message")
    artifacts: List[ArtifactModel] = Field(default_factory=list, description="List of generated artifacts upon completion")
    errors: Optional[str] = Field(None, description="Detailed error message if status is 'failure'")

# --- Schemas for /query ---

class QueryFilter(BaseModel):
    """
    Optional filters to narrow down the search context.
    """
    source_id: Optional[str] = Field(None, description="Filter by the original 'source_id' provided during ingest")
    doc_type: Optional[IngestType] = Field(None, description="Filter by media type (video, audio, etc.)")
    date_from: Optional[str] = Field(None, description="ISO 8601 date string (e.g., '2025-10-30')")
    date_to: Optional[str] = Field(None, description="ISO 8601 date string")
    
class QueryRequest(BaseModel):
    """
    Request model for POST /query.
    """
    query: str = Field(..., min_length=3, description="The natural language query.")
    filters: Optional[QueryFilter] = Field(default_factory=QueryFilter, description="Filters to apply to the retrieval")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of relevant chunks to retrieve")

class SourceChunk(BaseModel):
    """
References a single piece of retrieved context used to generate the answer.
    """
    source_file: str = Field(..., description="The original file name or source identifier")
    chunk_text: str = Field(..., description="The actual text chunk (transcript, OCR, etc.)")
    start_time: Optional[float] = Field(None, description="Start time in seconds (for video/audio)")
    end_time: Optional[float] = Field(None, description="End time in seconds (for video/audio)")
    score: float = Field(..., description="Relevance score from the retriever (e.g., cosine similarity)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Other metadata (e.g., page number, frame number)")
    
class QueryResponse(BaseModel):
    """
    Response model for POST /query.
    Returns the synthesized answer and the sources used.
    """
    answer: str = Field(..., description="The final answer synthesized by the LLM")
    sources: List[SourceChunk] = Field(..., description="The list of source chunks used to generate the answer")
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="A unique ID for this query interaction")