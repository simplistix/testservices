from socket import socket
from threading import Thread
from typing import Iterable

import pytest
from clickhouse_driver import Client as ClickhouseClient
from sqlalchemy import create_engine, MetaData, text
from testfixtures import compare, replace_in_environ, not_there, ShouldRaise

from testservices.services.databases import PostgresContainer, MariadbContainer, \
    ClickhouseContainer, DatabaseFromEnvironment, Database


@pytest.mark.containers
def test_postgres_minimal():
    with PostgresContainer() as db:
        url = f'postgresql+psycopg://{db.username}:{db.password}@{db.host}:{db.port}/{db.database}'
        engine = create_engine(url)
        metadata = MetaData()
        connection = engine.connect()
        metadata.reflect(connection)
        connection.close()
        engine.dispose()


def check_version(db: Database, prefix: str) -> None:
    engine = create_engine(db.url)
    metadata = MetaData()
    connection = engine.connect()
    metadata.reflect(connection)
    version = connection.execute(text('SELECT VERSION()')).scalar()
    assert version is not None
    assert version.startswith(prefix)
    connection.close()
    engine.dispose()


@pytest.mark.containers
def test_postgres_maximal():
    service = PostgresContainer(
        image="docker.io/library/postgres",
        version="15",
        driver='psycopg'
    )
    with service as db:
        check_version(db, 'PostgreSQL 15')


@pytest.mark.containers
def test_mysql_minimal():
    with MariadbContainer() as db:
        # we don't want MySQLdb as a dependency for just this one test!
        url = f'mysql+pymysql://{db.username}:{db.password}@{db.host}:{db.port}/{db.database}'
        engine = create_engine(url)
        metadata = MetaData()
        connection = engine.connect()
        metadata.reflect(connection)
        connection.close()
        engine.dispose()


@pytest.mark.containers
def test_mysql_maximal():
    service = MariadbContainer(
        image="docker.io/library/mariadb",
        version='10',
        driver='pymysql',
    )
    with service as db:
        check_version(db, '10')


@pytest.mark.containers
def test_clickhouse_minimal():
    with ClickhouseContainer() as db:
        client = ClickhouseClient(
            host=db.host,
            port=db.port,
            user=db.username,
            password=db.password,
            database=db.database,
        )
        compare(client.execute('SHOW DATABASES'), expected=[
            ('INFORMATION_SCHEMA',), ('default',), ('information_schema',),
            ('system',)
        ])


@pytest.mark.containers
def test_clickhouse_maximal():
    service = ClickhouseContainer(
        image="docker.io/clickhouse/clickhouse-server",
        version="23.2",
        database='clickhousedb',
    )
    with service as db:
        client = ClickhouseClient(
            host=db.host,
            port=db.port,
            user=db.username,
            password=db.password
        )
        compare(client.execute('SHOW DATABASES'), expected=[
            ('INFORMATION_SCHEMA',), ('clickhousedb',), ('default',), ('information_schema',),
            ('system',)
        ])


class Listener(Thread):

    def __init__(self, address: str = '') -> None:
        super().__init__()
        self.socket = socket()
        self.socket.bind((address, 0))
        _, self.port = self.socket.getsockname()

    def run(self):
        self.socket.listen(0)
        self.socket.settimeout(1)
        self.socket.accept()
        self.socket.close()


@pytest.fixture()
def listening_port() -> Iterable[int]:
    listener = Listener()
    try:
        listener.start()
        yield listener.port
    finally:
        listener.join(timeout=5)


class TestDatabaseFromEnvironment:

    def test_not_available(self):
        service = DatabaseFromEnvironment(check=False)
        with replace_in_environ('DB_URL', not_there):
            assert not service.possible()

    def test_url_minimal(self):
        service = DatabaseFromEnvironment(check=False)
        url = 'postgresql://user@host'
        with replace_in_environ('DB_URL', url):
            assert service.possible()
            with service as db:
                compare(db, expected=Database(
                    host='host',
                    port=None,
                    username='user',
                    password=None,
                    database=None,
                    dialect='postgresql',
                    driver=None,
                ))
                compare(db.url, expected=url)

    def test_url_explicit_env_var(self):
        service = DatabaseFromEnvironment('PROJECT_DB_URL', check=False)
        url = 'postgresql://user@host:1234'
        with replace_in_environ('PROJECT_DB_URL', url):
            assert service.possible()
            with service as db:
                compare(db, expected=Database(
                    host='host',
                    port=1234,
                    username='user',
                    password=None,
                    database=None,
                    dialect='postgresql',
                    driver=None,
                ))
                compare(db.url, expected=url)

    def test_url_maximal(self):
        service = DatabaseFromEnvironment(check=False)
        url = 'postgresql+psycopg://u:p@h:456/db'
        with replace_in_environ('DB_URL', url):
            assert service.possible()
            with service as db:
                compare(db, expected=Database(
                    host='h',
                    port=456,
                    username='u',
                    password='p',
                    database='db',
                    dialect='postgresql',
                    driver='psycopg',
                ))
                compare(db.url, expected=url)

    def test_check_okay(self, listening_port: int):
        service = DatabaseFromEnvironment()
        url = f'postgresql://user@127.0.0.1:{listening_port}'
        with replace_in_environ('DB_URL', url):
            assert service.possible()
            with service as db:
                compare(db, expected=Database(
                    host='127.0.0.1',
                    port=listening_port,
                    username='user',
                    password=None,
                    database=None,
                    dialect='postgresql',
                    driver=None,
                ))
                compare(db.url, expected=url)

    def test_check_timeout(self, free_port: int):
        service = DatabaseFromEnvironment(timeout=0, poll_frequency=0.01)
        url = f'postgresql://user@127.0.0.1:{free_port}'
        with replace_in_environ('DB_URL', url):
            assert service.possible()
            with ShouldRaise(TimeoutError(
                    f'server on 127.0.0.1:{free_port} did not start within 0s'
            )):
                service.get()

    def test_cannot_check_without_explicit_port(self):
        service = DatabaseFromEnvironment()
        url = 'postgresql://user@host'
        with replace_in_environ('DB_URL', url):
            with ShouldRaise(AssertionError('port must be specified when check=True')):
                service.get()
