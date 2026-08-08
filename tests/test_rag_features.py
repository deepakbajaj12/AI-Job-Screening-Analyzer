"""
Test RAG Engine & RAG API endpoints.
"""
import pytest
from backend.rag_engine import get_rag_engine


def test_rag_engine_init():
    rag = get_rag_engine()
    status = rag.status()
    assert status["ready"] is True
    assert "all-MiniLM-L6-v2" in status["embeddings_model"]


def test_rag_ingest_and_query():
    rag = get_rag_engine()
    rag.clear()

    sample_text = """
    Deepak Bajaj is a Full-Stack AI Engineer experienced in Python, Flask, React, and MongoDB.
    Built a 3-tier location fallback system using Nominatim and Foursquare APIs.
    Developed BiasGuard for auditing hiring evaluations for gender and prestige bias.
    Created a LangChain RAG pipeline with FAISS vector store and HuggingFace embeddings.
    """

    ingest_res = rag.ingest_text(sample_text, source_label="resume_test")
    assert ingest_res["success"] is True
    assert ingest_res["chunks_indexed"] > 0
    assert rag.is_indexed is True

    # Query 1: Technical skills
    query_res = rag.query("What programming languages and frameworks does Deepak know?")
    assert query_res["success"] is True
    assert len(query_res["retrieved_chunks"]) > 0
    assert "Python" in query_res["context"] or "React" in query_res["context"]

    # Query 2: Grounded prompt building
    prompt_res = rag.build_grounded_prompt("Tell me about the location fallback system.")
    assert prompt_res["success"] is True
    assert "grounded_prompt" in prompt_res
    assert "Nominatim" in prompt_res["context"] or "Foursquare" in prompt_res["context"]

    # Clear
    clear_res = rag.clear()
    assert clear_res["success"] is True
    assert rag.is_indexed is False


def test_rag_empty_inputs():
    rag = get_rag_engine()
    rag.clear()

    # Empty text ingest
    err_ingest = rag.ingest_text("")
    assert err_ingest["success"] is False

    # Query without indexing
    err_query = rag.query("What skills are listed?")
    assert err_query["success"] is False
