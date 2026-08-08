# RAG ENGINE: LangChain + FAISS + HuggingFace Embeddings for grounded resume Q&A
# Uses all-MiniLM-L6-v2 (free, local, no API key needed) + FAISS in-memory vector store

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy imports — app.py won't crash if langchain is not yet installed
_langchain_available = False
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings
    _langchain_available = True
    logger.info("LangChain RAG engine loaded successfully.")
except ImportError as e:
    logger.warning(f"LangChain not installed. RAG features disabled. Error: {e}")


class ResumeRAGEngine:
    """
    Retrieval-Augmented Generation engine for resume Q&A.

    Pipeline:
      1. ingest_text(text) -> Chunk -> Embed (HuggingFace) -> Store (FAISS)
      2. query(question)   -> Semantic similarity search -> Return top-k chunks
      3. build_grounded_prompt(q, jd) -> Grounded LLM prompt string
    """

    def __init__(self):
        self.vector_store = None
        self.embeddings = None
        self.chunk_count = 0
        self._ready = False

        if not _langchain_available:
            logger.warning("RAG engine in degraded mode — LangChain not available.")
            return

        try:
            # Free open-source embeddings model — runs on CPU, no API key needed
            self.embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True}
            )
            self._ready = True
            logger.info("HuggingFace embeddings (all-MiniLM-L6-v2) initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def is_indexed(self) -> bool:
        return self.vector_store is not None and self.chunk_count > 0

    def ingest_text(self, text: str, source_label: str = "resume") -> dict:
        """
        Chunk raw text and store embeddings in FAISS vector store.
        Returns: dict with success status and number of chunks indexed.
        """
        if not self._ready:
            return {"success": False, "error": "RAG engine not ready. Install LangChain dependencies."}

        if not text or not text.strip():
            return {"success": False, "error": "Empty text provided."}

        try:
            # Split text into overlapping 500-char chunks
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            chunks = splitter.create_documents(
                texts=[text],
                metadatas=[{"source": source_label}] * len(splitter.split_text(text))
            )

            if not chunks:
                return {"success": False, "error": "No chunks created from document."}

            # Create or merge into FAISS vector store
            if self.vector_store is None:
                self.vector_store = FAISS.from_documents(chunks, self.embeddings)
            else:
                new_store = FAISS.from_documents(chunks, self.embeddings)
                self.vector_store.merge_from(new_store)

            self.chunk_count += len(chunks)
            logger.info(f"Indexed {len(chunks)} chunks from '{source_label}'. Total: {self.chunk_count}")

            return {
                "success": True,
                "chunks_indexed": len(chunks),
                "total_chunks": self.chunk_count,
                "message": f"Successfully indexed {len(chunks)} chunks from {source_label}."
            }

        except Exception as e:
            logger.error(f"RAG ingest error: {e}")
            return {"success": False, "error": f"Indexing failed: {str(e)}"}

    def query(self, question: str, top_k: int = 3) -> dict:
        """
        Semantic similarity search over indexed documents.
        Returns: dict with retrieved chunks and combined context string.
        """
        if not self._ready:
            return {"success": False, "error": "RAG engine not ready."}
        if not self.is_indexed:
            return {"success": False, "error": "No document indexed yet. Please upload a resume first."}
        if not question or not question.strip():
            return {"success": False, "error": "Question cannot be empty."}

        try:
            docs_with_scores = self.vector_store.similarity_search_with_score(question, k=top_k)

            retrieved_chunks = [
                {
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", "unknown"),
                    "relevance_score": round(float(1 - score), 3)
                }
                for doc, score in docs_with_scores
            ]

            context = "\n\n---\n\n".join([c["content"] for c in retrieved_chunks])

            return {
                "success": True,
                "question": question,
                "retrieved_chunks": retrieved_chunks,
                "context": context,
                "chunks_retrieved": len(retrieved_chunks)
            }

        except Exception as e:
            logger.error(f"RAG query error: {e}")
            return {"success": False, "error": f"Query failed: {str(e)}"}

    def build_grounded_prompt(self, question: str, job_description: str = "") -> dict:
        """
        Retrieve relevant context and build a grounded LLM prompt.
        LLM is instructed to answer ONLY from retrieved resume context — no hallucinations.
        """
        query_result = self.query(question, top_k=3)
        if not query_result.get("success"):
            return query_result

        context = query_result["context"]
        jd_section = f"\n\nJob Description Context:\n{job_description[:1000]}" if job_description else ""

        grounded_prompt = f"""You are an expert resume analyst. Answer the question below using ONLY the provided resume context.
If the answer is not found in the context, say exactly: "This information is not mentioned in the resume."
Do NOT make up or assume any information not present in the context.

Resume Context:
{context}
{jd_section}

Question: {question}

Answer (grounded strictly in the resume context above):"""

        return {
            "success": True,
            "grounded_prompt": grounded_prompt,
            "source_chunks": query_result["retrieved_chunks"],
            "context": context
        }

    def clear(self) -> dict:
        """Clear the vector store and reset for a new session."""
        self.vector_store = None
        self.chunk_count = 0
        logger.info("RAG vector store cleared.")
        return {"success": True, "message": "Vector store cleared. Ready for new document."}

    def status(self) -> dict:
        """Return current engine status."""
        return {
            "ready": self._ready,
            "indexed": self.is_indexed,
            "chunks_indexed": self.chunk_count,
            "embeddings_model": "all-MiniLM-L6-v2" if self._ready else "unavailable",
            "vector_store": "FAISS (in-memory)" if self.is_indexed else "empty"
        }


# Module-level singleton — shared across all Flask requests
_rag_instance: Optional[ResumeRAGEngine] = None


def get_rag_engine() -> ResumeRAGEngine:
    """Get or create the singleton RAG engine instance."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = ResumeRAGEngine()
    return _rag_instance
