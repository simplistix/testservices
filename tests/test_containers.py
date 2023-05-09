import docker
import pytest
from clickhouse_driver import Client as ClickhouseClient
from docker.errors import NotFound
from testfixtures import compare, ShouldRaise

from testservices.services.containers import Container
from testservices.services.databases import CLICKHOUSE_CONFIG


@pytest.fixture()
def service() -> Container:
    return Container(
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
def test_container_available(service: Container):
    assert service.available()


@pytest.mark.no_containers
def test_containers_not_available(service: Container):
    assert not service.available()

