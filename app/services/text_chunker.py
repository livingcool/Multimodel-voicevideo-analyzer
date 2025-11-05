from typing import List, Optional, Tuple

class TextChunker:
    """
    A simple text chunker designed for transcripts and documents.
    
    It splits text by paragraphs and then combines them into chunks
    of a desired size, maintaining paragraph integrity.
    """
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        Args:
            chunk_size: The target number of characters per chunk.
            chunk_overlap: The target number of characters to overlap
                           between chunks to maintain context.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[str]:
        """
        Splits a large text into smaller chunks.
        
        Args:
            text: The full text string to be chunked.
            
        Returns:
            A list of text chunks.
        """
        if not text:
            return []
            
        # 1. Split the text into logical blocks (paragraphs)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return [] # No content
            
        chunks = []
        current_chunk = ""

        # 2. Combine paragraphs into chunks of the desired size
        for paragraph in paragraphs:
            # If adding the next paragraph fits, add it
            if len(current_chunk) + len(paragraph) + 1 <= self.chunk_size:
                current_chunk += paragraph + "\n\n"
            
            # If the current chunk is empty but the paragraph is too big,
            # we must split the paragraph itself.
            elif not current_chunk and len(paragraph) > self.chunk_size:
                chunks.extend(self._split_long_paragraph(paragraph))
                
            # If the paragraph makes the chunk too big, finalize the
            # current chunk and start a new one.
            else:
                chunks.append(current_chunk.strip())
                
                # Start the new chunk with an overlap
                overlap_text = self._get_overlap(current_chunk)
                current_chunk = overlap_text + paragraph + "\n\n"

        # Add the last remaining chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """Recursively split a paragraph that is too long."""
        sentences = [s.strip() for s in paragraph.split(". ") if s.strip()]
        if not sentences:
            return [paragraph] # Can't split further

        mini_chunks = []
        current_mini_chunk = ""
        for sentence in sentences:
            if len(current_mini_chunk) + len(sentence) + 2 <= self.chunk_size:
                current_mini_chunk += sentence + ". "
            elif not current_mini_chunk: # Sentence itself is too long
                mini_chunks.append(sentence + ".")
            else:
                mini_chunks.append(current_mini_chunk.strip())
                current_mini_chunk = sentence + ". "
        
        if current_mini_chunk:
            mini_chunks.append(current_mini_chunk.strip())
            
        return mini_chunks

    def _get_overlap(self, chunk: str) -> str:
        """Gets the last ~N characters from a chunk to use as overlap."""
        # Find the nearest sentence break to the overlap point
        overlap_point = max(0, len(chunk) - self.chunk_overlap)
        
        # Try to find a sentence end before the overlap point
        sentence_end = chunk.rfind(". ", 0, overlap_point)
        if sentence_end != -1:
            return chunk[sentence_end + 2:] # Return text after the period
        
        # If no sentence, find a word break
        word_break = chunk.rfind(" ", 0, overlap_point + 10)
        if word_break != -1:
            return chunk[word_break + 1:]
            
        # If all else fails, just take the raw character overlap
        return chunk[overlap_point:]

    def chunk_transcript(self, transcript_data: dict) -> List[Tuple[str, float, float]]:
        """
        A specific chunker for Sarvam's transcript format.
        It chunks based on segments with timestamps.
        
        Args:
            transcript_data: The raw JSON object from Sarvam.
            
        Returns:
            A list of tuples: (text_chunk, start_time, end_time)
        """
        # Sarvam format assumption: { "transcript": "...", "segments": [...] }
        # If no segments, fall back to simple text chunking
        segments = transcript_data.get("segments")
        if not segments:
            full_text = transcript_data.get("transcript", "")
            return [(chunk, 0.0, 0.0) for chunk in self.chunk_text(full_text)]

        chunks = []
        current_chunk_text = ""
        current_start_time = segments[0].get("start", 0.0)
        current_end_time = 0.0

        for segment in segments:
            segment_text = segment.get("text", "").strip()
            segment_start = segment.get("start", current_end_time)
            segment_end = segment.get("end", segment_start)

            if len(current_chunk_text) + len(segment_text) + 1 <= self.chunk_size:
                # Add to current chunk
                current_chunk_text += segment_text + " "
                current_end_time = segment_end
            else:
                # Finalize the current chunk
                chunks.append((current_chunk_text.strip(), current_start_time, current_end_time))
                
                # Start new chunk
                current_chunk_text = segment_text + " "
                current_start_time = segment_start
                current_end_time = segment_end
        
        # Add the final chunk
        if current_chunk_text:
            chunks.append((current_chunk_text.strip(), current_start_time, current_end_time))
            
        return chunks

# --- Singleton setup for Dependency Injection ---

_text_chunker: Optional[TextChunker] = None

def get_text_chunker() -> TextChunker:
    """Gets a singleton instance of the TextChunker."""
    global _text_chunker
    if _text_chunker is None:
        _text_chunker = TextChunker() # Use default size
    return _text_chunker