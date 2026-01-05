from langchain_core.messages import trim_messages
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI


class LlmService:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        self.output_parser = StrOutputParser()

        # 대화 히스토리 관련 토큰 제한
        self.trimmer = trim_messages(
            max_tokens=2000,  # 토큰 제한
            strategy="last",  # 최신 부분만 남김
            token_counter=self.llm,  # 토큰 계산기
            include_system=True,  # 시스템 메세지 포함
            allow_partial=False,  # 메세지 단위로 깔끔하게 자름
            start_on="human",  # 대화의 시작은 항상 사람 질문
        )

    def get_llm(self):
        return self.llm

    def get_trimmer(self):
        return self.trimmer
