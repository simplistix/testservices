import socket
from typing import Union
from unittest.mock import Mock, call

from testfixtures import ShouldRaise, Replacer, compare

from testservices.tcp import wait_for_server


class TestWaitForServer:

    def test_error_not_connection_refused(self):
        with ShouldRaise() as s:
            wait_for_server(-1, '127.0.0.-1')
        assert isinstance(s.raised, socket.error)

    def test_port_must_be_specified(self):
        with ShouldRaise(AssertionError('port may not be None')):
            wait_for_server(None, '127.0.0.-1')  # type: ignore

    def test_poll_to_success(self):
        def create_connection_mock(*returns: Union[Exception, None]):
            returns_ = list(returns)

            def create_connection_(*args):
                value = returns_.pop(0)
                if value:
                    raise value

            return create_connection_

        sleep = Mock()
        create_connection = create_connection_mock(
            socket.error('connection refused 1'),
            socket.error('connection refused 2'),
            None,
        )
        with Replacer() as replace:
            replace('testservices.tcp.sleep', sleep)
            replace('testservices.tcp.create_connection', create_connection)

            wait_for_server(1)

        compare(sleep.mock_calls, expected=[call(0.05), call(0.05)])
