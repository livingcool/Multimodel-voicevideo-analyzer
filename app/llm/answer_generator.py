# app/llm/answer_generator.py (Old Imports)
from typing import List, Optional, Tuple
from google import genai
from google.genai import types

from app.api.schemas import SourceChunk, QueryResponse
from app.config import get_settings # <--- Need to modify this
from app.config import get_settings, LLMProvider
from app.llm.prompt_templates import SYSTEM_INSTRUCTION, RAG_PROMPT_TEMPLATE

class AnswerGenerator:
    """
    Service responsible for generating the final, grounded answer 
    using the Gemini API.
    """
    
    # app/llm/answer_generator.py (New Logic)

    def __init__(self):
        settings = get_settings()
        
        # FIX: Compare the settings value with the imported Enum class
        if settings.LLM_PROVIDER != LLMProvider.GEMINI: # <--- CHANGED HERE
            print(f"FATAL: AnswerGenerator configured for Gemini, but LLM_PROVIDER is {settings.LLM_PROVIDER}")
            raise ValueError("LLM Provider Mismatch")
        
        # ... rest of the code is unchanged ...
            
        # Initialize the Gemini Client
        self.client = genai.Client(
            api_key=settings.GOOGLE_API_KEY
        )
        # Use a model appropriate for grounded QA
        self.model_name = "gemini-2.5-flash" 
        
        print(f"[LLM] Gemini client initialized with model {self.model_name}.")

    def generate_answer(self, query: str, chunks: List[SourceChunk]) -> QueryResponse:
        """
        Generates an answer grounded in the provided context chunks.
        """
        
        if not self.client:
            raise Exception("Gemini client failed to initialize. Check GOOGLE_API_KEY.")
        if not chunks:
            # Fallback when retriever finds nothing
            return QueryResponse(
                answer="I cannot answer this question because no relevant corporate knowledge was found.",
                sources=[],
                query_id="N/A"
            )
        
        # 1. Format the context for the prompt
        context_list = []
        for i, chunk in enumerate(chunks):
            # Format each chunk to include source info
            source_info = f"[Source {i+1}, File: {chunk.source_file}, Time: {chunk.start_time:.1f}s]"
            context_list.append(f"{source_info}\n{chunk.chunk_text}")
            
        context_string = "\n\n".join(context_list)
        
        # 2. Assemble the final prompt
        final_prompt = RAG_PROMPT_TEMPLATE.format(
            context=context_string,
            query=query
        )
        
        print(f"[LLM] Sending query and {len(chunks)} chunks to Gemini...")
        
        try:
            # 3. Call the Gemini API
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.2, # Lower temperature for factual RAG
                max_output_tokens=2048
            )
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=final_prompt,
                config=config
            )
            
            # 4. Map the response back to the QueryResponse schema
            return QueryResponse(
                answer=response.text,
                # Pass the original chunks back as sources
                sources=chunks
            )

        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return QueryResponse(
                answer=f"The LLM failed to generate a response due to an API error. ({type(e).__name__})",
                sources=[],
                query_id="N/A"
            )

# --- Singleton setup for Dependency Injection ---

_answer_generator: Optional[AnswerGenerator] = None

def get_answer_generator() -> AnswerGenerator:
    """
    Dependency injector for the singleton AnswerGenerator service.
    """
    global _answer_generator
    if _answer_generator is None:
        _answer_generator = AnswerGenerator()
    return _answer_generator