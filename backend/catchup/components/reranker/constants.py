from enum import StrEnum


class RerankerProvider(StrEnum):
    COHERE = "cohere"
    AWS_BEDROCK = "aws-bedrock"