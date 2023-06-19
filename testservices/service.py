from abc import ABC
from types import TracebackType
from typing import Type, Optional, Generic, TypeVar

T = TypeVar('T')


class Service(Generic[T], ABC):

    # The name of this service
    name: str = None

    def possible(self) -> bool:
        """
        Returns ``True`` if it's possible to create this service or check if
        it already exists.
        """
        return True


    def create(self) -> None:
        """
        Do any work needed to create this service so it can be used.
        """

    def get(self) -> T:
        """
        Return an object that makes most sense to use this service.
        This method may be called many times during the life of the service.
        """
        raise NotImplementedError

    def destroy(self) -> None:
        """
        Do any work needed to destroy this service and release its resources.
        """

    def __enter__(self) -> T:
        self.create()
        return self.get()

    def __exit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType]
    ) -> None:
        self.destroy()
