import json
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import uuid

from app.api.schemas import IngestType, TaskStatus
from app.config import get_settings
from app.store.metadata_store import get_db, Document, TextChunk
from app.services.audio import prepare_audio_for_transcription, split_audio_file
from app.services.sarvam_client import get_sarvam_client
from app.services.text_chunker import get_text_chunker
from app.services.embedder import get_embedding_service
from app.store.vector_store import get_vector_store
from app.services.video import extract_key_frames
from app.services.image import analyze_frames_with_gemini

# A helper to update task state (used by the orchestrator via task_self)
def update_task_state(task, status: TaskStatus, details: str, progress: float = 0.0):
    """Helper function to update Celery task state and metadata."""
    meta = {
        'status': status.value,
        'details': details,
        'progress_percent': progress,
    }
    task.update_state(state=status.value, meta=meta)

def process_audio_source(
    task_self, # The Celery task instance passed here
    source_id: str,
    original_file_path: Path,
    file_name: str,
    doc_type: IngestType,
    language: str
) -> Dict[str, Any]:
    """
    The main processing pipeline for any file with an audio track (AUDIO or VIDEO).
    Handles segmentation, transcription, chunking, and embedding.
    """
    
    # Get all singleton services
    settings = get_settings()
    sarvam_client = get_sarvam_client()
    text_chunker = get_text_chunker()
    embed_service = get_embedding_service()
    vector_store = get_vector_store()
    
    artifacts: Dict[str, Any] = {}
    
    with get_db() as db:
        
        # --- 1. Create Document Record ---
        print(f"[Orchestrator] Creating document record for {source_id}")
        doc = Document(
            source_id=source_id,
            source_file_name=file_name,
            doc_type=doc_type,
            storage_path=str(original_file_path),
            status="processing"
        )
        db.add(doc)
        # Commit the document immediately to save the source_id and prevent integrity errors on failure
        db.commit() 
        db.refresh(doc)
        
        try:
            # --- 2. Prepare Audio (FFmpeg) ---
            update_task_state(task_self, TaskStatus.PROCESSING, "Extracting/Standardizing audio...", 10.0)
            prepared_audio_path = prepare_audio_for_transcription(
                input_path=original_file_path,
                output_dir=settings.TRANSCRIPT_DIR,
                source_id=source_id
            )
            
            # --- 3. Segment Audio (FIX for 30s limit) ---
            update_task_state(task_self, TaskStatus.PROCESSING, "Splitting audio for API limits...", 20.0)
            # Use 29 seconds to strictly adhere to the API's 30s limit
            segment_paths = split_audio_file(
                prepared_audio_path,
                settings.TRANSCRIPT_DIR,
                segment_duration_sec=29 
            )
            if not segment_paths:
                raise Exception("Audio file was split, but no segments were created.")

            # --- 4. Transcribe Segments (Sarvam) & Combine (Full Loop) ---
            update_task_state(task_self, TaskStatus.PROCESSING, f"Transcribing {len(segment_paths)} segments (Sarvam)...", 40.0)
            
            full_transcript_text = ""
            combined_segments = []
            
            for i, segment_path in enumerate(segment_paths):
                # Update progress for user feedback
                progress = 40.0 + (i / len(segment_paths)) * 10.0
                update_task_state(task_self, TaskStatus.PROCESSING, f"Transcribing segment {i+1}/{len(segment_paths)}...", progress)
                
                segment_transcript_data = sarvam_client.transcribe_audio_file(
                    file_path=segment_path,
                    language_code=language
                )
                
                # Combine results
                segment_text = segment_transcript_data.get('transcript', '')
                if segment_text:
                    full_transcript_text += segment_text + " "
                    combined_segments.extend(segment_transcript_data.get('segments', [{'text': segment_text, 'start': 0.0, 'end': 0.0}]))
            
            transcript_data = {"transcript": full_transcript_text.strip(), "segments": combined_segments}
            
            # Save the raw combined transcript
            transcript_path = settings.TRANSCRIPT_DIR / f"{source_id}_transcript.json"
            with open(transcript_path, 'w', encoding='utf-8') as f:
                json.dump(transcript_data, f, ensure_ascii=False, indent=2)
            
            artifacts['transcript_path'] = str(transcript_path)
            
            # --- 5. Chunk Transcript & Embed Text ---
            update_task_state(task_self, TaskStatus.PROCESSING, "Chunking and embedding transcript...", 55.0)
            chunks_with_times = text_chunker.chunk_transcript(transcript_data)
            
            if not chunks_with_times:
                raise Exception("Transcript was empty or could not be chunked.")
                
            text_chunks = [chunk[0] for chunk in chunks_with_times]
            vectors = embed_service.embed_texts(text_chunks)
            vector_ids = vector_store.add_vectors(vectors)
            
            # Link Text Chunks to Metadata DB (SQL)
            new_chunk_records = []
            for i, chunk_data in enumerate(chunks_with_times):
                text, start, end = chunk_data
                vector_id = int(vector_ids[i])
                
                db_chunk = TextChunk(
                    document_id=doc.id,
                    vector_id=vector_id,
                    text_content=text,
                    start_time=start,
                    end_time=end
                )
                new_chunk_records.append(db_chunk)
            
            db.add_all(new_chunk_records)
            
            # --- 6. Video Frame Analysis (Multimodal Step) ---
            if doc_type == IngestType.VIDEO:
                update_task_state(task_self, TaskStatus.PROCESSING, "Extracting video frames...", 70.0)
                
                # 6a. Extract Frames
                frames_output_dir = settings.FRAME_DIR / source_id
                frames_output_dir.mkdir(parents=True, exist_ok=True)
                
                extract_key_frames(original_file_path, frames_output_dir)
                artifacts['frames_dir'] = str(frames_output_dir)
                
                # 6b. Analyze Frames (Gemini Vision)
                update_task_state(task_self, TaskStatus.PROCESSING, "Analyzing frames with Gemini Vision...", 80.0)
                frame_descriptions = analyze_frames_with_gemini(frames_output_dir)
                
                # 6c. Embed Frame Descriptions and Link
                frame_texts = list(frame_descriptions.values())
                
                if frame_texts:
                    frame_vectors = embed_service.embed_texts(frame_texts)
                    frame_vector_ids = vector_store.add_vectors(frame_vectors)
                    
                    new_frame_chunk_records = []
                    frame_filenames = list(frame_descriptions.keys())

                    for i, text in enumerate(frame_texts):
                        frame_filename = frame_filenames[i]
                        # Time extraction
                        try:
                            time_sec = float(frame_filename.split('_')[-1].replace('s.jpg', ''))
                        except ValueError:
                            time_sec = 0.0

                        db_chunk = TextChunk(
                            document_id=doc.id,
                            vector_id=int(frame_vector_ids[i]),
                            text_content=text,
                            start_time=time_sec,
                            end_time=time_sec
                        )
                        new_frame_chunk_records.append(db_chunk)
                        
                    db.add_all(new_frame_chunk_records)
                    artifacts['visual_count'] = len(frame_vector_ids)
            
            # --- 7. Finalize and Commit ---
            update_task_state(task_self, TaskStatus.PROCESSING, "Saving index and finalizing record...", 95.0)
            
            doc.status = "completed"
            db.commit()
            vector_store.save_index()
            
            # Final artifact counts
            artifacts['vector_count'] = vector_store.index.ntotal 
            artifacts['metadata_count'] = len(new_chunk_records) + artifacts.get('visual_count', 0)
            
            print(f"[Orchestrator] Successfully processed {source_id}.")
            return artifacts

        except Exception as e:
            # --- Error Handling ---
            print(f"[Orchestrator] FAILED processing for {source_id}: {e}")
            db.rollback()
            doc.status = "failed"
            db.add(doc)
            db.commit()
            raise
        
# app/services/ingestion_orchestrator.py (Add this function definition)

def process_image_source(
    task_self,
    source_id: str,
    original_file_path: Path,
    file_name: str,
    doc_type: IngestType
) -> Dict[str, Any]:
    """
    (Placeholder) The main processing pipeline for image files.
    """
    print(f"[Orchestrator] Processing image {source_id} (placeholder)...")
    
    # Placeholder: In a real implementation, this would call image analysis and indexing.
    update_task_state(task_self, TaskStatus.SUCCESS, "Image processed successfully (placeholder).", 100.0)
    
    print(f"[Orchestrator] Image processing complete (placeholder).")
    return {"status": "success_placeholder"}