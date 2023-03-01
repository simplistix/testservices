import socket
from datetime import datetime

import pytest
from docker import from_env
from docker.errors import NotFound, DockerException
from testfixtures import ShouldRaise


@pytest.mark.containers
def test_containers_experiment():
    client = from_env()
    print(datetime.now(), 'client')
    service = client.containers.run(
        "docker.io/library/postgres",
        environment={'POSTGRES_HOST_AUTH_METHOD': 'trust'},
        ports={'5432/tcp': 0},
        detach=True,
        auto_remove=True,
    )
    print(datetime.now(), 'started')
    service = client.containers.get(service.id)
    port = int(service.ports['5432/tcp'][0]['HostPort'])
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("localhost", port))
    print(datetime.now(), 'connected')
    service.stop(timeout=0)
    print(datetime.now(), 'stopped')
    with ShouldRaise(NotFound):
        client.containers.get(service.id)


@pytest.mark.no_containers
def test_no_containers_experiment():
    with ShouldRaise(DockerException):
        client = from_env()
