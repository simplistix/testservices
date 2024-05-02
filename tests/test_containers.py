import json
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict
from uuid import uuid1

import docker
import pytest
from clickhouse_driver import Client as ClickhouseClient
from docker.errors import NotFound, APIError
from testfixtures import compare, ShouldRaise

from testservices.services.containers import (
    Container,
    ContainerFailed,
    MisconfiguredContainer
)
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
        assert service._container is not None
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
    service = Container(
        image,
        version='15',
        name=name,
        ready_phrases=(b"LOG:  database system is ready to accept connections",)
    )
    with ShouldRaise(ContainerFailed) as s:
        service.create()

    message = str(s.raised).split('You must')[0].rstrip()
    # status may be legitimately 'stopped' or 'exited'
    message = message.replace('status: stopped', 'status: exited')

    compare(message, show_whitespace=True, expected=dedent(
        f"""\
        name={name}
        image=docker.io/library/postgres:15
        reason=status: exited
        logs:
        Error: Database is uninitialized and superuser password is not specified.
        """
    ).rstrip())
    assert service._container is not None
    service._container.remove()


@pytest.mark.containers
def test_container_timeout_waiting_for_phrase(service: Container):
    name = str(uuid1())
    service = make_service(
        ready_phrases=[b'foo'], ready_timeout=0.001, ready_poll_wait=0.01, name=name
    )
    with ShouldRaise(ContainerFailed) as s:
        service.create()
    compare(str(s.raised).split('logs:')[0].rstrip(), show_whitespace=True, expected=dedent(
        f"""\
        name={name}
        image=docker.io/clickhouse/clickhouse-server:23.2
        reason=Took longer than 0.001s waiting for 'foo'
        """
    ).rstrip())
    assert service._container is not None
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
        assert container_service._container is not None
        compare(container.id, expected=container_service._container.id)
        assert container_service._image_has_tag('docker.io/clickhouse/clickhouse-server:23.2')


@pytest.mark.containers
def test_container_available(service: Container):
    assert service.possible()


@pytest.mark.no_containers
def test_containers_not_available(service: Container):
    assert not service.possible()


@pytest.mark.containers
def test_exists():
    service = make_service()
    assert not service.exists()
    with service:
        assert service.exists()
    assert not service.exists()


@pytest.mark.containers
def test_exists_when_container_gone():
    service = make_service()
    with service:
        assert service.exists()
        assert service._container is not None
        service._container.stop(timeout=0)
        with ShouldRaise(ContainerFailed) as s:
            assert service.exists()
        compare(str(s.raised).split('logs:')[0].rstrip(), show_whitespace=True, expected=dedent(
            f"""\
            name={service._container.name}
            image=docker.io/clickhouse/clickhouse-server:23.2
            reason=exists but status='exited'
            """
        ).rstrip())
        service._container.remove()
        assert not service.exists()
        del service._container
    assert not service.exists()


@pytest.mark.containers
def test_exists_by_name():
    service = make_service(name='foo')
    assert not service.exists()
    with service:
        assert service.exists()
    assert not service.exists()


@pytest.mark.containers
def test_exists_by_name_multiple_found():
    with make_service(name='foo'):
        # Checking that we can't create container with identical names
        # which means searching by name shouldn't be able to return more than one
        # container:
        duplicate = make_service(name='foo')
        with ShouldRaise(APIError):
            duplicate.create()


@pytest.mark.containers
def test_exists_but_wrong_image(is_podman: bool):

    if is_podman:
        expected = 'docker.io/library/postgres:15'
        actual = 'docker.io/clickhouse/clickhouse-server:23.2'
    else:
        expected = 'postgres:15'
        actual = 'clickhouse/clickhouse-server:23.2'

    service1 = make_service(name='foo', image="docker.io/clickhouse/clickhouse-server")
    service2 = make_service(name='foo', image="docker.io/library/postgres", version='15')
    with service1:
        with ShouldRaise(MisconfiguredContainer(
                f"image: expected=<Image: '{expected}'>, "
                f"actual=<Image: '{actual}'>"
        )):
            service2.exists()
    assert not service1.exists()
    assert not service2.exists()


@pytest.mark.containers
def test_exists_but_wrong_env():
    service1 = make_service(name='foo')
    service2 = make_service(name='foo', env={'CLICKHOUSE_USER': 'bar', 'OTHER': 'BAZ'})
    with service1:
        with ShouldRaise(MisconfiguredContainer(
                "environment: CLICKHOUSE_USER: expected='bar' actual='foo', "
                "OTHER: expected='BAZ' actual=None"
        )):
            service2.exists()
    assert not service1.exists()
    assert not service2.exists()


@pytest.mark.containers
def test_exists_but_wrong_port(free_port: int):
    service1 = make_service(name='foo', ports={9000: free_port})
    service2 = make_service(name='foo', ports={9000: 1234})
    with service1:
        with ShouldRaise(MisconfiguredContainer(
                "ports:\n"
                "expected={'9000/tcp': 1234}\n"
                f"  actual={{'9000/tcp': '{free_port}'}}"
        )):
            service2.exists()
    assert not service1.exists()
    assert not service2.exists()


@pytest.mark.containers
def test_exists_but_missing_port(free_port: int):
    service1 = make_service(name='foo', ports={9000: free_port})
    service2 = make_service(name='foo', ports={1234: 0})
    with service1:
        with ShouldRaise(MisconfiguredContainer(
                "ports:\n"
                "expected={'1234/tcp': 0}\n"
                f"  actual={{'9000/tcp': '{free_port}'}}"
        )):
            service2.exists()
    assert not service1.exists()
    assert not service2.exists()


@pytest.mark.containers
def test_exists_but_wrong_volumes(tmp_path: Path):
    necessary_volumes = {CLICKHOUSE_CONFIG: {'bind': '/etc/clickhouse-server/config.d',
                                             'mode': 'ro'}}
    (tmp_path / 'volume1').mkdir()
    (tmp_path / 'volume2').mkdir()
    (tmp_path / 'volume3').mkdir()

    volumes1 = necessary_volumes.copy()
    volumes1[str(tmp_path / 'volume1')] = {'bind': '/volume1', 'mode': 'ro'}
    volumes1[str(tmp_path / 'volume2')] = {'bind': '/volumeX', 'mode': 'ro'}
    service1 = make_service(name='foo', volumes=volumes1)

    volumes2 = necessary_volumes.copy()
    volumes2[str(tmp_path / 'volume2')] = {'bind': '/volumeY', 'mode': 'rw'}
    volumes2[str(tmp_path / 'volume3')] = {'bind': '/volume3', 'mode': 'rw'}
    service2 = make_service(name='foo', volumes=volumes2)

    with service1:
        with ShouldRaise(MisconfiguredContainer) as s:
            service2.exists()
    compare(str(s.raised), expected=(
        f'volumes:\n'
        f'expected=\n{json.dumps(volumes2, indent=4)}\n'
        f'  actual=\n{json.dumps(volumes1, indent=4)}'
    ))
    assert not service1.exists()
    assert not service2.exists()
