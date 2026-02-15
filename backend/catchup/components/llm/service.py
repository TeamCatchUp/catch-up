from abc import ABC, abstractmethod
from langchain_core.messages import trim_messages
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock

from catchup.components.llm.constants import ModelCapacity
from catchup.configs.config import settings

class BaseLlmService(ABC):
    def __init__(
        self,
        model_capacity: ModelCapacity
    ):
        self.model_capacity = model_capacity
        self.llm: BaseChatModel = self._create_llm()
        self.trimmer = self._create_trimmer()
        
    @abstractmethod
    def _create_llm(self) -> BaseChatModel:
        pass
    
    def _create_trimmer(self):
        # 대화 히스토리 관련 토큰 제한
        trimmer = trim_messages(
            max_tokens=2000,  # 토큰 제한
            strategy="last",  # 최신 부분만 남김
            token_counter=self.llm,  # 토큰 계산기
            include_system=True,  # 시스템 메세지 포함
            allow_partial=False,  # 메세지 단위로 깔끔하게 자름
            start_on="human",  # 대화의 시작은 항상 사람 질문
        )
        return trimmer
    
    def get_llm(self) -> BaseChatModel:
        return self.llm
    
    def get_trimmer(self):
        return self.trimmer
    
    def get_trimmed_llm(self):
        """Trimmer와 LLM이 결합된 Runnable 반환"""
        return self.trimmer | self.llm
    

class OpenAiLlmService(BaseLlmService):
    def _create_llm(self) -> BaseChatModel:
        
        model_name = (
            settings.OPENAI_SMALL_MODEL
            if self.model_capacity == ModelCapacity.SMALL
            else settings.OPENAI_LARGE_MODEL
        )
        
        return ChatOpenAI(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
            temperature=0,
            streaming=True
        )


class AwsBedrockLlmService(BaseLlmService):
    def _create_llm(self) -> BaseChatModel:
        
        model_id = (
            settings.AWS_BEDROCK_SMALL_MODEL
            if self.model_capacity == ModelCapacity.SMALL
            else settings.AWS_BEDROCK_LARGE_MODEL
        )
        
        return ChatBedrock(
            model_id=model_id,
            region_name=settings.AWS_REGION,
            aws_access_key_id=None,
            aws_secret_access_key=None,
            temperature=0,
            max_tokens=4096,
            streaming=True
        )