import sys
from collections import defaultdict
from pathlib import Path
from types import TracebackType, FrameType
from typing import Mapping, Optional, TypeVar, Type, Union, Dict, List, Any, cast

from .service import Service

T = TypeVar('T')


class NameConflict(Exception):
    """
    A service name conflicts with service already in the collection
    """


class MissingService(Exception):
    """
    A service did not exist when was needed.
    """


class ManagedService(Service[T]):

    def __init__(self, service: Service[T], name: str):
        self.service = service
        self.name = name

    def exists(self) -> bool:
        return self.service.exists()

    def create(self) -> None:
        if not self.service.exists():
            raise MissingService(f'{self.service} did not exist, collection not up?')

    def get(self) -> T:
        return self.service.get()

    def __repr__(self) -> str:
        return f'<Managed {type(self.service).__qualname__}: {self.name}>'


class Collection:

    name: str

    def __init__(
            self,
            *services: Service[Any] | Mapping[str, Service[Any]],
            name: str | None = None,
    ):
        if name is None:
            frame = cast(FrameType, sys._getframe().f_back)
            name = Path(frame.f_code.co_filename).parent.name
        self.name = name
        self._by_name: Dict[str, ManagedService[Any]] = {}
        self._by_type: Dict[Type[Service[Any]], List[ManagedService[Any]]] = defaultdict(list)
        for service in services:
            if isinstance(service, Mapping):
                for name, service_ in service.items():
                    self.manage(service_, name)
            else:
                self.manage(service)

    def up(self) -> None:
        """
        Ensure all services in this collection have been started
        and are ready to use.
        """
        for managed in self._by_name.values():
            service = managed.service
            if not service.exists():
                service.create()

    def down(self) -> None:
        """
        Ensure all services in this collection have been stopped
        and any resources release or cleaned up.
        """
        for managed in self._by_name.values():
            service = managed.service
            if service.exists():
                service.destroy()

    def __enter__(self) -> 'Collection':
        self.up()
        return self

    def __exit__(
            self,
            exc_type: Type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
    ) -> None:
        self.down()

    def manage(self, service: Service[T], name: str | None = None) -> Service[T]:
        """
        Manage the supplied service, optionally under the supplied name.
        """

        explicit_name = name or service.name
        if explicit_name:
            if explicit_name in self._by_name:
                raise NameConflict(explicit_name)
            name = explicit_name
        else:
            i = 1
            name = base = type(service).__qualname__
            while name in self._by_name:
                i += 1
                name = f'{base}_{i}'

        managed = ManagedService[T](service, name)
        self._by_name[name] = managed
        self._by_type[type(service)].append(managed)

        service.name = '_'.join(part for part in [self.name, name] if part)

        return managed

    def obtain(self, service_type: Type[Service[T]], name: str | None = None) -> ManagedService[T]:
        """
        Obtain a service managed by this collection of the specified type and,
        optionally, name.
        """
        if name:
            managed = self._by_name[name]
            if type(managed.service) is not service_type:
                raise TypeError(
                    f"{name!r} is of type {type(managed.service).__qualname__}, "
                    f"but {service_type.__qualname__} requested"
                )
            return managed
        possible = self._by_type[service_type]
        if len(possible) > 1:
            text = ', '.join(repr(managed) for managed in possible)
            raise TypeError(
                f'Multiple services, specify name: {text}'
            )
        return possible[0]

