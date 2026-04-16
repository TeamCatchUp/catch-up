from concurrent.futures import ThreadPoolExecutor


class RagExecutors:
    vector_search: ThreadPoolExecutor | None = None
    bedrock_rerank: ThreadPoolExecutor | None = None
    llm: ThreadPoolExecutor | None = None

    def init(
        self,
        vector_search_size: int = 10,
        bedrock_rerank_size: int = 3,
        llm_size: int = 20,
    ) -> None:
        self.vector_search = ThreadPoolExecutor(
            max_workers=vector_search_size,
            thread_name_prefix="vector-search",
        )
        self.bedrock_rerank = ThreadPoolExecutor(
            max_workers=bedrock_rerank_size,
            thread_name_prefix="bedrock-rerank",
        )
        self.llm = ThreadPoolExecutor(
            max_workers=llm_size,
            thread_name_prefix="rag-llm",
        )

    def shutdown(self, wait: bool = True, cancel_futures: bool = True) -> None:
        for executor in [self.vector_search, self.bedrock_rerank, self.llm]:
            if executor:
                executor.shutdown(wait=wait, cancel_futures=cancel_futures)


# Singleton
rag_executors = RagExecutors()
