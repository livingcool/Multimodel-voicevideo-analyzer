import faiss
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List

from app.config import Settings, get_settings
from app.services.embedder import EmbeddingService, get_embedding_service

class VectorStore:
    """
    A service to manage the FAISS vector index.
    
    This is a singleton that loads the index on startup and provides
    methods to add vectors and search.
    """
    
    def __init__(self, settings: Settings, embed_service: EmbeddingService):
        self.index_path = settings.VECTOR_DIR / "main_index.faiss"
        self.embedding_dim = embed_service.embedding_dim
        self.index = self._load_or_create_index()
        
    def _load_or_create_index(self) -> faiss.Index:
        """Loads the FAISS index from disk, or creates a new one."""
        
        if self.index_path.exists():
            try:
                print(f"[VectorStore] Loading existing FAISS index from {self.index_path}")
                index = faiss.read_index(str(self.index_path))
                if index.d != self.embedding_dim:
                    raise Exception(f"Index dim ({index.d}) != model dim ({self.embedding_dim})")
                return index
            except Exception as e:
                print(f"[VectorStore] FAILED to load index: {e}. Rebuilding...")
                # Fall through to create a new one
        
        # --- Create a new index ---
        print(f"[VectorStore] Creating new FAISS index with dim {self.embedding_dim}")
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Using IndexFlatIP because our embedder normalizes embeddings.
        # Inner Product (IP) on normalized vectors is equivalent to Cosine Similarity.
        index = faiss.IndexFlatIP(self.embedding_dim)
        return index

    def add_vectors(self, vectors: np.ndarray) -> List[int]:
        """
        Adds a batch of vectors to the index.
        
        Args:
            vectors: A 2D numpy array of shape (num_vectors, embedding_dim).
            
        Returns:
            A list of the FAISS IDs (indices) for the newly added vectors.
        """
        if not vectors.any():
            return []
            
        if vectors.ndim != 2 or vectors.shape[1] != self.embedding_dim:
            raise ValueError(f"Invalid vector shape. Expected (n, {self.embedding_dim})")
        
        # FAISS requires float32
        vectors = vectors.astype('float32')
        
        start_index = self.index.ntotal
        self.index.add(vectors)
        count = len(vectors)
        
        print(f"[VectorStore] Added {count} new vectors. Total vectors: {self.index.ntotal}")
        
        # Return the sequential IDs that FAISS just assigned
        return list(range(start_index, start_index + count))

    def search(self, query_vector: np.ndarray, top_k: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Searches the index for the most similar vectors.
        
        Args:
            query_vector: A 1D numpy array (the query embedding).
            top_k: The number of results to return.
            
        Returns:
            A tuple of (distances, indices).
        """
        if query_vector.ndim == 1:
            # FAISS search expects a 2D array of (1, dim)
            query_vector = np.expand_dims(query_vector, axis=0)
            
        query_vector = query_vector.astype('float32')
        
        # D = distances (scores), I = indices (the vector IDs)
        distances, indices = self.index.search(query_vector, top_k)
        
        # Return the results for the first (and only) query
        return distances[0], indices[0]

    def save_index(self):
        """Saves the current index state to disk."""
        print(f"[VectorStore] Saving FAISS index to {self.index_path}...")
        faiss.write_index(self.index, str(self.index_path))
        print("[VectorStore] Index saved.")

# --- Singleton setup for Dependency Injection ---

_vector_store: Optional[VectorStore] = None

def get_vector_store() -> VectorStore:
    """
    Dependency injector to get a singleton VectorStore.
    This ensures the index is only loaded once.
    """
    global _vector_store
    if _vector_store is None:
        # This service depends on the embedder service being ready
        embed_service = get_embedding_service()
        settings = get_settings()
        _vector_store = VectorStore(settings, embed_service)
    return _vector_store