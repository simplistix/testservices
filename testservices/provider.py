from types import TracebackType
from typing import TypeVar, Type, Optional, Generic, get_args

from .service import Service

T = TypeVar("T")


class NoAvailableService(Exception):
    pass


class Provider(Generic[T]):

    _service: Optional[Service] = None

    def __init__(self, *services: Service[T]):
        self.services = services

    def __enter__(self) -> T:
        for service in self.services:
            if service.possible():
                service.create()
                self._service = service
                return service.get()
        else:
            get_args(type(self))
            raise NoAvailableService()

    def __exit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType]
    ) -> None:
        if self._service is not None:
            self._service.destroy()

