import torch
import numpy as np
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from app.config import Settings, get_settings

class EmbeddingService:
    """
    A service to handle the loading of the embedding model and
    the creation of text embeddings.
    
    This is designed as a singleton to ensure the (potentially large)
    model is only loaded into memory once.
    """
    
    def __init__(self, settings: Settings):
        self.model_name = settings.EMBEDDING_MODEL
        
        # Auto-detect the best device (CUDA/GPU if available, else CPU)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[EmbeddingService] Initializing model '{self.model_name}' on device '{self.device}'...")
        
        # Load the model from HuggingFace
        self.model = SentenceTransformer(self.model_name, device=self.device)
        
        # Get the embedding dimension from the model
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"[EmbeddingService] Model loaded. Embedding dimension: {self.embedding_dim}")

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Generates embeddings for a list of text chunks.
        
        Args:
            texts: A list of strings to embed.
            
        Returns:
            A numpy array of shape (num_texts, embedding_dim).
        """
        if not texts:
            return np.array([])
            
        print(f"[EmbeddingService] Generating embeddings for {len(texts)} text chunks...")
        
        # We normalize embeddings to make cosine similarity search faster and simpler
        embeddings = self.model.encode(
            texts, 
            show_progress_bar=False,
            normalize_embeddings=True,
            device=self.device
        )
        
        print(f"[EmbeddingService] Embeddings generated with shape {embeddings.shape}")
        return embeddings

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generates an embedding for a single text chunk.
        
        Args:
            text: A single string to embed.
            
        Returns:
            A 1D numpy array of shape (embedding_dim,).
        """
        # Get the 2D array (shape 1, dim) and return the first (only) row
        return self.embed_texts([text])[0]

# --- Singleton setup for Dependency Injection ---

_embedding_service: Optional[EmbeddingService] = None

def get_embedding_service() -> EmbeddingService:
    """
    Dependency injector for FastAPI to get a singleton EmbeddingService.
    """
    global _embedding_service
    if _embedding_service is None:
        settings = get_settings()
        _embedding_service = EmbeddingService(settings)
    return _embedding_service