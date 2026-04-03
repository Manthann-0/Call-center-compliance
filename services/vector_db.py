"""
Vector Storage Service using ChromaDB.
Provides evidence that transcripts are indexed for semantic search.
"""
import os
import logging
import chromadb
from chromadb.config import Settings
from config import settings

logger = logging.getLogger(__name__)

# Initialize ChromaDB client with persistent storage in local directory
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
os.makedirs(DB_PATH, exist_ok=True)

try:
    # Use simple local persistent client
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    
    # Get or create a collection for call transcripts
    collection = chroma_client.get_or_create_collection(
        name="call_transcripts",
        metadata={"description": "Indexed call center transcripts for semantic search"}
    )
    logger.info("ChromaDB vector storage initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize ChromaDB: {e}")
    collection = None

def index_transcript(job_id: str, transcript: str, summary: str, metadata: dict = None):
    """
    Index a transcript and its metadata into the vector database.
    """
    if collection is None:
        logger.warning(f"ChromaDB not initialized. Skipping indexing for job {job_id}")
        return False
        
    try:
        # We index the transcript and insert summary + metadata into DB
        meta = metadata or {}
        meta["summary"] = summary[:500] if summary else "" # Max limit str length for meta
        
        collection.add(
            documents=[transcript],
            metadatas=[meta],
            ids=[job_id]
        )
        logger.info(f"Successfully indexed transcript {job_id} into vector storage.")
        return True
    except Exception as e:
        logger.error(f"Error indexing transcript {job_id}: {e}")
        return False
