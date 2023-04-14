from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Optional, Sequence, Dict
from uuid import uuid1

import docker
from docker.errors import ImageNotFound
from docker.models.containers import Container

from ..service import Service


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


class DatabaseContainer(Service):

    _container = None
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
    ):
        super().__init__()
        self.image = image
        self.version = version
        self.env = {}
        self.port = port
        self.ready_phrases = ready_phrases
        self.dialect = dialect
        self.driver = driver
        self.password = str(uuid1())
        self.volumes = volumes or {}

    def start(self):
        client = docker.from_env()
        image_tag = f'{self.image}:{self.version}'
        try:
            client.images.get(image_tag)
        except ImageNotFound:
            client.images.pull(self.image, tag=self.version)
        self._container: Container = client.containers.run(
            image_tag,
            environment=self.env,
            ports={f'{self.port}/tcp': 0},
            detach=True,
            auto_remove=True,
            volumes=self.volumes,
        )
        self._container = client.containers.get(self._container.id)
        self._port = int(self._container.ports[f'{self.port}/tcp'][0]['HostPort'])
        starting = True
        while starting:
            log: bytes = self._container.logs()
            start = 0
            for phrase in self.ready_phrases:
                index = log.find(phrase, start)
                if index < 0:
                    sleep(0.01)
                    break
                start = index + len(phrase)
            else:
                starting = False

    def get(self):
        return Database(
            host='127.0.0.1',
            port=self._port,
            username=self.username,
            password=self.password,
            database=self.database,
            dialect=self.dialect,
            driver=self.driver
        )

    def stop(self):
        if self._container is not None:
            self._container.stop(timeout=0)


class PostgresContainer(DatabaseContainer):

    username = 'postgres'
    database = 'postgresdb'

    def __init__(
            self,
            image: str = "docker.io/library/postgres",
            version: str = 'latest',
            driver: str = None
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
            driver: str = None
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

    root_password: str = str(uuid1())
    username = 'clickhouseuser'
    database = 'default'

    def __init__(
            self,
            image: str = "docker.io/clickhouse/clickhouse-server",
            version: str = 'latest',
            driver: str = None,
            username: str = 'clickhouseuser',
            database: str = None,
    ):
        env = {
            'CLICKHOUSE_USER': username,
            'CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT': '1',
            'CLICKHOUSE_LOG_LEVEL': 'TRACE',
        }
        self.username = username
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
        )
        env['CLICKHOUSE_PASSWORD'] = self.password
        self.env = env
