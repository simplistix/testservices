import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Dict
from urllib.parse import urlparse, urlunparse
from uuid import uuid1

from .containers import Container
from ..service import Service
from ..tcp import wait_for_server


@dataclass
class Database:
    host: str
    port: int
    username: str
    password: Optional[str]
    database: Optional[str]
    dialect: Optional[str] = None
    driver: Optional[str] = None

    @property
    def url(self) -> str:
        auth = self.username
        if self.password:
            auth += f':{self.password}'
        protocol = self.dialect
        if self.driver:
            protocol = f'{protocol}+{self.driver}'
        url_ = f'{protocol}://{auth}@{self.host}:{self.port}'
        if self.database:
            url_ = f'{url_}/{self.database}'
        return url_


class DatabaseContainer(Container):

    _port = None

    username: str
    database: str

    def __init__(
            self,
            image: str,
            version: str,
            port: int,
            dialect: str,
            ready_phrases: Sequence[bytes] = (),
            driver: Optional[str] = None,
            volumes: Optional[Dict[str, Dict[str, str]]] = None,
            always_pull: bool = False,
            env: Optional[Dict[str, str]] = None,
    ):
        self.dialect = dialect
        self.driver = driver
        self.password = str(uuid1())
        super().__init__(image, version, {port: 0}, ready_phrases, volumes, env, always_pull)

    def get(self) -> Database:
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
            driver: str = None,
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
            driver: str = None,
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
            driver: str = None,
            database: str = None,
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


class DatabaseFromEnvironment(Service):

    def __init__(
            self,
            url='DB_URL',
            *,
            check: bool = True,
            timeout: float = 5,
            poll_frequency: float = 0.05,
    ):
        self.url = url
        self.check = check
        self.timeout = timeout
        self.poll_frequency = poll_frequency

    def available(self) -> bool:
        return self.url in os.environ

    def get(self) -> Database:
        parts = urlparse(os.environ[self.url])
        scheme_parts = parts.scheme.split('+', 1)
        if len(scheme_parts) == 1:
            dialect = scheme_parts[0]
            driver = None
        else:
            dialect, driver = scheme_parts
        database = Database(
            host=parts.hostname,
            port=int(parts.port),
            username=parts.username,
            password=parts.password,
            database=parts.path[1:] if parts.path else None,
            dialect=dialect,
            driver=driver,
        )
        if self.check:
            wait_for_server(database.port, database.host, self.timeout, self.poll_frequency)
        return database
