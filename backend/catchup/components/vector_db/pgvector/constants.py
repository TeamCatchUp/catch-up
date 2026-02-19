from enum import StrEnum


class VectorDbProvider(StrEnum):
    MEILISEARCH = "meilisearch"
    PGVECTOR = "pgvector"
