from pathlib import WindowsPath
from re import sub
from llama_index import (
    ServiceContext,
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    global_service_context,
)
import llama_index
from llama_index import query_engine
from llama_index.embeddings import HuggingFaceEmbedding
from llama_index.embeddings.base import similarity
from llama_index.schema import TextNode, MetadataMode
from llama_index.retrievers import BaseRetriever
from llama_index.query_engine import (
    ToolRetrieverRouterQueryEngine,
    RetrieverQueryEngine,
)
from llama_index.vector_stores import MilvusVectorStore
from llama_index.readers import SimpleDirectoryReader
from llama_index.node_parser import SentenceWindowNodeParser, SentenceSplitter
from llama_index.postprocessor import (
    SimilarityPostprocessor,
    MetadataReplacementPostProcessor,
)
from llama_index.tools.query_engine import QueryEngineTool
from llama_index.extractors import (
    SummaryExtractor,
    QuestionsAnsweredExtractor,
    TitleExtractor,
    KeywordExtractor,
    EntityExtractor,
    BaseExtractor,
)
from milvus import default_server

import os
from typing import List, Dict, Any, Optional


from common import DATA_PATH, EMBEDDING_DIM, EMBEDDING_MODEL, subjects, PathSep, debug


class AugmentedIngestPipeline:
    def __init__(
        self, data_dir_path: str, service_context: ServiceContext, create=True
    ) -> None:
        self.data_dir = data_dir_path
        self.service_ctx = service_context
        self.embed_model = self.service_ctx.embed_model
        self.vector_indexes = {}
        self.metadata_fn = lambda x: {"title": x.replace("_", " ")}
        self.node_parser = SentenceWindowNodeParser.from_defaults(
            window_size=3,
            window_metadata_key="window",
            original_text_metadata_key="og_text",
            include_metadata=True,
        )
        self.create = create

    def _load_data(self, path):
        docs = SimpleDirectoryReader(path, file_metadata=self.metadata_fn).load_data()

        return docs

    def _make_nodes(self, docs):
        nodes = self.node_parser.get_nodes_from_documents(docs, show_progress=debug)
        return nodes

    def _insert_into_vectorstore(self, subject, nodes, create=False):
        collection_name = f"augmentED_{subject}"
        self.vector_store = MilvusVectorStore(
            dim=EMBEDDING_DIM,
            host=default_server.server_address,
            port=default_server.listen_port,
            collection_name=collection_name,
            overwrite=create,
        )
        storage_ctx = StorageContext.from_defaults(vector_store=self.vector_store)
        self.vector_indexes[subject] = VectorStoreIndex(
            nodes=nodes,
            service_context=self.service_ctx,
            storage_context=storage_ctx,
        )

    def _get_subject_query_engine(self, subject) -> Dict:
        query_engine = self.vector_indexes[subject].as_query_engine(
            similarity_top_k=3,
            node_postprocessors=[
                MetadataReplacementPostProcessor(target_metadata_key="window")
            ],
        )
        return query_engine

    def run_pipeline(self):
        self.one_giant_index_nodes = []
        for subject in subjects:
            path = self.data_dir + PathSep + subjects[subject]
            docs = self._load_data(path)
            nodes = self._make_nodes(docs)
            self._insert_into_vectorstore(subject, nodes)
            self.one_giant_index_nodes.extend(nodes)

        self._insert_into_vectorstore("OGI", self.one_giant_index_nodes, create=False)
        self.one_giant_index = self.vector_indexes["OGI"]

    def get_indices_as_tools(self):
        tools = []
        for subject in self.vector_indexes:
            vector_tool = QueryEngineTool.from_defaults(
                query_engine=self.vector_indexes[subject].as_query_engine(
                    similarity_top_k=2,
                    node_postprocessors=[
                        MetadataReplacementPostProcessor(target_metadata_key="window")
                    ],
                ),
                description=f"Useful for retrieving specific context for solving questions related to the {subject}",
            )
            tools.append(vector_tool)
        return tools

    def search_one_giant_index(
        self,
        query,
        top_k=10,
        replace_with_meta=True,
        metadata_key="title",
    ):
        retr = self.one_giant_index.as_retriever(
            similarity_top_k=top_k,
        )
        answers = retr.retrieve(query)
        if replace_with_meta:
            return list(set(map(lambda x: x.metadata[metadata_key], answers)))
        else:
            return list(
                map(lambda x: x.get_content(metadata_mode=MetadataMode.LLM), answers)
            )

    def index_one_doc(self, file_path: str):
        doc = (
            SimpleDirectoryReader(
                input_files=[file_path],
                filename_as_id=True,
            ).load_data(),
        )
        nodes = self._make_nodes(doc[0])

        self._insert_into_vectorstore("user_doc", nodes)

        return self.vector_indexes["user_doc"]


if __name__ == "__main__":
    default_server.start()
    print(os.getcwd())
    pipe = AugmentedIngestPipeline(
        DATA_PATH,
        service_context=ServiceContext.from_defaults(
            llm=None, embed_model=HuggingFaceEmbedding(EMBEDDING_MODEL)
        ),
    )
    pipe.run_pipeline()
    pipe.search_one_giant_index("depr")
    default_server.stop()
