from asyncio import Semaphore


class NamedSemaphore(Semaphore):
    def __init__(self, value: int, name: str):
        super().__init__(value)
        self.name = name


class ServiceSemaphores:
    llm_small: Semaphore | None = None
    llm_large: Semaphore | None = None
    reranker: Semaphore | None = None

    def init(
        self,
        small_llm_value: int,
        large_llm_value: int,
        reranker_value: int,
    ) -> None:
        self.llm_small = NamedSemaphore(small_llm_value, "llm_small")
        self.llm_large = NamedSemaphore(large_llm_value, "llm_large")
        self.reranker = NamedSemaphore(reranker_value, "reranker")


# Singleton
service_semaphores = ServiceSemaphores()
