import os
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

try:
    from .config import RAGConfig, default_config, CHROMA_PERSIST_DIR
    from .loader import Document, load_all_documents
except ImportError:
    from engine.config import RAGConfig, default_config, CHROMA_PERSIST_DIR
    from engine.loader import Document, load_all_documents

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

STOPWORDS = {
    "what", "is", "the", "for", "in", "at", "was", "and", "or", "to", "a",
    "an", "of", "my", "if", "can", "tell", "me", "this", "that", "which",
    "do", "does", "did", "with", "from", "by", "as", "about", "there", "give"
}

GENERIC_TERMS = {
    "medical", "college", "institute", "hospital", "cut-off", "cutoff",
    "closing", "opening", "rank", "ranks", "neet", "ug", "admission",
    "quota", "seat", "course", "fee", "tuition", "annual", "round",
    "government", "state", "under"
}


class VectorStoreManager:
    def __init__(self, config: RAGConfig = default_config):
        self.config = config
        self.collection_name = "neet_counsel_records"
        self.client = None
        self.collection = None
        self.embedding_fn = None
        self.fallback_docs: List[Document] = []
        self._init_backend()

    def _init_backend(self):
        if not CHROMA_AVAILABLE:
            return

        try:
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.config.embedding_model_name,
                device=self.config.device
            )
        except Exception:
            self.embedding_fn = None

        self.client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))

    def build_or_load_index(self, data_dir: Path, force_rebuild: bool = False) -> int:
        docs = load_all_documents(data_dir)
        self.fallback_docs = docs

        if not CHROMA_AVAILABLE:
            return len(docs)

        if force_rebuild:
            try:
                self.client.delete_collection(name=self.collection_name)
            except Exception:
                pass

        try:
            self.collection = self.client.get_collection(
                name=self.collection_name,
                embedding_function=self.embedding_fn
            )
            count = self.collection.count()
            if count > 0 and not force_rebuild:
                return count
        except Exception:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"}
            )

        ids = [doc.doc_id for doc in docs]
        contents = [doc.page_content for doc in docs]
        metadatas = [doc.metadata for doc in docs]

        batch_size = 50
        for i in range(0, len(ids), batch_size):
            self.collection.upsert(
                ids=ids[i:i + batch_size],
                documents=contents[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size]
            )

        return self.collection.count()

    def query(self, query_text: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        k = top_k or self.config.top_k
        results: List[Dict[str, Any]] = []

        if CHROMA_AVAILABLE and self.collection is not None and self.collection.count() > 0:
            query_res = self.collection.query(
                query_texts=[query_text],
                n_results=k
            )

            docs = query_res.get("documents", [[]])[0]
            metas = query_res.get("metadatas", [[]])[0]
            dists = query_res.get("distances", [[]])[0] if query_res.get("distances") else [0.0] * len(docs)

            for doc_text, meta, dist in zip(docs, metas, dists):
                results.append({
                    "content": doc_text,
                    "metadata": meta,
                    "distance": float(dist),
                    "is_supported": float(dist) <= self.config.max_cosine_distance
                })
            return results

        raw_tokens = re.findall(r"\b[a-z0-9_-]+\b", query_text.lower())
        q_terms = [t for t in raw_tokens if t not in STOPWORDS and len(t) > 1]
        if not q_terms:
            return results

        distinctive = [t for t in q_terms if t not in GENERIC_TERMS and t not in {"st", "sc", "obc", "ews", "ur", "open"}]

        scored: List[Tuple[int, Document]] = []
        for d in self.fallback_docs:
            doc_tokens = set(re.findall(r"\b[a-z0-9_-]+\b", d.page_content.lower()))

            if distinctive:
                matched_distinctive = [t for t in distinctive if t in doc_tokens]
                if len(matched_distinctive) < min(len(distinctive), 1):
                    continue
                distinctive_ratio = len(matched_distinctive) / len(distinctive)
                if distinctive_ratio < 0.5:
                    continue
                score = len(matched_distinctive) * 4 + sum(1 for t in q_terms if t in doc_tokens)
            else:
                score = sum(1 for t in q_terms if t in doc_tokens)

            if score >= 3:
                scored.append((score, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        for score, d in scored[:k]:
            results.append({
                "content": d.page_content,
                "metadata": d.metadata,
                "distance": 0.2 if score >= 6 else 0.4,
                "is_supported": True
            })

        return results
