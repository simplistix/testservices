from textwrap import dedent
from typing import Any, Dict
from uuid import uuid1

import docker
import pytest
from clickhouse_driver import Client as ClickhouseClient
from docker.errors import NotFound
from testfixtures import compare, ShouldRaise

from testservices.services.containers import Container, ContainerFailedToStart
from testservices.services.databases import CLICKHOUSE_CONFIG


def make_service(**overrides: Any) -> Container:
    params: Dict[str, Any] = dict(
        image="docker.io/clickhouse/clickhouse-server",
        version="23.2",
        ports={9000: 0},
        volumes={CLICKHOUSE_CONFIG: {'bind': '/etc/clickhouse-server/config.d', 'mode': 'ro'}},
        env={
            'CLICKHOUSE_USER': "foo",
            'CLICKHOUSE_PASSWORD': 'pass',
            'CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT': '1',
            'CLICKHOUSE_LOG_LEVEL': 'TRACE',
        },
        ready_phrases=[b'<Information> Application: Ready for connections.']
    )
    params.update(overrides)
    return Container(**params)


@pytest.fixture()
def service() -> Container:
    return make_service()


@pytest.mark.containers
def test_container(service: Container):

    with service as container:
        container_id = service._container.id
        client = ClickhouseClient(
            host='localhost',
            port=container.port_map[9000],
            user='foo',
            password='pass'
        )
        compare(client.execute('SHOW DATABASES'), expected=[
            ('INFORMATION_SCHEMA',), ('default',), ('information_schema',), ('system',)
        ])

    # make sure the container is cleaned up:
    client = docker.from_env()
    with ShouldRaise(NotFound):
        client.containers.get(container_id)


@pytest.mark.containers
def test_container_fails_to_start(service: Container):
    image = "docker.io/library/postgres"
    name = str(uuid1())
    service = Container(image, version='15', name=name)
    with ShouldRaise(ContainerFailedToStart) as s:
        service.create()
    compare(str(s.raised).split('Database')[0].rstrip(), show_whitespace=True, expected=dedent(
        f"""\
        name={name}
        image=docker.io/library/postgres:15
        reason=status: exited
        logs:
        Error:
        """
    ).rstrip())
    service._container.remove()


@pytest.mark.containers
def test_container_timeout_waiting_for_phrase(service: Container):
    name = str(uuid1())
    service = make_service(
        ready_phrases=[b'foo'], ready_timeout=0.001, ready_poll_wait=0.01, name=name
    )
    with ShouldRaise(ContainerFailedToStart) as s:
        service.create()
    compare(str(s.raised).split('logs:')[0].rstrip(), show_whitespace=True, expected=dedent(
        f"""\
        name={name}
        image=docker.io/clickhouse/clickhouse-server:23.2
        reason=Took longer than 0.001s waiting for 'foo'
        """
    ).rstrip())
    service._container.stop(timeout=0)
    service._container.remove()


@pytest.mark.containers
def test_container_name():

    client = docker.from_env()
    name = str(uuid1())
    service = make_service(name=name)

    with service as container_service:
        compare(container_service.name, expected=name)
        container = client.containers.get(name)
        compare(container.id, expected=container_service._container.id)
        assert container_service._image_has_tag('docker.io/clickhouse/clickhouse-server:23.2')


@pytest.mark.containers
def test_container_available(service: Container):
    assert service.possible()


@pytest.mark.no_containers
def test_containers_not_available(service: Container):
    assert not service.possible()

