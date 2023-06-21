from abc import ABC
from functools import cached_property
from time import sleep
from typing import Optional, Sequence, Dict
from docker import DockerClient
from docker.errors import ImageNotFound, DockerException
from docker.models.containers import Container as DockerPyContainer

from ..service import Service, T

class ContainerFailedToStart(Exception):

    def __init__(self, name: str, image_tag: str, reason: str, logs: bytes):
        self.name = name
        self.image_tag = image_tag
        self.reason = reason
        self.logs = logs

    def __str__(self) -> str:
        logs = self.logs.decode(errors='replace')
        return f'name={self.name}\nimage={self.image_tag}\nreason={self.reason}\nlogs:\n{logs}'

DEFAULT_START_WAIT = 0.05
DEFAULT_READY_POLL_WAIT = 0.01
DEFAULT_READY_TIMEOUT = 5

DOCKER_IO_PREFIX = 'docker.io/'


class ContainerImplementation(Service[T], ABC):

    _container: Optional[DockerPyContainer] = None
    port_map: Optional[Dict[int, int]] = None

    #: The number of seconds to wait before checking whether a started container
    #: has remained running.
    start_wait: float

    #: Phrases that should be present in contain logs for the container to be considered
    #: to have successfully started.
    ready_phrases: Sequence[bytes]

    #: The number of seconds to wait between checks for :attr:`ready_phrases`.
    ready_poll_wait: float

    #: The number of seconds checking for :attr:`ready_phrases` after which the container
    #: will be considered to have failed to start.
    ready_timeout: float

    def __init__(
            self,
            image: str,
            version: str,
            always_pull: bool = False,
            env: Optional[Dict[str, str]] = None,
            ports: Optional[Dict[int, int]] = None,
            volumes: Optional[Dict[str, Dict[str, str]]] = None,
            start_wait: float = DEFAULT_START_WAIT,
            ready_phrases: Sequence[bytes] = (),
            ready_poll_wait: float = DEFAULT_READY_POLL_WAIT,
            ready_timeout: float = DEFAULT_READY_TIMEOUT,
            name: Optional[str] = None,
    ):
        super().__init__()
        self.image = image
        self.version = version
        self.always_pull = always_pull
        self.env = env or {}
        self.ports = ports or {}
        self.volumes = volumes or {}
        self.start_wait = start_wait
        self.ready_phrases = ready_phrases
        self.ready_poll_wait = ready_poll_wait
        self.ready_timeout = ready_timeout
        self.name = name

    @cached_property
    def _client(self) -> DockerClient:
        return DockerClient.from_env()

    def _image_has_tag(self, tag: str) -> bool:
        client = self._client
        for attr in 'ImageID', 'Image':
            image_name = self._container.attrs.get(attr)
            if image_name is not None:
                break
        if not image_name:
            return False
        if image_name.startswith('sha256:'):
            _, image_name = image_name.split(':', 1)
        image = client.images.get(image_name)
        has_tag = tag in image.tags
        # docker strips docker.io/ from tags
        if not has_tag and tag.startswith(DOCKER_IO_PREFIX):
            has_tag = tag[len(DOCKER_IO_PREFIX):] in image.tags
        return has_tag

    def possible(self) -> bool:
        try:
            self._client
        except DockerException:
            return False
        else:
            return True

    def create(self) -> None:
        assert self._container is None
        client = self._client
        image_tag = f'{self.image}:{self.version}'

        try:
            client.images.get(image_tag)
        except ImageNotFound:
            pull = True
        else:
            pull = False
        if pull or self.always_pull:
            client.images.pull(self.image, tag=self.version)

        self._container = _container = client.containers.create(
            image_tag,
            environment=self.env,
            ports={f'{source}/tcp': dest for source, dest in self.ports.items()},
            volumes=self.volumes,
            name=self.name,
        )
        self._container.start()
        sleep(self.start_wait)
        reason = ''
        started = failed = False
        waited = 0.0
        while not (started or failed):
            _container = client.containers.get(self._container.id)
            if _container.status != 'running':
                reason = f'status: {_container.status}'
                failed = True
            elif waited > self.ready_timeout:
                reason = f'Took longer than {self.ready_timeout}s waiting for {reason!r}'
                failed = True
            else:
                log: bytes = _container.logs()
                start = 0
                for phrase in self.ready_phrases:
                    index = log.find(phrase, start)
                    if index < 0:
                        waited += self.ready_poll_wait
                        reason = phrase.decode()
                        sleep(self.ready_poll_wait)
                        break
                    start = index + len(phrase)
                else:
                    started = True

        if failed:
            raise ContainerFailedToStart(_container.name, image_tag, reason, _container.logs())

        self._container = _container = client.containers.get(_container.id)

        self.port_map = {
            source: int(self._container.ports[f'{source}/tcp'][0]['HostPort'])
            for source, dest in self.ports.items()
        }

    def destroy(self) -> None:
        if self._container is not None:
            self._container.stop(timeout=0)
            self._container.remove()
            del self._container


class Container(ContainerImplementation['Container']):

    def get(self) -> "Container":
        return self
