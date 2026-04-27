from abc import ABC
from abc import abstractmethod

from botocore.config import Config
from langchain_aws import ChatBedrock
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import trim_messages
from langchain_openai import ChatOpenAI

from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.isolated_chat_bedrock import IsolatedChatBedrock
from catchup.configs.config import settings


class BaseLlmService(ABC):
    def __init__(
        self,
        model_capacity: ModelCapacity,
        streaming: bool = True
    ):
        self.model_capacity = model_capacity
        self.llm: BaseChatModel = self._create_llm(streaming)
        self.trimmer = self._create_trimmer()
        
    @abstractmethod
    def _create_llm(
        self,
        streaming: bool
    ) -> BaseChatModel:
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
    def _create_llm(
            self,
            streaming: bool
        ) -> BaseChatModel:
        
        model_name = (
            settings.OPENAI_SMALL_MODEL
            if self.model_capacity == ModelCapacity.SMALL
            else settings.OPENAI_LARGE_MODEL
        )
        
        return ChatOpenAI(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
            temperature=0,
            streaming=streaming
        )


class AwsBedrockLlmService(BaseLlmService):
    def __init__(
        self,
        model_capacity: ModelCapacity,
        streaming: bool = True,
        isolated: bool = False,
        extended_thinking: bool = False,
        thinking_budget_tokens: int = 8000,
    ):
        # isolated=True면 rag_executors.llm_executor 전용 pool 사용 (chat 파이프라인용)
        # isolated=False면 default pool 사용 (ingestion 등 일반 용도)
        self._isolated = isolated
        self._extended_thinking = extended_thinking
        self._thinking_budget_tokens = thinking_budget_tokens
        super().__init__(model_capacity, streaming)

    def _create_llm(
            self,
            streaming: bool
        ) -> BaseChatModel:

        model_id = (
            settings.AWS_BEDROCK_SMALL_MODEL
            if self.model_capacity == ModelCapacity.SMALL
            else settings.AWS_BEDROCK_LARGE_MODEL
        )

        provider = None
        if model_id.startswith("arn:"):
            provider = "anthropic"

        config = Config(
            max_pool_connections=200,
            retries={"max_attempts": 5, "mode": "adaptive"},
        )

        # Extended thinking은 Claude 3.7 Sonnet 이상에서만 지원.
        # temperature=1 필수 (AWS Bedrock 요구사항).
        # streaming=False 권장 (thinking 토큰을 사용자에게 노출하지 않음).
        if self._extended_thinking:
            return ChatBedrock(
                model_id=model_id,
                provider=provider,
                region_name=settings.AWS_REGION,
                credentials_profile_name=settings.AWS_CREDENTIALS_PROFILE_NAME,
                temperature=1,
                max_tokens=self._thinking_budget_tokens + 4096,
                streaming=False,
                config=config,
                model_kwargs={
                    "thinking": {
                        "type": "enabled",
                        "budget_tokens": self._thinking_budget_tokens,
                    }
                },
            )

        cls = IsolatedChatBedrock if self._isolated else ChatBedrock
        return cls(
            model_id=model_id,
            provider=provider,
            region_name=settings.AWS_REGION,
            credentials_profile_name=settings.AWS_CREDENTIALS_PROFILE_NAME,
            temperature=0,
            max_tokens=8192,
            streaming=streaming,
            config=config
        )
