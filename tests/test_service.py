from testfixtures import compare, ShouldRaise
from testfixtures.mock import Mock, call

from testservices.service import Service


def test_abstract():
    service = Service[Service]()
    with ShouldRaise(NotImplementedError):
        service.get()

class SampleService(Service['SampleService']):

    def get(self) -> "SampleService":
        return self


def test_minimal():
    service = SampleService()
    assert service.available()
    with service as s:
        assert s is service


class MockService(Service):

    def __init__(self, mock: Mock, name: str, *args):
        self.mock = getattr(mock, name)
        self.mock.init(*args)
        super().__init__()

    def start(self):
        self.mock.start()

    def stop(self):
        self.mock.stop()

    def get(self):
        self.mock.get()
        return self

    def use(self):
        self.mock.use()


def test_single():
    mock = Mock()
    service = MockService(mock, 'service')
    with service:
        service.use()
    compare(mock.mock_calls, expected=[
        call.service.init(),
        call.service.start(),
        call.service.get(),
        call.service.use(),
        call.service.stop(),
    ])
