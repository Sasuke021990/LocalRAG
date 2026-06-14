"""
Text chunker for splitting documents into manageable pieces
"""

import logging
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

class TextChunker:
    """
    A class to split text into chunks for processing.
    
    Uses RecursiveCharacterTextSplitter from LangChain to create overlapping 
    text chunks that maintain context while being small enough for embeddings.
    """
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        """
        Initialize the TextChunker with specified parameters.
        
        Args:
            chunk_size (int): Maximum number of characters per chunk
            chunk_overlap (int): Number of characters that overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize the text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        logger.info(f"Initialized TextChunker with chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
    
    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into chunks.
        
        Args:
            text (str): The text to be chunked
            
        Returns:
            List of dictionaries containing chunk information
        """
        if not text or not isinstance(text, str):
            logger.warning("Empty or invalid text provided for chunking")
            return []
        
        try:
            # Split the text into chunks
            docs = self.text_splitter.create_documents([text])
            
            # Convert to list of dictionaries with metadata
            chunks = []
            for i, doc in enumerate(docs):
                chunk_info = {
                    "id": f"chunk_{i}",
                    "content": doc.page_content,
                    "metadata": {
                        "source": doc.metadata.get("source", ""),
                        "chunk_index": i,
                        "chunk_size": len(doc.page_content)
                    }
                }
                chunks.append(chunk_info)
            
            logger.info(f"Split text into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking text: {str(e)}")
            raise

    def get_chunk_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Get statistics about the chunks.
        
        Args:
            chunks (List): List of chunk dictionaries
            
        Returns:
            Dictionary with chunk statistics
        """
        if not chunks:
            return {"total_chunks": 0, "avg_chunk_size": 0}
        
        total_chars = sum(len(chunk["content"]) for chunk in chunks)
        avg_chunk_size = total_chars // len(chunks) if chunks else 0
        
        return {
            "total_chunks": len(chunks),
            "total_characters": total_chars,
            "avg_chunk_size": avg_chunk_size
        }