import asyncio
import json
import logging
from abc import ABC, abstractmethod

import boto3
from botocore.config import Config
from langchain.embeddings import Embeddings
from langchain_aws import BedrockEmbeddings
from langchain_cohere import CohereEmbeddings
from langchain_openai import OpenAIEmbeddings

from catchup.configs.config import settings
from catchup.connectors.confluence.transformers import ConfluenceEmbedInput

logger = logging.getLogger(__name__)

class BaseEmbeddingService(ABC):
    def __init__(self):
        self.embedder: Embeddings = self._create_embedder()
    
    @abstractmethod
    def _create_embedder(self):
        pass
    
    def get_embedder(self) -> Embeddings:
        return self.embedder
    

class OpenAiEmbeddingService(BaseEmbeddingService):
    def _create_embedder(self):
        return OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY
        )
    
class CohereEmbeddingService(BaseEmbeddingService):
    def _create_embedder(self):
        return CohereEmbeddings(
            model=settings.COHERE_EMBEDDING_MODEL,
            api_key=settings.COHERE_API_KEY
        )
    
class AwsBedrockEmbeddingService(BaseEmbeddingService):
    MULTIMODAL_MAX_ITEMS = 96
    MULTIMODAL_MAX_PAYLOAD_BYTES = 19 * 1024 * 1024

    def __init__(self):
        self.client = self._create_client()
        self.model_id = settings.AWS_BEDROCK_EMBEDDING_MODEL
        super().__init__()

    def _create_client(self):
        config = Config(
            max_pool_connections=settings.EMBEDDING_MAX_CONCURRENCY * 2,
            retries={"max_attempts": 5, "mode": "standard"},
        )
        return boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_EMBEDDING_MODEL_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=config,
        )

    def _create_embedder(self):
        model_id = self.model_id
        provider = None
        if model_id.startswith("arn:"):
            provider = "cohere"
        
        return BedrockEmbeddings(
            model_id=model_id,
            provider=provider,
            client=self.client
        )

    async def embed_confluence_documents(
        self,
        inputs: list[ConfluenceEmbedInput],
    ) -> list[list[float] | None]:
        if not inputs:
            return []

        return await asyncio.to_thread(self._embed_confluence_documents_sync, inputs)

    def _embed_confluence_documents_sync(
        self,
        inputs: list[ConfluenceEmbedInput],
    ) -> list[list[float] | None]:
        embeddings: list[list[float] | None] = [None] * len(inputs)
        batch_inputs: list[dict] = []
        batch_indices: list[int] = []
        batch_payload_bytes = self._request_overhead_bytes()

        for index, embed_input in enumerate(inputs):
            request_input = embed_input.to_bedrock_input()
            input_payload_bytes = embed_input.payload_bytes()

            if input_payload_bytes > self.MULTIMODAL_MAX_PAYLOAD_BYTES:
                logger.warning(
                    "[CONFLUENCE][EMBED] Input payload exceeds multimodal limit: index=%s, size=%s",
                    index,
                    input_payload_bytes,
                )
                continue

            would_exceed_limit = (
                batch_inputs
                and (
                    len(batch_inputs) >= self.MULTIMODAL_MAX_ITEMS
                    or batch_payload_bytes + input_payload_bytes > self.MULTIMODAL_MAX_PAYLOAD_BYTES
                )
            )
            if would_exceed_limit:
                self._flush_multimodal_batch(batch_inputs, batch_indices, embeddings)
                batch_inputs = []
                batch_indices = []
                batch_payload_bytes = self._request_overhead_bytes()

            batch_inputs.append(request_input)
            batch_indices.append(index)
            batch_payload_bytes += input_payload_bytes

        if batch_inputs:
            self._flush_multimodal_batch(batch_inputs, batch_indices, embeddings)

        return embeddings

    def _flush_multimodal_batch(
        self,
        batch_inputs: list[dict],
        batch_indices: list[int],
        embeddings: list[list[float] | None],
    ) -> None:
        response = self.client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "inputs": batch_inputs,
                    "input_type": "search_document",
                    "embedding_types": ["float"],
                    "output_dimension": settings.PGVECTOR_EMBEDDING_DIMENSIONS,
                }
            ),
        )
        payload = json.loads(response["body"].read())
        batch_embeddings = payload.get("embeddings", [])
        if isinstance(batch_embeddings, dict):
            batch_embeddings = batch_embeddings.get("float", [])

        if len(batch_embeddings) != len(batch_indices):
            raise ValueError(
                "Unexpected Bedrock embedding response size: "
                f"expected={len(batch_indices)}, actual={len(batch_embeddings)}"
            )

        for index, embedding in zip(batch_indices, batch_embeddings, strict=True):
            embeddings[index] = embedding

    def _request_overhead_bytes(self) -> int:
        return len(
            json.dumps(
                {
                    "inputs": [],
                    "input_type": "search_document",
                    "embedding_types": ["float"],
                    "output_dimension": settings.PGVECTOR_EMBEDDING_DIMENSIONS,
                }
            ).encode("utf-8")
        )
