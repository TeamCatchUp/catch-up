from enum import StrEnum


class EmbeddingProvider(StrEnum):
    OPENAI = "openai"
    COHERE = "cohere"
    AWS_BEDROCK = "aws-bedrock"