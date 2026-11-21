import time
import math
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

STOPWORDS = {
    "what", "was", "the", "for", "in", "of", "category", "is", "a",
    "an", "to", "how", "much", "and", "or", "tell", "me", "give", "there"
}

SYNONYMS = {
    "ur": "open",
    "general": "open",
    "cut-off": "closing",
    "cutoff": "closing",
    "fee": "fees",
    "structure": "fees",
    "sskm": "ipgmer"
}


@dataclass
class CacheEntry:
    query: str
    embedding: List[float]
    response: Dict[str, Any]
    created_at: float
    last_accessed: float
    hit_count: int = 0


class SemanticCache:
    def __init__(
        self,
        similarity_threshold: float = 0.72,
        max_entries: int = 1000,
        ttl_seconds: int = 86400,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.model_name = model_name
        self.entries: List[CacheEntry] = []
        self.model = None
        self.total_queries = 0
        self.hits = 0
        self.misses = 0
        self.total_latency_saved_ms = 0.0
        self._init_encoder()

    def _init_encoder(self):
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.model = SentenceTransformer(self.model_name)
            except Exception:
                self.model = None

    def _encode(self, text: str) -> List[float]:
        if self.model is not None and NUMPY_AVAILABLE:
            emb = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            return emb.tolist()

        clean_text = text.lower().replace("?", " ").replace(",", " ").replace(".", " ").replace("-", " ").replace("_", " ")
        raw_words = re.findall(r"[a-z0-9]+", clean_text)
        tokens = [SYNONYMS.get(w, w) for w in raw_words if w not in STOPWORDS]

        ngrams = []
        for t in tokens:
            ngrams.append(t)
            if len(t) >= 3:
                for i in range(len(t) - 2):
                    ngrams.append(t[i:i + 3])

        dim = 256
        vec = [0.0] * dim
        for g in ngrams:
            h = abs(hash(g)) % dim
            vec[h] += 1.0

        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def _purge_expired(self):
        now = time.time()
        self.entries = [
            e for e in self.entries
            if (now - e.created_at) < self.ttl_seconds
        ]

    def lookup(self, query: str) -> Tuple[Optional[Dict[str, Any]], float]:
        self.total_queries += 1
        self._purge_expired()

        if not self.entries:
            self.misses += 1
            return None, 0.0

        q_clean = query.strip().lower()
        for entry in self.entries:
            if entry.query.strip().lower() == q_clean:
                self.hits += 1
                entry.hit_count += 1
                entry.last_accessed = time.time()
                est_saved = 450.0
                self.total_latency_saved_ms += est_saved
                return entry.response, 1.0

        q_vec = self._encode(query)
        best_entry = None
        best_sim = -1.0

        for entry in self.entries:
            sim = self._cosine_similarity(q_vec, entry.embedding)
            if sim > best_sim:
                best_sim = sim
                best_entry = entry

        if best_entry and best_sim >= self.similarity_threshold:
            self.hits += 1
            best_entry.hit_count += 1
            best_entry.last_accessed = time.time()
            est_saved = 450.0
            self.total_latency_saved_ms += est_saved
            return best_entry.response, best_sim

        self.misses += 1
        return None, max(best_sim, 0.0)

    def store(self, query: str, response: Dict[str, Any]):
        self._purge_expired()

        if len(self.entries) >= self.max_entries:
            self.entries.sort(key=lambda e: e.last_accessed)
            self.entries.pop(0)

        q_vec = self._encode(query)
        now = time.time()
        new_entry = CacheEntry(
            query=query,
            embedding=q_vec,
            response=response,
            created_at=now,
            last_accessed=now,
            hit_count=0
        )
        self.entries.append(new_entry)

    def get_telemetry(self) -> Dict[str, Any]:
        hit_rate = (self.hits / self.total_queries * 100.0) if self.total_queries > 0 else 0.0
        return {
            "total_queries": self.total_queries,
            "cache_hits": self.hits,
            "cache_misses": self.misses,
            "hit_rate_pct": round(hit_rate, 2),
            "cached_entries_count": len(self.entries),
            "total_latency_saved_ms": round(self.total_latency_saved_ms, 2)
        }
