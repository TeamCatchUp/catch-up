from enum import StrEnum


class LlmProvider(StrEnum):
    OPENAI = "openai"
    AWS_BEDROCK = "aws-bedrock"
    

class ModelCapacity(StrEnum):
    SMALL = "small"
    LARGE = "large"