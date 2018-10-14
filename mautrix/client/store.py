from abc import ABC, abstractmethod
from .api.types import SyncToken


class ClientStore(ABC):
    @property
    @abstractmethod
    def next_batch(self) -> SyncToken:
        return SyncToken("")

    @next_batch.setter
    @abstractmethod
    def next_batch(self, value: SyncToken) -> None:
        pass

class MemoryClientStore(ClientStore):
    def __init__(self, next_batch: SyncToken) -> None:
        self.next_batch: SyncToken = next_batch

    @property
    def next_batch(self):
        return self.next_batch

    @next_batch.setter
    def next_batch(self, value):
        pass
