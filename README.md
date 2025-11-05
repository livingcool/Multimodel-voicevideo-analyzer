Multimodal RAG Ingestion & Query Engine
This project is a production-grade, asynchronous API for ingesting "dark data" (videos, audio, images) and making it searchable via a RAG pipeline.

🚀 The Problem & The Vision
Your current RAG pipeline only understands text. Corporate knowledge, however, also exists in videos (product demos, all-hands meetings), audio (podcast interviews, call center recordings), and images (diagrams, whiteboards).

This project unlocks that 90% of "dark data." It provides a system to ask questions like, "What was the new feature demoed in the Q2 all-hands video?" and get a direct, text-based answer.

🏗️ Core Architecture
This system is built on a decoupled, asynchronous, production-ready architecture.

Lightweight API (FastAPI): A non-blocking API server that handles file uploads and queries. It returns a task_id in milliseconds.

Heavy Compute Workers (Celery): A set of background workers that handle the slow, resource-intensive tasks like audio transcription (Sarvam) and video analysis.

Task Broker (Redis): Manages the queue of jobs, ensuring no task is lost.

Smart Routing: Tasks are routed to specific queues. ingest_video goes to a gpu_tasks queue, while ingest_audio goes to a cpu_tasks queue.

📊 Current Project Status (As of 2025-11-05)
Estimated Completion: ~55%

The core ingestion "plumbing" is complete and validated. We can successfully process multimedia files into text.

✅ What's Working
FastAPI Server: All endpoints (/ingest, /task/{id}, /query) are running.

Async Pipeline: A file upload correctly creates a job in Redis (Celery).

Task Routing: video tasks are correctly routed to the gpu_tasks queue.

Video-to-Text Pipeline (Live):

Receives a video file.

Uses ffmpeg to extract the audio track.

Sends the audio to the Sarvam AI API for transcription.

Saves the resulting transcript as a JSON file.

Task Status: The GET /task/{id} endpoint correctly reports the final "success" status and artifacts.

❌ What's Not Done (Next Steps)
Embedding: The new transcripts are not yet chunked, embedded, or saved to a vector store.

Visual Analysis: The video-frame analysis part of the ingest_video task is still a placeholder.

Query Engine: The POST /query endpoint is still a placeholder. It does not perform any retrieval or LLM (Gemini) generation.

🛠️ Setup & Run Instructions
1. Prerequisites
Python 3.10+

Redis: Must be installed and running.

FFmpeg: Must be installed and added to your system's PATH.

2. Installation
Clone the repository.

Create and activate a virtual environment:

Bash

python -m venv .venv
.\.venv\Scripts\Activate
Install all requirements:

Bash

pip install -r requirements.txt
Create your .env file from the example:

Bash

copy .env.example .env
Edit .env and add your SARVAM_API_KEY and GOOGLE_API_KEY.

Create the local data directory:

Bash

mkdir data
3. Running the System
You must run 3 or 4 separate terminals.

Terminal 1: FastAPI Server

Bash

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
Terminal 2: CPU Worker (For audio-only files)

Bash

celery -A app.workers.celery_app worker --loglevel=info -Q cpu_tasks -P eventlet
Terminal 3: GPU Worker (For video/image files)

Bash

celery -A app.workers.celery_app worker --loglevel=info -Q gpu_tasks -P eventlet
Terminal 4: Test with cURL (Run from a folder containing a test video)

PowerShell

curl.exe -X 'POST' 'http://localhost:8000/api/v1/ingest' -H 'accept: application/json' -F 'type=video' -F 'file=@"YOUR_VIDEO_FILE.mp4"' -F 'source_id=test_run' -F 'metadata={\"language\": \"ta-IN\"}'
🐞 Development & Triage Log
This section documents the errors encountered and rectified during the initial setup of the scaffold.

Environment & Dependency Errors
Error: pip's dependency resolver ... conflicts. (e.g., langchain-core versions).

Root Cause: The global Python environment was "polluted" with packages from other projects.

Fix: Stopped all work in the global environment. Created a clean project folder (multimodal-poc-clean) and a new virtual environment (.venv). All packages were installed cleanly inside it.

Error: ModuleNotFoundError: No module named 'app'.

Root Cause: Running uvicorn from a terminal where the virtual environment (.venv) was not activated. The system's global Python had no knowledge of the app module's location.

Fix: Activating the venv (.\.venv\Scripts\Activate) before running uvicorn or celery. This is mandatory for every new terminal session.

Windows-Specific Errors
Error: 'touch' is not recognized as the name of a cmdlet...

Root Cause: Using a Linux/bash command (touch) in Windows PowerShell.

Fix: Used the PowerShell equivalent: New-Item -Path "README.md" -ItemType File.

Error: PermissionError: [WinError 5] Access is denied in the Celery worker.

Root Cause: Celery's default worker pool (prefork) is incompatible with the Windows process model.

Fix: Installed eventlet (pip install eventlet) and forced Celery to use this Windows-compatible pool with the -P eventlet flag.

Command: celery -A ... worker -P eventlet

Error: FileNotFoundError: [WinError 2] The system cannot find the file specified when running the ingest_video task.

Root Cause: The ffmpeg-python library is a wrapper and requires the actual ffmpeg.exe program, which was not installed or not in the system's PATH.

Fix:

Downloaded the ffmpeg build (e.g., from gyan.dev).

Extracted the archive.

Added the full path to the bin folder (e.g., C:\ffmpeg-build\bin) to the System PATH environment variables.

Crucially: Restarted all terminals (Uvicorn, Celery) to ensure they loaded the new PATH.

cURL (PowerShell) Errors
Error: Unexpected token '\' in expression or statement.

Root Cause: Pasting a bash multi-line command (using \) into PowerShell.

Fix: Used the PowerShell multi-line character (the backtick `) or (preferably) converted the command to a single line.

Error: Invoke-WebRequest : Cannot bind parameter 'Headers'...

Root Cause: In PowerShell, curl is an alias for Invoke-WebRequest, which has different syntax and doesn't use -H or -F.

Fix: Used curl.exe to explicitly call the real curl program and bypass the PowerShell alias.

Error: curl: (26) Failed to open/read local data...

Root Cause: Running the curl.exe command from a directory that did not contain the sample video file.

Fix: Used cd to navigate to the correct folder (e.g., C:\Users\ganes\Downloads) before running the command.

Error: {"detail":"Metadata must be a valid JSON string."}

Root Cause: PowerShell was interpreting the double quotes in the JSON string (-F 'metadata={"language": "ta-IN"}') before passing them to curl.exe.

Fix: "Escaped" the internal quotes with backslashes: -F 'metadata={\"language\": \"ta-IN\"}'.

Application & API Errors
Error: NameError: name 'Enum' is not defined (in schemas.py).

Fix: Added from enum import Enum.

Error: NameError: name 'Optional' is not defined (in schemas.py and config.py).

Fix: Added from typing import Optional.

Error: ValidationError: S3_ENDPOINT_URL Input should be a valid URL...

Root Cause: S3_ENDPOINT_URL was defined in .env as an empty string (S3_ENDPOINT_URL=), which Pydantic's AnyHttpUrl type correctly rejected.

Fix: Commented out or deleted the unused S3 environment variables (#S3_ENDPOINT_URL=) from the .env file.

Error: Browser error ERR_CONNECTION_TIMED_OUT when navigating to http://0.0.0.0:8000.

Root Cause: 0.0.0.0 is a "listen" address for a server, not a "connect" address for a browser.

Fix: Used http://127.0.0.1:8000 or http://localhost:8000 in the browser.

Error: 500 Internal Server Error on file upload.

Root Cause: The API (routes_ingest.py) tried to call task.delay() but the Celery worker was not running, or Redis was not running. The connection to the message broker failed.

Fix: Ensured the Redis server was running first, then started the Celery worker second.

Error: API returned 202Accepted (with a task_id), but the Celery worker terminal was silent.

Root Cause: A task-queue mismatch. The video task was correctly routed to the gpu_tasks queue, but the running worker was only listening to cpu_tasks.

Fix: Started a second worker dedicated to the correct queue: celery -A ... worker -Q gpu_tasks -P eventlet.