from typing import TypeVar, Type, Optional

from .service import Service

T = TypeVar("T")


class NoAvailableService(Exception):
    pass


class Provider:

    _service: Optional[Service] = None

    def __init__(self, provides: Type[T], *services: Service):
        self.provides = provides
        self.services = services

    def __enter__(self) -> T:
        for service in self.services:
            if service.available():
                service.start()
                self._service = service
                return service.get()
        else:
            raise NoAvailableService(
                f'No service available to provide {self.provides.__qualname__}'
            )

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._service is not None:
            self._service.stop()

