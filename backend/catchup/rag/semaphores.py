from asyncio import Semaphore


class NamedSemaphore(Semaphore):
    def __init__(self, value: int, name: str):
        super().__init__(value)
        self.name = name


class RagSemaphores:
    analysis: Semaphore | None = None
    final_answer: Semaphore | None = None
    rerank: Semaphore | None = None

    def init(
        self,
        small_model_sema_value: int,
        large_model_sema_value: int,
        rerank_sema_value: int,
    ) -> None:
        self.analysis = NamedSemaphore(small_model_sema_value, "analysis")
        self.final_answer = NamedSemaphore(large_model_sema_value, "final_answer")
        self.rerank = NamedSemaphore(rerank_sema_value, "rerank")

# Singleton
rag_semaphores = RagSemaphores()