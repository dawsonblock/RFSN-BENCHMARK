"""Lightweight embeddings for failure similarity matching."""
from __future__ import annotations
import re
import math
from typing import List


def _tokens(text: str) -> List[str]:
    """Extract tokens from text for hashing."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    toks = [t for t in text.split() if t and len(t) > 2]
    return toks[:2000]


def hash_embed(text: str, dim: int = 2048) -> List[float]:
    """
    Deterministic hashed bag-of-words with log scaling.
    
    No external dependencies (numpy, sklearn, etc.).
    Returns a dense python list of floats.
    
    Args:
        text: Input text to embed
        dim: Embedding dimension
        
    Returns:
        L2-normalized embedding vector
    """
    v = [0.0] * dim
    for tok in _tokens(text):
        h = hash(tok) % dim
        v[h] += 1.0
    
    # Log scaling + L2 normalize
    norm = 0.0
    for i, x in enumerate(v):
        if x > 0:
            x = 1.0 + math.log(x)
            v[i] = x
            norm += x * x
    
    norm = math.sqrt(norm) if norm > 0 else 1.0
    return [x / norm for x in v]


def cosine(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    return sum(x * y for x, y in zip(a, b))


def batch_cosine(query: List[float], vectors: List[List[float]]) -> List[float]:
    """Compute cosine similarity between query and multiple vectors."""
    return [cosine(query, v) for v in vectors]
