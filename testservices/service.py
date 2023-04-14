from typing import List, Sequence, Type, Optional

from .provider import Provider
from .supplier import Supplier


class Service:
    name: str
    providers: List[Provider]
    suppliers: List[Supplier]

    def start(self):
        pass

    def get(self):
        return self

    def stop(self):
        pass

    def cleanup(self):
        pass

    def __enter__(self):
        self.start()
        return self.get()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        self.cleanup()


class Dependency:
    service: Type[Service]
    name: Optional[str]
