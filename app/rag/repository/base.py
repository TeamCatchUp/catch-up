from abc import ABC, abstractmethod

from langchain_core.documents import Document


class VectorStoreRepository(ABC):
    @abstractmethod
    def retrieve(self, query: str, k: int) -> list[Document]:
        pass
