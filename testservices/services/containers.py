from functools import cached_property
from time import sleep
from typing import Optional, Sequence, Dict
from docker import DockerClient
from docker.errors import ImageNotFound, DockerException
from docker.models.containers import Container as DockerPyContainer

from ..service import Service


class Container(Service):

    _container: Optional[DockerPyContainer] = None
    port_map: Optional[Dict[int, int]] = None

    def __init__(
            self,
            image: str,
            version: str,
            ports: Dict[int, int],
            ready_phrases: Sequence[bytes] = (),
            volumes: Optional[Dict[str, Dict[str, str]]] = None,
            env: Optional[Dict[str, str]] = None,
            always_pull: bool = False,
    ):
        super().__init__()
        self.image = image
        self.version = version
        self.env = env or {}
        self.ports = ports
        self.ready_phrases = ready_phrases
        self.volumes = volumes or {}
        self.always_pull = always_pull

    @cached_property
    def _client(self) -> DockerClient:
        return DockerClient.from_env()

    def available(self) -> bool:
        try:
            self._client
        except DockerException:
            return False
        else:
            return True

    def start(self):
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
        self._container: DockerPyContainer = client.containers.run(
            image_tag,
            environment=self.env,
            ports={f'{source}/tcp': dest for source, dest in self.ports.items()},
            detach=True,
            auto_remove=True,
            volumes=self.volumes,
        )
        self._container = client.containers.get(self._container.id)
        self.port_map = {
            source: int(self._container.ports[f'{source}/tcp'][0]['HostPort'])
            for source, dest in self.ports.items()
        }
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
        return self

    def stop(self):
        if self._container is not None:
            self._container.stop(timeout=0)
            del self._container
