"""
Re-ranking implementation using HuggingFace Cross-Encoder models optimized for CPU.
"""

import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

# For HuggingFace model loading and inference
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    logging.warning("transformers or torch not available - re-ranking disabled")

from utils.device import get_best_device

logger = logging.getLogger(__name__)

@dataclass
class RerankedResult:
    """Data class to represent a re-ranked search result."""
    content: str
    score: float
    metadata: Dict[str, Any]
    original_rank: int

class CrossEncoderReranker:
    """
    A cross-encoder re-ranker for improving search result relevance.
    
    This implementation uses HuggingFace models optimized for CPU execution.
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", 
                 device: str = None):
        """
        Initialize the CrossEncoderReranker.
        
        Args:
            model_name (str): Name of the HuggingFace cross-encoder model
            device (str): Device to run inference on ('cpu', 'cuda', or 'dml')
        """
        self.model_name = model_name
        self.device = device
        
        # Initialize model and tokenizer
        self.tokenizer = None
        self.model = None
        
        if HF_AVAILABLE:
            try:
                # Determine the appropriate device using centralized utility
                if self.device is None:
                    self.device = get_best_device()
                elif isinstance(self.device, str):
                    self.device = torch.device(self.device)
                
                # Load tokenizer and model
                logger.info(f"Loading cross-encoder model: {model_name}")
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
                
                # Move model to device
                self.model.to(self.device)
                self.model.eval()  # Set to evaluation mode
                
                logger.info(f"Cross-encoder model loaded successfully on {self.device}")
                
            except Exception as e:
                logger.error(f"Error loading cross-encoder model: {str(e)}")
                self.tokenizer = None
                self.model = None
        else:
            logger.warning("HuggingFace transformers not available - re-ranking will be disabled")
    
    def rerank(self, query: str, results: List[RerankedResult], 
               top_k: int = 10) -> List[RerankedResult]:
        """
        Re-rank search results using cross-encoder scoring.
        
        Args:
            query (str): Search query
            results (List): List of SearchResult objects to re-rank
            top_k (int): Number of top results to return
            
        Returns:
            List of re-ranked SearchResult objects ordered by relevance score
        """
        if not self.model or not HF_AVAILABLE:
            logger.warning("Cross-encoder model not available - returning original results")
            # Return first top_k results in original order
            return results[:top_k]
        
        try:
            # Prepare pairs for cross-encoding (query + document content)
            pairs = [(query, result.content) for result in results]
            
            # Tokenize all pairs at once for efficiency
            encoded_pairs = self.tokenizer(
                pairs,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512  # Adjust as needed
            )
            
            # Move to device
            encoded_pairs = {k: v.to(self.device) for k, v in encoded_pairs.items()}
            
            # Get scores from cross-encoder
            with torch.no_grad():
                outputs = self.model(**encoded_pairs)
                scores = outputs.logits.squeeze(-1).cpu().numpy()
            
            # Combine results with scores and sort by score (descending)
            scored_results = []
            for i, result in enumerate(results):
                reranked_result = RerankedResult(
                    content=result.content,
                    score=float(scores[i]),
                    metadata=result.metadata,
                    original_rank=getattr(result, 'original_rank', i)
                )
                scored_results.append(reranked_result)
            
            # Sort by score (higher is better for cross-encoder)
            scored_results.sort(key=lambda x: x.score, reverse=True)
            
            # Return top k results
            final_results = scored_results[:top_k]
            
            logger.info(f"Re-ranked {len(results)} results with cross-encoder, returning top {len(final_results)}")
            return final_results
            
        except Exception as e:
            logger.error(f"Error in re-ranking: {str(e)}")
            # Return original results if re-ranking fails
            return results[:top_k]
    
    def batch_rerank(self, query: str, results: List[RerankedResult], 
                     top_k: int = 10) -> List[RerankedResult]:
        """
        Batch re-rank search results for better efficiency with large result sets.
        
        Args:
            query (str): Search query
            results (List): List of SearchResult objects to re-rank
            top_k (int): Number of top results to return
            
        Returns:
            List of re-ranked SearchResult objects ordered by relevance score
        """
        if not self.model or not HF_AVAILABLE:
            logger.warning("Cross-encoder model not available - returning original results")
            return results[:top_k]
        
        try:
            # Process in batches to manage memory usage
            batch_size = 16  # Adjust based on available memory
            all_reranked_results = []
            
            for i in range(0, len(results), batch_size):
                batch = results[i:i+batch_size]
                
                # Prepare pairs for this batch
                pairs = [(query, result.content) for result in batch]
                
                # Tokenize
                encoded_pairs = self.tokenizer(
                    pairs,
                    padding=True,
                    truncation=True,
                    return_tensors="pt",
                    max_length=512
                )
                
                # Move to device
                encoded_pairs = {k: v.to(self.device) for k, v in encoded_pairs.items()}
                
                # Get scores
                with torch.no_grad():
                    outputs = self.model(**encoded_pairs)
                    scores = outputs.logits.squeeze(-1).cpu().numpy()
                
                # Combine with scores
                batch_results = []
                for j, result in enumerate(batch):
                    reranked_result = RerankedResult(
                        content=result.content,
                        score=float(scores[j]),
                        metadata=result.metadata,
                        original_rank=getattr(result, 'original_rank', j)
                    )
                    batch_results.append(reranked_result)
                
                all_reranked_results.extend(batch_results)
            
            # Sort all results by score and return top k
            all_reranked_results.sort(key=lambda x: x.score, reverse=True)
            final_results = all_reranked_results[:top_k]
            
            logger.info(f"Batch re-ranked {len(results)} results with cross-encoder, returning top {len(final_results)}")
            return final_results
            
        except Exception as e:
            logger.error(f"Error in batch re-ranking: {str(e)}")
            # Return original results if re-ranking fails
            return results[:top_k]
    
    def get_reranker_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the re-ranker.
        
        Returns:
            Dictionary with re-ranker statistics
        """
        return {
            "model_name": self.model_name,
            "device": str(self.device),
            "available": HF_AVAILABLE
        }