# RAG ENGINE: Ultra-Low-Memory Hybrid RAG for Resume Q&A
# Optimized for 512MB RAM environments (Render Free Tier)
# Primary: LangChain + FAISS + HuggingFace Embeddings (Lazy Loaded)
# Fallback: Scikit-Learn TF-IDF Vectorizer + Cosine Similarity (<5MB RAM)

import gc
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Check dependency availability without loading heavy models into RAM at startup
_langchain_available = False
_huggingface_available = False
_tfidf_available = False

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
    _langchain_available = True
except ImportError:
    pass

try:
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings
    _huggingface_available = True
except ImportError:
    pass

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _tfidf_available = True
except ImportError:
    pass


class ResumeRAGEngine:
    """
    Memory-Efficient Retrieval-Augmented Generation Engine.

    Features:
      - Lazy Loading: Embeddings model is loaded only on first query/ingest
      - Dual Vector Engine: Tries FAISS+HuggingFace first; falls back to lightweight TF-IDF (<5MB RAM)
      - Explicit GC: Clears memory pools after operations to prevent memory leaks
    """

    def __init__(self):
        self.vector_store = None
        self.embeddings = None
        self.chunk_count = 0
        self._mode = "uninitialized"  # "faiss" or "tfidf"
        self._raw_chunks: List[str] = []
        self._tfidf_vectorizer = None
        self._tfidf_matrix = None

    @property
    def is_ready(self) -> bool:
        return _langchain_available or _tfidf_available

    @property
    def is_indexed(self) -> bool:
        return self.chunk_count > 0

    def _init_embeddings(self) -> bool:
        """Lazy load HuggingFace Embeddings on demand."""
        if self.embeddings is not None:
            return True
        if not _huggingface_available:
            return False

        try:
            logger.info("Lazy-loading HuggingFace all-MiniLM-L6-v2 embeddings...")
            self.embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True}
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to load HuggingFace embeddings (RAM limit?): {e}. Falling back to TF-IDF engine.")
            self.embeddings = None
            return False

    def ingest_text(self, text: str, source_label: str = "resume") -> dict:
        """
        Chunk raw text and store in vector index.
        Uses FAISS+HuggingFace if RAM permits, otherwise TF-IDF.
        """
        if not text or not text.strip():
            return {"success": False, "error": "Empty text provided."}

        try:
            # 1. Chunk document
            if _langchain_available:
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=500,
                    chunk_overlap=50,
                    separators=["\n\n", "\n", ". ", " ", ""]
                )
                chunk_objs = splitter.create_documents(
                    texts=[text],
                    metadatas=[{"source": source_label}] * len(splitter.split_text(text))
                )
                chunks_text = [doc.page_content for doc in chunk_objs]
            else:
                # Simple fallback splitter
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                chunks_text = paragraphs if paragraphs else [text[i:i+500] for i in range(0, len(text), 450)]

            if not chunks_text:
                return {"success": False, "error": "No chunks generated from document."}

            self._raw_chunks = chunks_text
            self.chunk_count = len(chunks_text)

            # 2. Try FAISS Vector Store first
            faiss_success = False
            if _huggingface_available and self._init_embeddings():
                try:
                    if _langchain_available:
                        docs = [Document(page_content=c, metadata={"source": source_label}) for c in chunks_text]
                        if self.vector_store is None:
                            self.vector_store = FAISS.from_documents(docs, self.embeddings)
                        else:
                            self.vector_store.merge_from(FAISS.from_documents(docs, self.embeddings))
                        self._mode = "faiss"
                        faiss_success = True
                except Exception as faiss_err:
                    logger.warning(f"FAISS indexing error: {faiss_err}. Reverting to TF-IDF.")
                    self.vector_store = None

            # 3. TF-IDF Fallback (<5MB RAM footprint)
            if not faiss_success:
                if _tfidf_available:
                    self._tfidf_vectorizer = TfidfVectorizer(stop_words='english')
                    self._tfidf_matrix = self._tfidf_vectorizer.fit_transform(self._raw_chunks)
                    self._mode = "tfidf"
                else:
                    self._mode = "raw"

            gc.collect()  # Release transient objects from RAM

            return {
                "success": True,
                "chunks_indexed": len(chunks_text),
                "total_chunks": self.chunk_count,
                "engine_mode": self._mode,
                "message": f"Successfully indexed {len(chunks_text)} chunks ({self._mode.upper()} mode)."
            }

        except Exception as e:
            logger.error(f"RAG ingest error: {e}")
            return {"success": False, "error": f"Indexing failed: {str(e)}"}

    def query(self, question: str, top_k: int = 3) -> dict:
        """
        Semantic/Cosine similarity search over indexed chunks.
        """
        if not self.is_indexed:
            return {"success": False, "error": "No document indexed yet. Please upload a resume first."}
        if not question or not question.strip():
            return {"success": False, "error": "Question cannot be empty."}

        try:
            retrieved_chunks = []

            # 1. FAISS Mode
            if self._mode == "faiss" and self.vector_store is not None:
                try:
                    docs_with_scores = self.vector_store.similarity_search_with_score(question, k=top_k)
                    for doc, score in docs_with_scores:
                        retrieved_chunks.append({
                            "content": doc.page_content,
                            "source": doc.metadata.get("source", "resume"),
                            "relevance_score": round(float(max(0.0, 1.0 - score)), 3)
                        })
                except Exception as query_err:
                    logger.warning(f"FAISS query error: {query_err}. Switching to TF-IDF search.")
                    self._mode = "tfidf"

            # 2. TF-IDF Mode (Fast, low-RAM cosine similarity search)
            if (self._mode == "tfidf" or not retrieved_chunks) and _tfidf_available and self._tfidf_matrix is not None:
                q_vec = self._tfidf_vectorizer.transform([question])
                sim_scores = cosine_similarity(q_vec, self._tfidf_matrix).flatten()
                top_indices = sim_scores.argsort()[-top_k:][::-1]

                for idx in top_indices:
                    score = float(sim_scores[idx])
                    if score > 0.0 or len(retrieved_chunks) < 1:  # Include top match
                        retrieved_chunks.append({
                            "content": self._raw_chunks[idx],
                            "source": "resume",
                            "relevance_score": round(score, 3)
                        })

            # 3. Simple Keyword Search Mode (Last resort fallback)
            if not retrieved_chunks and self._raw_chunks:
                words = set(question.lower().split())
                scored = []
                for chunk in self._raw_chunks:
                    score = sum(1 for w in words if w in chunk.lower())
                    scored.append((score, chunk))
                scored.sort(key=lambda x: x[0], reverse=True)
                for score, chunk in scored[:top_k]:
                    retrieved_chunks.append({
                        "content": chunk,
                        "source": "resume",
                        "relevance_score": round(min(1.0, score / max(1, len(words))), 3)
                    })

            context = "\n\n---\n\n".join([c["content"] for c in retrieved_chunks])
            gc.collect()

            return {
                "success": True,
                "question": question,
                "retrieved_chunks": retrieved_chunks,
                "context": context,
                "chunks_retrieved": len(retrieved_chunks),
                "engine_mode": self._mode
            }

        except Exception as e:
            logger.error(f"RAG query error: {e}")
            return {"success": False, "error": f"Query failed: {str(e)}"}

    def build_grounded_prompt(self, question: str, job_description: str = "") -> dict:
        """Build grounded LLM prompt string using retrieved context."""
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
            "context": context,
            "engine_mode": query_result.get("engine_mode", "hybrid")
        }

    def clear(self) -> dict:
        """Clear indices and run garbage collection."""
        self.vector_store = None
        self.chunk_count = 0
        self._raw_chunks = []
        self._tfidf_vectorizer = None
        self._tfidf_matrix = None
        self._mode = "uninitialized"
        gc.collect()
        logger.info("RAG engine cleared and RAM garbage collected.")
        return {"success": True, "message": "Vector store cleared."}

    def status(self) -> dict:
        """Return engine status."""
        return {
            "ready": self.is_ready,
            "indexed": self.is_indexed,
            "chunks_indexed": self.chunk_count,
            "mode": self._mode,
            "embeddings_model": "all-MiniLM-L6-v2 (lazy-loaded)" if _huggingface_available else "TF-IDF (low-memory)",
            "vector_store": self._mode.upper() if self.is_indexed else "empty"
        }


# Singleton instance
_rag_instance: Optional[ResumeRAGEngine] = None


def get_rag_engine() -> ResumeRAGEngine:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = ResumeRAGEngine()
    return _rag_instance
