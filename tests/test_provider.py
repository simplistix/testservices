from dataclasses import dataclass

from testfixtures import compare, ShouldRaise

from testservices.provider import Provider, NoAvailableService
from testservices.service import Service


@dataclass
class SampleInstance:
    identifier: str


class SampleService(Service[SampleInstance]):

    count: int = 0
    started: int = 0
    stopped: int = 0

    def __init__(self, available: bool = True, name: str | None = None):
        self._available = available
        self._name = name or type(self).__name__

    def possible(self) -> bool:
        return self._available

    def create(self):
        self.started += 1

    def destroy(self):
        self.stopped += 1

    def get(self) -> SampleInstance:
        self.count += 1
        return SampleInstance(identifier=f'{self._name}:{self.count}')


def test_minimal():
    service = SampleService()
    provider = Provider[SampleInstance](service)
    compare(service.started, expected=0)
    compare(service.stopped, expected=0)
    with provider as instance:
        compare(service.started, expected=1)
        compare(service.stopped, expected=0)
        compare(instance, expected=SampleInstance('SampleService:1'))
    compare(service.started, expected=1)
    compare(service.stopped, expected=1)


def test_first_not_available():
    service1 = SampleService(name='1', available=False)
    service2 = SampleService(name='2', available=True)
    provider = Provider[SampleInstance](service1, service2)
    compare(service1.started, expected=0)
    compare(service1.stopped, expected=0)
    compare(service2.started, expected=0)
    compare(service2.stopped, expected=0)
    with provider as instance:
        compare(service1.started, expected=0)
        compare(service1.stopped, expected=0)
        compare(service2.started, expected=1)
        compare(service2.stopped, expected=0)
        compare(instance, expected=SampleInstance('2:1'))
    compare(service1.started, expected=0)
    compare(service1.stopped, expected=0)
    compare(service2.started, expected=1)
    compare(service2.stopped, expected=1)


def test_none_available():
    service1 = SampleService(name='1', available=False)
    service2 = SampleService(name='2', available=False)
    provider = Provider[SampleInstance](service1, service2)
    with ShouldRaise(NoAvailableService()):
        with provider:
            pass  # pragma: no cover


def test_no_services():
    provider = Provider[SampleInstance]()
    with ShouldRaise(NoAvailableService()):
        with provider:
            pass  # pragma: no cover
