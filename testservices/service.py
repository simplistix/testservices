from abc import ABC
from types import TracebackType
from typing import Type, Optional, Any, Generic, TypeVar, cast

T = TypeVar('T')


class Service(Generic[T], ABC):

    def available(self) -> bool:
        """
        Returns ``True`` if this service can be used.
        """
        return True

    def start(self) -> None:
        """
        Do any work needed to start this service.
        """

    def get(self) -> T:
        """
        Return an object that makes most sense to use this service.
        This method may be called many times during the life of the service.
        """
        raise NotImplementedError

    def stop(self) -> None:
        """
        Do any work needed to stop this service and clean up anything required.
        """

    def __enter__(self) -> T:
        self.start()
        return self.get()

    def __exit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType]
    ) -> None:
        self.stop()


class Dependency:
    service: Type[Service]
    name: Optional[str]
