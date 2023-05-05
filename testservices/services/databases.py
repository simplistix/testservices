from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Dict
from uuid import uuid1

from .containers import Container


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
        return f'{protocol}://{auth}@{self.host}:{self.port}/{self.database}'


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

    def get(self):
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
