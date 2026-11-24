"""Local retrieval-augmented research notes with transparent source excerpts.

The default retriever is TF-IDF (no model download or external API). Optional
SentenceTransformers can be added later without changing the store contract.
"""
from __future__ import annotations
from contextlib import contextmanager
import json, os, re, sqlite3, uuid
from pathlib import Path
from typing import Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_EMBEDDING_MODELS = {}

class ResearchRAG:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path=Path(db_path or os.getenv("DATAPILOT_RESEARCH_DB", "research_knowledge.sqlite3"))
        self.db_path.parent.mkdir(parents=True,exist_ok=True)
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT, doi TEXT, section TEXT, chunk TEXT NOT NULL, embedding TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            columns = {row[1] for row in db.execute("PRAGMA table_info(chunks)").fetchall()}
            if "embedding" not in columns: db.execute("ALTER TABLE chunks ADD COLUMN embedding TEXT")
    @contextmanager
    def _db(self):
        db=sqlite3.connect(self.db_path)
        db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    @staticmethod
    def _chunks(text: str, size: int=1100, overlap: int=150):
        clean=re.sub(r"\s+"," ",text).strip()
        if not clean: return []
        chunks=[]; start=0
        while start<len(clean):
            end=min(len(clean),start+size); chunks.append(clean[start:end])
            if end==len(clean): break
            start=max(start+1,end-overlap)
        return chunks
    def _embed(self, texts: list[str]):
        if os.getenv("DATAPILOT_ENABLE_RESEARCH_EMBEDDINGS", "false").lower() not in {"1", "true", "yes"}: return None
        from sentence_transformers import SentenceTransformer
        model_name=os.getenv("DATAPILOT_RESEARCH_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        if model_name not in _EMBEDDING_MODELS: _EMBEDDING_MODELS[model_name]=SentenceTransformer(model_name)
        return _EMBEDDING_MODELS[model_name].encode(texts, normalize_embeddings=True).tolist()
    def index_text(self,title: str,text: str,source: str="user-provided text",doi: str="") -> dict[str,Any]:
        if not title.strip() or len(text.strip())<80: raise ValueError("Provide a title and at least 80 characters of source text.")
        chunks=self._chunks(text)
        try: embeddings=self._embed(chunks)
        except Exception: embeddings=None
        with self._db() as db:
            for i,chunk in enumerate(chunks): db.execute("INSERT INTO chunks(id,title,source,doi,section,chunk,embedding) VALUES(?,?,?,?,?,?,?)",(str(uuid.uuid4()),title[:300],source[:1000],doi[:200],f"Chunk {i+1}",chunk,json.dumps(embeddings[i]) if embeddings else None))
        return {"status":"indexed","title":title,"chunks_added":len(chunks),"retrieval":"sentence-transformers embeddings" if embeddings else "TF-IDF cosine similarity","source":source,"doi":doi or None}
    def status(self) -> dict[str,Any]:
        with self._db() as db:
            count=db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            docs=db.execute("SELECT COUNT(DISTINCT title) FROM chunks").fetchone()[0]
        embedding_enabled=os.getenv("DATAPILOT_ENABLE_RESEARCH_EMBEDDINGS", "false").lower() in {"1", "true", "yes"}
        return {"indexed_chunks":int(count),"indexed_documents":int(docs),"retriever":"Sentence Transformers embeddings (when installed) with TF-IDF fallback" if embedding_enabled else "TF-IDF cosine similarity","generation":"retrieval-only; no unsupported answer generation"}
    def search(self,query: str,k: int=4) -> list[dict[str,Any]]:
        if not query.strip(): return []
        with self._db() as db: rows=[dict(r) for r in db.execute("SELECT * FROM chunks ORDER BY created_at DESC").fetchall()]
        if not rows: return []
        docs=[r["chunk"] for r in rows]
        scores=None
        if os.getenv("DATAPILOT_ENABLE_RESEARCH_EMBEDDINGS", "false").lower() in {"1", "true", "yes"}:
            try:
                import numpy as np
                query_vector=np.asarray(self._embed([query])[0])
                doc_vectors=[json.loads(row["embedding"]) if row.get("embedding") else None for row in rows]
                missing=[i for i,value in enumerate(doc_vectors) if value is None]
                if missing:
                    computed=self._embed([docs[i] for i in missing])
                    for index,vector in zip(missing,computed): doc_vectors[index]=vector
                scores=np.asarray(doc_vectors,dtype=float) @ query_vector
            except Exception: scores=None
        if scores is None:
            vectorizer=TfidfVectorizer(stop_words="english",ngram_range=(1,2),max_features=30000)
            try:
                matrix=vectorizer.fit_transform(docs+[query]); scores=cosine_similarity(matrix[-1],matrix[:-1]).ravel()
            except ValueError:
                scores=[0.0 for _ in docs]
        indices=scores.argsort()[::-1][:max(1,min(k,10))]
        return [{"title":rows[i]["title"],"source":rows[i]["source"],"doi":rows[i]["doi"],"section":rows[i]["section"],"excerpt":rows[i]["chunk"],"relevance":round(float(scores[i]),4)} for i in indices if scores[i]>0]
    def answer_context(self,query: str,k: int=4) -> dict[str,Any]:
        hits=self.search(query,k)
        return {"query":query,"mode":"retrieval_only" if hits else "no_evidence","answer_policy":"No generated factual answer is returned; use these excerpts as grounded context and cite their source metadata.","sources":hits}


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract text from an uploaded research PDF using optional PyMuPDF."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PDF text extraction requires PyMuPDF. Install it with pip install pymupdf.") from exc
    document=fitz.open(stream=pdf_bytes,filetype="pdf")
    try:
        pages=[page.get_text("text") for page in document]
        return "\n\n".join(pages), len(pages)
    finally:
        document.close()
