import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Dict
from urllib.parse import urlparse
from uuid import uuid1

from .containers import (
    ContainerImplementation, DEFAULT_READY_POLL_WAIT, DEFAULT_READY_TIMEOUT, DEFAULT_START_WAIT
)
from ..service import Service
from ..tcp import wait_for_server


@dataclass
class Database:
    """
    The credentials to connect to a database.
    """
    host: str
    port: int | None
    username: str
    password: str | None
    database: str | None
    dialect: str | None = None
    driver: str | None = None

    @property
    def url(self) -> str:
        auth = self.username
        if self.password:
            auth += f':{self.password}'
        protocol = self.dialect
        if self.driver:
            protocol = f'{protocol}+{self.driver}'
        netloc = f'{auth}@{self.host}'
        if self.port:
            netloc = f'{netloc}:{self.port}'
        url_ = f'{protocol}://{netloc}'
        if self.database:
            url_ = f'{url_}/{self.database}'
        return url_


class DatabaseContainer(ContainerImplementation[Database]):

    _port = None

    username: str
    database: str

    def __init__(
            self,
            image: str,
            version: str,
            port: int,
            dialect: str,
            start_wait: float = DEFAULT_START_WAIT,
            ready_phrases: Sequence[bytes] = (),
            ready_poll_wait: float = DEFAULT_READY_POLL_WAIT,
            ready_timeout: float = DEFAULT_READY_TIMEOUT,
            driver: Optional[str] = None,
            volumes: Optional[Dict[str, Dict[str, str]]] = None,
            always_pull: bool = False,
            env: Optional[Dict[str, str]] = None,
            name: Optional[str] = None,
    ):
        self.dialect = dialect
        self.driver = driver
        self.password = str(uuid1())
        super().__init__(
            image, version, always_pull, env, {port: 0}, volumes,
            start_wait, ready_phrases, ready_poll_wait, ready_timeout, name
        )

    def get(self) -> Database:
        assert self.port_map is not None, 'create() not called!'
        return Database(
            host='127.0.0.1',
            port=tuple(self.port_map.values())[0],
            username=self.username,
            password=self.password,
            database=self.database,
            dialect=self.dialect,
            driver=self.driver
        )


class PostgresContainer(DatabaseContainer):

    username = 'postgres'
    database = 'postgresdb'

    def __init__(
            self,
            image: str = "docker.io/library/postgres",
            version: str = 'latest',
            driver: str | None = None,
            always_pull: bool = False,
    ):
        super().__init__(
            image,
            version,
            port=5432,
            dialect='postgresql',
            ready_phrases=(
                b'PostgreSQL init process complete; ready for start up',
                b"LOG:  database system is ready to accept connections",
            ),
            driver=driver,
            always_pull = always_pull,
        )
        self.env = {
            'POSTGRES_USER': self.username,
            'POSTGRES_PASSWORD': self.password,
            'POSTGRES_DB': self.database,
        }


class MariadbContainer(DatabaseContainer):

    username = 'mysqluser'
    database = 'mysqldb'

    def __init__(
            self,
            image: str = "docker.io/library/mariadb",
            version: str = 'latest',
            driver: str | None = None,
            always_pull: bool = False,
    ):
        super().__init__(
            image,
            version,
            port=3306,
            dialect='mysql',
            ready_phrases=(
                b'Temporary server started.',
                b"ready for connections.",
            ),
            ready_timeout=10,
            driver=driver,
            always_pull=always_pull,
        )
        self.root_password = str(uuid1())
        self.env = {
            'MARIADB_ROOT_PASSWORD': self.root_password,
            'MYSQL_USER': self.username,
            'MYSQL_PASSWORD': self.password,
            'MYSQL_DATABASE': self.database,
        }


CLICKHOUSE_CONFIG = str((Path(__file__).parent / 'config' / 'clickhouse').absolute())


class ClickhouseContainer(DatabaseContainer):

    username = 'clickhouseuser'
    database = 'default'

    def __init__(
            self,
            image: str = "docker.io/clickhouse/clickhouse-server",
            version: str = 'latest',
            driver: str | None = None,
            database: str | None = None,
            always_pull: bool = False,
    ):
        env = {
            'CLICKHOUSE_USER': self.username,
            'CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT': '1',
            'CLICKHOUSE_LOG_LEVEL': 'TRACE',
        }
        ready_phrases = [b'<Information> Application: Ready for connections.']
        if database:
            ready_phrases *= 2
            self.database = database
            env['CLICKHOUSE_DB'] = self.database
        super().__init__(
            image,
            version,
            volumes={CLICKHOUSE_CONFIG: {'bind': '/etc/clickhouse-server/config.d', 'mode': 'ro'}},
            port=9000,
            dialect='clickhouse',
            ready_phrases=ready_phrases,
            driver=driver,
            always_pull=always_pull,
        )
        env['CLICKHOUSE_PASSWORD'] = self.password
        self.env = env


class DatabaseFromEnvironment(Service[Database]):
    """
    A :class:`Database` service where the credentials are extracted from
    an environment variable.
    """

    def __init__(
            self,
            url: str ='DB_URL',
            *,
            check: bool = True,
            timeout: float = 5,
            poll_frequency: float = 0.05,
    ):
        self.url = url
        self.check = check
        self.timeout = timeout
        self.poll_frequency = poll_frequency

    def possible(self) -> bool:
        return self.url in os.environ

    def get(self) -> Database:
        parts = urlparse(os.environ[self.url])
        scheme_parts = parts.scheme.split('+', 1)
        assert parts.hostname, 'url must have hostname'
        assert parts.username, 'url must have username'
        if len(scheme_parts) == 1:
            dialect = scheme_parts[0]
            driver = None
        else:
            dialect, driver = scheme_parts
        database = Database(
            host=parts.hostname,
            port=int(parts.port) if parts.port else None,
            username=parts.username,
            password=parts.password,
            database=parts.path[1:] if parts.path else None,
            dialect=dialect,
            driver=driver,
        )
        if self.check:
            assert database.port, 'port must be specified when check=True'
            wait_for_server(database.port, database.host, self.timeout, self.poll_frequency)
        return database
