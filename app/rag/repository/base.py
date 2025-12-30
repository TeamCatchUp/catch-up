from abc import ABC, abstractmethod


class VectorStoreRepository(ABC):
    @abstractmethod
    def retrieve(self, query: str, k: int) -> list[str]:
        pass
