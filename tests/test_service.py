from typing import Self

from testfixtures import compare, ShouldRaise
from testfixtures.mock import Mock, call

from testservices.service import Service


def test_abstract():
    service = Service[None]()
    with ShouldRaise(NotImplementedError):
        service.get()
    with ShouldRaise(NotImplementedError):
        service.exists()


class SampleService(Service['SampleService']):

    def get(self) -> "SampleService":
        return self


def test_minimal():
    service = SampleService()
    compare(service.name, expected=None)
    service.name = 'foo'
    compare(service.name, expected='foo')
    assert service.possible()
    with service as s:
        assert s is service


class MockService(Service['MockService']):

    def __init__(self, mock: Mock, name: str, *args):
        self.mock = getattr(mock, name)
        self.mock.init(*args)
        super().__init__()

    def create(self) -> None:
        self.mock.create()

    def destroy(self) -> None:
        self.mock.destroy()

    def get(self) -> Self:
        self.mock.get()
        return self

    def use(self) -> None:
        self.mock.use()


def test_single():
    mock = Mock()
    service = MockService(mock, 'service')
    with service:
        service.use()
    compare(mock.mock_calls, expected=[
        call.service.init(),
        call.service.create(),
        call.service.get(),
        call.service.use(),
        call.service.destroy(),
    ])
