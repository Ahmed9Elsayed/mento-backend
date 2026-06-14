from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from langchain_core.documents import Document

from components import has_available_pagefile
from prompts import HISTORY_AWARE_RETRIEVER_PROMPT, RAG_SYSTEM_PROMPT
from settings import Settings

try:
    from langsmith import traceable
except ImportError:

    def traceable(*args: Any, **kwargs: Any) -> Any:
        def decorator(func: Any) -> Any:
            return func

        return decorator


@dataclass
class RetrievedChunk:
    content: str
    source: str
    score: float | None = None
    metadata: dict[str, Any] | None = None


def _trace_retrieve_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    service = inputs.get("self")
    settings = getattr(service, "settings", None)
    return {
        "query": inputs.get("query"),
        "k": inputs.get("k"),
        "collection": getattr(settings, "qdrant_collection", None),
        "embedding_model": getattr(settings, "embedding_model", None),
    }


def _trace_retrieve_outputs(
    outputs: list[RetrievedChunk] | None,
) -> list[dict[str, Any]] | None:
    if outputs is None:
        return None
    traced_chunks = []
    for chunk in outputs:
        traced_chunks.append(
            {
                "content_preview": chunk.content,
                "content_length": len(chunk.content),
                "source": chunk.source,
                "score": chunk.score,
                "metadata": chunk.metadata or {},
            }
        )
    return traced_chunks


class RAGService:
    def __init__(self, settings: Settings, llm: Any):
        self.settings = settings
        self.llm = llm
        self._embeddings: Any | None = None
        self._client: Any | None = None
        self._vector_store: Any | None = None
        self._chain: Any | None = None
        self.index_metadata_path = settings.base_dir / "index_metadata.json"

    @property
    def embeddings(self) -> Any:
        if self._embeddings is None:
            if not has_available_pagefile(self.settings.min_embedding_pagefile_mb):
                raise MemoryError(
                    "Available Windows pagefile is too low to load the embedding model safely."
                )
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
            except ImportError:
                from langchain_community.embeddings import \
                    HuggingFaceEmbeddings

            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.settings.embedding_model
            )
        return self._embeddings

    @property
    def client(self) -> Any:
        if self._client is None:
            from qdrant_client import QdrantClient

            if not self.settings.qdrant_url:
                raise RuntimeError("QDRANT_URL is missing in Module 4/.env")
            self._client = QdrantClient(
                url=self.settings.qdrant_url,
                api_key=self.settings.qdrant_api_key or None,
                prefer_grpc=False,
            )
        return self._client

    @property
    def vector_store(self) -> Any:
        if self._vector_store is None:
            from langchain_qdrant import QdrantVectorStore

            kwargs: dict[str, Any] = {
                "client": self.client,
                "collection_name": self.settings.qdrant_collection,
                "embedding": self.embeddings,
            }
            if self.settings.qdrant_vector_name:
                kwargs["vector_name"] = self.settings.qdrant_vector_name
            self._vector_store = QdrantVectorStore(**kwargs)
        return self._vector_store

    @property
    def retriever(self) -> Any:
        self.ensure_index()
        return self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.settings.retriever_k},
        )

    @property
    def chain(self) -> Any:
        if self._chain is None:
            try:
                from langchain.chains import (create_history_aware_retriever,
                                              create_retrieval_chain)
                from langchain.chains.combine_documents import \
                    create_stuff_documents_chain
            except ModuleNotFoundError:
                from langchain_classic.chains import (
                    create_history_aware_retriever,
                    create_retrieval_chain,
                )
                from langchain_classic.chains.combine_documents import (
                    create_stuff_documents_chain,
                )
            from langchain_core.prompts import (ChatPromptTemplate,
                                                MessagesPlaceholder)

            contextualize_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", HISTORY_AWARE_RETRIEVER_PROMPT),
                    MessagesPlaceholder("chat_history"),
                    ("human", "{input}"),
                ]
            )
            history_aware_retriever = create_history_aware_retriever(
                self.llm,
                self.retriever,
                contextualize_prompt,
            )

            qa_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", RAG_SYSTEM_PROMPT),
                    MessagesPlaceholder("chat_history"),
                    ("human", "{input}"),
                ]
            )
            document_chain = create_stuff_documents_chain(self.llm, qa_prompt)
            self._chain = create_retrieval_chain(
                history_aware_retriever, document_chain
            )
        return self._chain

    def ensure_index(self) -> dict[str, Any]:
        if self.settings.force_rebuild_index:
            self.rebuild_index()
        elif not self.collection_exists() or self.collection_count() == 0:
            self.rebuild_index()

        return {
            "collection": self.settings.qdrant_collection,
            "points": self.collection_count(),
            "embedding_model": self.settings.embedding_model,
        }

    def collection_exists(self) -> bool:
        try:
            self.client.get_collection(self.settings.qdrant_collection)
            return True
        except Exception:
            return False

    def collection_count(self) -> int:
        if not self.collection_exists():
            return 0
        result = self.client.count(self.settings.qdrant_collection, exact=True)
        return int(getattr(result, "count", 0))

    def rebuild_index(self) -> dict[str, Any]:
        from qdrant_client import models

        if self.collection_exists():
            self.client.delete_collection(self.settings.qdrant_collection)

        vector_size = len(self.embeddings.embed_query("Mento vector size probe"))
        vectors_config: Any = models.VectorParams(
            size=vector_size, distance=models.Distance.COSINE
        )
        if self.settings.qdrant_vector_name:
            vectors_config = {
                self.settings.qdrant_vector_name: models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                )
            }

        self.client.create_collection(
            collection_name=self.settings.qdrant_collection,
            vectors_config=vectors_config,
        )

        documents = list(self.load_and_chunk_dataset())
        self.vector_store.add_documents(documents)

        metadata = {
            "dataset": self.settings.dataset_name,
            "split": self.settings.dataset_split,
            "embedding_model": self.settings.embedding_model,
            "chunk_size": self.settings.chunk_size,
            "chunk_overlap": self.settings.chunk_overlap,
            "document_chunks": len(documents),
            "collection": self.settings.qdrant_collection,
        }
        self.index_metadata_path.write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        return metadata

    def load_and_chunk_dataset(self) -> Iterable[Document]:
        from datasets import load_dataset
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        dataset_dict = load_dataset(self.settings.dataset_name)
        split_name = self.settings.dataset_split
        if split_name not in dataset_dict:
            split_name = next(iter(dataset_dict.keys()))
        dataset = dataset_dict[split_name]

        columns = list(dataset.column_names)
        context_column = self._choose_column(
            columns,
            ["Context", "context", "question", "Question", "input", "text", "prompt"],
        )
        response_column = self._choose_column(
            columns,
            ["Response", "response", "answer", "Answer", "output", "completion"],
        )

        rows_limit = (
            self.settings.max_dataset_rows
            if self.settings.max_dataset_rows > 0
            else len(dataset)
        )
        raw_documents: list[Document] = []
        for idx, row in enumerate(dataset):
            if idx >= rows_limit:
                break

            context = str(row.get(context_column, "")).strip() if context_column else ""
            response = (
                str(row.get(response_column, "")).strip() if response_column else ""
            )
            if not context and not response:
                continue

            page_content = (
                f"Client concern:\n{context}\n\nCounselor response:\n{response}".strip()
            )
            raw_documents.append(
                Document(
                    page_content=page_content,
                    metadata={
                        "source": self.settings.dataset_name,
                        "split": split_name,
                        "row": idx,
                        "context_column": context_column,
                        "response_column": response_column,
                    },
                )
            )

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return splitter.split_documents(raw_documents)

    @staticmethod
    def _choose_column(columns: list[str], candidates: list[str]) -> str | None:
        exact = {column: column for column in columns}
        lowered = {column.lower(): column for column in columns}
        for candidate in candidates:
            if candidate in exact:
                return exact[candidate]
            if candidate.lower() in lowered:
                return lowered[candidate.lower()]
        return None

    @traceable(
        run_type="retriever",
        name="Mento.retrieve_chunks",
        tags=["mento", "rag", "chunks"],
        process_inputs=_trace_retrieve_inputs,
        process_outputs=_trace_retrieve_outputs,
    )
    def retrieve_chunks(self, query: str, k: int | None = None) -> list[RetrievedChunk]:
        self.ensure_index()
        k = k or self.settings.retriever_k
        docs_and_scores = self.vector_store.similarity_search_with_score(query, k=k)
        chunks: list[RetrievedChunk] = []
        for document, score in docs_and_scores:
            metadata = dict(document.metadata or {})
            source = str(metadata.get("source", self.settings.dataset_name))
            row = metadata.get("row")
            if row is not None:
                source = f"{source} row {row}"
            chunks.append(
                RetrievedChunk(
                    content=document.page_content,
                    source=source,
                    score=float(score) if score is not None else None,
                    metadata=metadata,
                )
            )
        return chunks

    def metadata(self) -> dict[str, Any]:
        metadata = {
            "collection": self.settings.qdrant_collection,
            "points": self.collection_count(),
            "embedding_model": self.settings.embedding_model,
            "dataset": self.settings.dataset_name,
        }
        if self.index_metadata_path.exists():
            try:
                metadata["last_build"] = json.loads(
                    self.index_metadata_path.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError:
                pass
        return metadata
