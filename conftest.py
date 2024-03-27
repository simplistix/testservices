from socket import socket
from typing import cast

import pytest


@pytest.fixture()
def free_port(address: str = '') -> int:
    s = socket()
    s.bind((address, 0))
    _, port = s.getsockname()
    return cast(int, port)
