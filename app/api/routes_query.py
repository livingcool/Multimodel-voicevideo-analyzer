from fastapi import APIRouter, Depends
from app.api.schemas import QueryRequest, QueryResponse
from app.retrieval.retriever import get_retriever
from app.llm.answer_generator import get_answer_generator

router = APIRouter()

@router.post("/query", response_model=QueryResponse)
async def query_system(
    request: QueryRequest,
    retriever = Depends(get_retriever),
    answer_generator = Depends(get_answer_generator)
):
    """
    Accepts a natural language query and returns a synthesized answer
    based on the ingested multimedia content (RAG).
    """
    
    print(f"Received query: {request.query}")
    
    # 1. Retrieve the relevant text chunks
    relevant_chunks = retriever.retrieve_chunks(request)
    
    # 2. Generate the grounded answer using the LLM
    response = answer_generator.generate_answer(request.query, relevant_chunks)
    
    return response