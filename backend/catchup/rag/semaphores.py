from asyncio import Semaphore


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
        self.analysis = Semaphore(small_model_sema_value)
        self.final_answer = Semaphore(large_model_sema_value)
        self.rerank = Semaphore(rerank_sema_value)

# Singleton
rag_semaphores = RagSemaphores()