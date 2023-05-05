import pytest
from clickhouse_driver import Client as ClickhouseClient
from testfixtures import compare

from testservices.services.containers import Container
from testservices.services.databases import CLICKHOUSE_CONFIG


@pytest.mark.containers
def test_clickhouse_maximal():
    service = Container(
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
    with service as container:
        client = ClickhouseClient(
            host='localhost',
            port=container.port_map[9000],
            user='foo',
            password='pass'
        )
        compare(client.execute('SHOW DATABASES'), expected=[
            ('INFORMATION_SCHEMA',), ('default',), ('information_schema',), ('system',)
        ])


