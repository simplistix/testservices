import os
from socket import socket
from typing import cast

import pytest


@pytest.fixture()
def free_port(address: str = '') -> int:
    s = socket()
    s.bind((address, 0))
    _, port = s.getsockname()
    return cast(int, port)


@pytest.fixture()
def is_podman() -> bool:
    return 'podman' in os.environ.get('DOCKER_HOST', '')
