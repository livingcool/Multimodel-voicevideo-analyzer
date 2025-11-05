from typing import List,Optional
import numpy as np
from app.api.schemas import QueryRequest, SourceChunk
from app.services.embedder import get_embedding_service
from app.store.vector_store import get_vector_store
from app.store.metadata_store import get_db, get_chunks_by_vector_ids, TextChunk


class Retriever:
    """
    Core service responsible for accepting a query and retrieving 
    the most relevant text chunks (context) from the vector store.
    """
    def __init__(self):
        self.embedder = get_embedding_service()
        self.vector_store = get_vector_store()
    
    def retrieve_chunks(self, request: QueryRequest) -> List[SourceChunk]:
        """
        Processes the query, searches the vector index, and returns 
        the enriched source chunks.
        """
        print(f"[Retriever] Received query: '{request.query}'")
        
        # 1. Embed the user query
        print(f"[Retriever] Embedding query...")
        query_vector = self.embedder.embed_text(request.query)
        
        # 2. Search the FAISS index
        # This returns the scores (distances) and the internal FAISS IDs
        print(f"[Retriever] Searching FAISS for top_k={request.top_k}...")
        distances, vector_ids = self.vector_store.search(query_vector, request.top_k)
        
        # Filter out invalid IDs (e.g., -1 if index is not full)
        valid_vector_ids = [int(vid) for vid in vector_ids if vid != -1]
        
        if not valid_vector_ids:
            print("[Retriever] No relevant vectors found.")
            return []
            
        # 3. Retrieve metadata (text content) from the SQL DB
        print(f"[Retriever] Retrieving metadata for {len(valid_vector_ids)} vectors...")
        
        # FAISS results (distances and IDs) often need to be sorted before use, 
        # but the search result is already distance-sorted. We need to 
        # match the retrieved chunks back to their distance scores.
        
        # Create a mapping of FAISS ID -> distance score for easy lookup
        score_map = {int(vector_ids[i]): float(distances[i]) 
                     for i in range(len(vector_ids)) if vector_ids[i] != -1}
        
        # Retrieve the chunks from the database
        with get_db() as db:
            metadata_chunks: List[TextChunk] = get_chunks_by_vector_ids(db, valid_vector_ids)
        
        # 4. Assemble the final SourceChunk list for the LLM
        source_chunks: List[SourceChunk] = []
        for chunk in metadata_chunks:
            # Check if the chunk belongs to a document matching the filters
            # (Note: Filter logic is simplified here; fully integrating it 
            # requires modifying the SQL query in metadata_store.py)
            
            # For now, just map the retrieved chunk data to the schema
            score = score_map.get(chunk.vector_id, 0.0)
            
            source_chunks.append(
                SourceChunk(
                    source_file=chunk.document.source_file_name,
                    chunk_text=chunk.text_content,
                    start_time=chunk.start_time,
                    end_time=chunk.end_time,
                    score=score,
                    metadata={"document_id": chunk.document_id, "vector_id": chunk.vector_id}
                )
            )
            
        # Ensure the final list is sorted by score (distance) descending
        source_chunks.sort(key=lambda x: x.score, reverse=True)
        
        print(f"[Retriever] Retrieved {len(source_chunks)} relevant chunks.")
        return source_chunks

# --- Singleton setup for Dependency Injection ---

_retriever: Optional[Retriever] = None

def get_retriever() -> Retriever:
    """
    Dependency injector for the singleton Retriever service.
    """
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever