from types import TracebackType
from typing import TypeVar, Type, Optional, Generic, get_args

from .service import Service

#: The type of object returned by services in this :class:`Provider`.
T = TypeVar("T")


class NoAvailableService(Exception):
    pass


class Provider(Generic[T]):
    """
    This provides a single :term:`service` from a selection of alternatives.
    The intention is to provide the first :term:`service` that is
    :any:`possible <Service.possible>` in the current
    context, :any:`create <Service.create>` it if doesn't already
    :any:`exist <Service.exists>` and then return
    :any:`the object <Service.get>`
    representing it.
    """

    _service: Optional[Service[T]] = None

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

