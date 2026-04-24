# =============================================================================
# backend/app/services/vector_store.py
# ChromaDB vector store wrapper for the DMRE embedding pipeline.
# Manages a single collection (name configured via CHROMA_COLLECTION in .env)
# and exposes add_chunks() for ingestion and query() for retrieval.
# =============================================================================

from __future__ import annotations

from app.config import settings

_client = None
_collection = None


def _get_collection():
    """Connect to ChromaDB and return (or create) the DMRE collection."""
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "chromadb is not installed. "
            "Run: pip install chromadb==0.6.3"
        ) from exc

    _client = chromadb.HttpClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
    )
    # cosine distance is standard for sentence embeddings.
    _collection = _client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def add_chunks(
    chroma_ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    """
    Store embedding vectors in ChromaDB.

    Args:
        chroma_ids:  Unique IDs for each chunk (format: "{memory_id}_{chunk_index}").
        embeddings:  384-dim float vectors from embedding_service.embed().
        documents:   Raw chunk text strings (stored for snippet retrieval).
        metadatas:   Dicts of scalar metadata attached to each chunk.
    """
    collection = _get_collection()
    collection.add(
        ids=chroma_ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def query(
    query_embedding: list[float],
    n_results: int = 20,
) -> dict:
    """
    Retrieve the top-n most similar chunks from ChromaDB.

    Args:
        query_embedding: 384-dim query vector from embedding_service.embed_query().
        n_results:       Number of candidates to return before re-ranking.

    Returns:
        ChromaDB result dict with keys: ids, documents, metadatas, distances.
        Distances are cosine distances (lower = more similar).
    """
    collection = _get_collection()
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )


def delete_memory_chunks(memory_id: str) -> None:
    """Remove all chunks belonging to a memory (used when a memory is deleted)."""
    collection = _get_collection()
    # ChromaDB where filter matches on metadata fields.
    collection.delete(where={"memory_id": memory_id})
