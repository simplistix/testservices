import pytest
from clickhouse_driver import Client as ClickhouseClient
from sqlalchemy import create_engine, MetaData, text
from testfixtures import compare, replace_in_environ, not_there

from testservices.services.databases import PostgresContainer, MariadbContainer, \
    ClickhouseContainer, DatabaseFromEnvironment, Database


@pytest.mark.containers
def test_postgres_minimal():
    with PostgresContainer() as db:
        # we don't want psycopg2 as a dependency for just this one test!
        url = f'postgresql+psycopg://{db.username}:{db.password}@{db.host}:{db.port}/{db.database}'
        engine = create_engine(url)
        metadata = MetaData()
        connection = engine.connect()
        metadata.reflect(connection)
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
        engine = create_engine(db.url)
        metadata = MetaData()
        connection = engine.connect()
        metadata.reflect(connection)
        version = connection.execute(text('SELECT VERSION()')).scalar()
        assert version.startswith('PostgreSQL 15')
        connection.close()
        engine.dispose()


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
        engine = create_engine(db.url)
        metadata = MetaData()
        connection = engine.connect()
        metadata.reflect(connection)
        version = connection.execute(text('SELECT VERSION()')).scalar()
        assert version.startswith('10')
        connection.close()
        engine.dispose()


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


class TestDatabaseFromEnvironment:

    def test_not_available(self):
        service = DatabaseFromEnvironment()
        with replace_in_environ('DB_URL', not_there):
            assert not service.available()

    def test_url_minimal(self):
        service = DatabaseFromEnvironment()
        with replace_in_environ('DB_URL', 'postgresql://user@host:1234'):
            assert service.available()
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

    def test_url_explicit_env_var(self):
        service = DatabaseFromEnvironment('PROJECT_DB_URL')
        with replace_in_environ('PROJECT_DB_URL', 'postgresql://user@host:1234'):
            assert service.available()
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

    def test_url_maximal(self):
        service = DatabaseFromEnvironment()
        with replace_in_environ('DB_URL', 'postgresql+psycopg://u:p@h:456/db'):
            assert service.available()
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

