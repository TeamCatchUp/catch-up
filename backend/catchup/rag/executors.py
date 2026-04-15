from concurrent.futures import ThreadPoolExecutor


class RagExecutors:
    chat: ThreadPoolExecutor | None = None
    bedrock_rerank: ThreadPoolExecutor | None = None

    def init(self, chat_thread_pool_size: int = 10, bedrock_rerank_size: int = 3) -> None:
        self.chat = ThreadPoolExecutor(
            max_workers=chat_thread_pool_size,
            thread_name_prefix="rag-chat",
        )
        self.bedrock_rerank = ThreadPoolExecutor(
            max_workers=bedrock_rerank_size,
            thread_name_prefix="bedrock-rerank",
        )

    def shutdown(self, wait: bool = True, cancel_futures: bool = True) -> None:
        for executor in [self.chat, self.bedrock_rerank]:
            if executor:
                executor.shutdown(wait=wait, cancel_futures=cancel_futures)


# Singleton
rag_executors = RagExecutors()
