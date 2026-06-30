from concurrent.futures import ThreadPoolExecutor


class ServiceExecutors:
    vector_search_executor: ThreadPoolExecutor | None = None
    rerank_executor: ThreadPoolExecutor | None = None
    llm_executor: ThreadPoolExecutor | None = None

    def init(
        self,
        vector_search_size: int = 10,
        rerank_size: int = 3,
        llm_size: int = 20,
    ) -> None:
        self.vector_search_executor = ThreadPoolExecutor(
            max_workers=vector_search_size,
            thread_name_prefix="vector-search",
        )
        self.rerank_executor = ThreadPoolExecutor(
            max_workers=rerank_size,
            thread_name_prefix="bedrock-rerank",
        )
        self.llm_executor = ThreadPoolExecutor(
            max_workers=llm_size,
            thread_name_prefix="rag-llm",
        )

    def shutdown(self, wait: bool = True, cancel_futures: bool = True) -> None:
        for executor in [
            self.vector_search_executor,
            self.rerank_executor,
            self.llm_executor,
        ]:
            if executor:
                executor.shutdown(wait=wait, cancel_futures=cancel_futures)


# Singleton
service_executors = ServiceExecutors()
