"""Build + load a FAISS index over the policy corpus.

The embedding model is `sentence-transformers/all-MiniLM-L6-v2` — small, fast,
no API key. For production swap in `OpenAIEmbeddings` or Bedrock Titan via the
`embeddings_provider` config knob.
"""

from __future__ import annotations

from pathlib import Path

from src.llm.corpus import load_corpus
from src.utils import ensure_dir, get_logger, project_path

log = get_logger(__name__)

DEFAULT_INDEX_DIR = project_path("data/policies/.faiss")


def _embeddings():
    # local import keeps the API process light when LLM features are off
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


def build_index(index_dir: Path = DEFAULT_INDEX_DIR) -> Path:
    from langchain_community.vectorstores import FAISS
    from langchain_text_splitters import MarkdownTextSplitter

    docs = [d.langchain_document() for d in load_corpus()]
    splitter = MarkdownTextSplitter(chunk_size=600, chunk_overlap=80)
    chunks = splitter.split_documents(docs)
    log.info("llm.vectorstore.build", n_docs=len(docs), n_chunks=len(chunks))

    store = FAISS.from_documents(chunks, _embeddings())
    ensure_dir(index_dir)
    store.save_local(str(index_dir))
    log.info("llm.vectorstore.saved", path=str(index_dir))
    return index_dir


def load_index(index_dir: Path = DEFAULT_INDEX_DIR):
    from langchain_community.vectorstores import FAISS

    return FAISS.load_local(
        str(index_dir),
        _embeddings(),
        allow_dangerous_deserialization=True,
    )
