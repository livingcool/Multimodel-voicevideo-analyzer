from fastapi import FastAPI, Depends, Request
from app.config import Settings, get_settings
from app.api import routes_ingest, routes_task, routes_query
from app.store.metadata_store import create_db_and_tables  # <-- 1. ADD THIS IMPORT

# Create the FastAPI app instance
app = FastAPI(
    title="Multimodal RAG Ingestion & Query Engine",
    description="API for ingesting video, audio, and images for RAG.",
    version="0.1.0"
)

# --- Create Database Tables on Startup ---
@app.on_event("startup")
def on_startup():
    """
    Event handler that runs when the application starts.
    This creates all necessary database tables.
    """
    create_db_and_tables()
# --- 2. ADD THIS ENTIRE BLOCK ---


# --- Include API Routers ---
# These imports bring in the endpoints you defined in other files.
app.include_router(
    routes_ingest.router,
    prefix="/api/v1",
    tags=["1. Ingestion"]
)
app.include_router(
    routes_task.router,
    prefix="/api/v1",
    tags=["2. Task Status"]
)
app.include_router(
    routes_query.router,
    prefix="/api/v1",
    tags=["3. Query"]
)

# --- Root Endpoint / Health Check ---
@app.get("/", tags=["Health Check"])
async def read_root(settings: Settings = Depends(get_settings)):
    """
    Root endpoint for health check.
    Returns the application name and current settings (excluding secrets).
    """
    return {
        "app_name": "Multimodal RAG Engine",
        "log_level": settings.LOG_LEVEL,
        "storage_backend": settings.STORAGE_BACKEND,
        "llm_provider": settings.LLM_PROVIDER,
        "embedding_model": settings.EMBEDDING_MODEL
    }