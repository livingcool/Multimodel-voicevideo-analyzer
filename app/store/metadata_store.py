from sqlalchemy import create_engine, Column, Integer, String, Float, Text, ForeignKey, Enum as SqlEnum, DateTime
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
import uuid  # <-- ADD THIS LINE
from sqlalchemy.orm import joinedload
from app.config import settings 
from app.api.schemas import IngestType # Use the same enum from your API

# --- SQLAlchemy Setup ---

# Use connect_args for SQLite only, as it's needed for Celery compatibility
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_recycle=3600 # Recycle connections every hour
)

# SessionLocal is the factory for new database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our declarative models
Base = declarative_base()

# --- Database Models (Tables) ---

class Document(Base):
    """
    Represents a single ingested file (video, audio, etc.).
    A Document has many TextChunks.
    """
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    source_file_name = Column(String, index=True)
    source_id = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    doc_type = Column(SqlEnum(IngestType), nullable=False)
    storage_path = Column(String) # Path to the *original* file
    status = Column(String, default="processing") # e.g., 'processing', 'completed', 'failed'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship: A Document can have many chunks
    chunks = relationship("TextChunk", back_populates="document", cascade="all, delete-orphan")

class TextChunk(Base):
    """
    Represents a single chunk of text from a document.
    This is the core link between the vector store and the text content.
    """
    __tablename__ = "text_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    vector_id = Column(Integer, unique=True, index=True) # The ID from FAISS
    
    text_content = Column(Text, nullable=False)
    start_time = Column(Float, nullable=True) # For video/audio
    end_time = Column(Float, nullable=True)   # For video/audio
    page_number = Column(Integer, nullable=True) # For PDFs
    
    # Relationship: A TextChunk belongs to one Document
    document = relationship("Document", back_populates="chunks")


# --- Pydantic Models for Data Validation ---
# These ensure data is clean before it goes to the DB

class TextChunkCreate(BaseModel):
    """Pydantic model for creating a new TextChunk."""
    vector_id: int
    text_content: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    page_number: Optional[int] = None
    
    class Config:
        orm_mode = True # Renamed to from_attributes in Pydantic v2

# --- Database Initialization & Session Management ---

def create_db_and_tables():
    """
    Initializes the database and creates tables.
    Called on application startup.
    """
    try:
        print("[MetadataStore] Initializing database and tables...")
        Base.metadata.create_all(bind=engine)
        print("[MetadataStore] Database tables created successfully.")
    except Exception as e:
        print(f"[MetadataStore] FATAL: Error creating database tables: {e}")
        raise

@contextmanager
def get_db() -> Session:
    """
    Provides a database session for a single request or operation.
    Ensures the session is always closed, and transactions are
    rolled back on error.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        
# --- CRUD Functions ---

def get_chunk_by_vector_id(db: Session, vector_id: int) -> Optional[TextChunk]:
    """Retrieves a single text chunk by its FAISS vector ID."""
    return (
        db.query(TextChunk)
        .filter(TextChunk.vector_id == vector_id)
        .options(joinedload(TextChunk.document)) # Eagerly load the document
        .first()
    )

def get_chunks_by_vector_ids(db: Session, vector_ids: List[int]) -> List[TextChunk]:
    """Retrieves multiple text chunks by their FAISS vector IDs, loading the parent document eagerly."""
    if not vector_ids:
        return []
    
    return (
        db.query(TextChunk)
        .filter(TextChunk.vector_id.in_(vector_ids))
        .options(joinedload(TextChunk.document)) # <--- THIS IS THE CRITICAL FIX
        .all()
    )