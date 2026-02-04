from abc import ABC, abstractmethod
from enum import StrEnum
from langchain_core.messages import trim_messages
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock

from catchup.configs.config import settings

class LlmProvider(StrEnum):
    OPENAI = "openai"
    AWS_BEDROCK = "aws-bedrock"


class BaseLlmService(ABC):
    def __init__(self):
        self.llm: BaseChatModel = self._create_llm()
        self.trimmer = self._create_trimmer()
        
    @abstractmethod
    def _create_llm(self) -> BaseChatModel:
        pass
    
    def _create_trimmer(self):
        # 대화 히스토리 관련 토큰 제한
        self.trimmer = trim_messages(
            max_tokens=2000,  # 토큰 제한
            strategy="last",  # 최신 부분만 남김
            token_counter=self.llm,  # 토큰 계산기
            include_system=True,  # 시스템 메세지 포함
            allow_partial=False,  # 메세지 단위로 깔끔하게 자름
            start_on="human",  # 대화의 시작은 항상 사람 질문
        )
    
    def get_llm(self) -> BaseChatModel:
        return self.llm
    
    def get_trimmer(self):
        return self.trimmer
    

class OpenAiLlmService(BaseLlmService):
    def _create_llm(self) -> BaseChatModel:
        return ChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0,
        )


class AwsBedrockLlmService(BaseLlmService):
    def _create_llm(self) -> BaseChatModel:
        return ChatBedrock(
            model=settings.AWS_BEDROCK_MODEL,
            region=settings.AWS_BEDROCK_REGION,
            temperature=0,
        )