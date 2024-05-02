import json
from abc import ABC
from functools import cached_property
from pprint import pformat
from time import sleep
from typing import Optional, Sequence, Dict, Any
from docker import DockerClient
from docker.errors import ImageNotFound, DockerException, NotFound
from docker.models.containers import Container as DockerPyContainer
from docker.models.images import Image

from ..service import Service, T


class ContainerFailed(Exception):

    def __init__(self, name: str, image_tag: str, reason: str, logs: bytes):
        self.name = name
        self.image_tag = image_tag
        self.reason = reason
        self.logs = logs

    def __str__(self) -> str:
        logs = self.logs.decode(errors='replace')
        return f'name={self.name}\nimage={self.image_tag}\nreason={self.reason}\nlogs:\n{logs}'


class MisconfiguredContainer(Exception):
    """
    A container exists but its configuration doesn't match what's required.
    """


DEFAULT_START_WAIT = 0.05
DEFAULT_READY_POLL_WAIT = 0.01
DEFAULT_READY_TIMEOUT = 5

DOCKER_IO_PREFIX = 'docker.io/'


class ContainerImplementation(Service[T], ABC):

    _container: DockerPyContainer | None = None
    port_map: dict[int, int]

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
        self.image_tag = f'{self.image}:{self.version}'
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

    def _container_image(self, container: DockerPyContainer) -> Image:
        for attr in 'ImageID', 'Image':
            image_name = container.attrs.get(attr)
            if image_name is not None:
                break
        assert image_name is not None, 'neither ImageID or Image set?'
        # docker-py doesn't have this conditional, which means it goes wrong on podman:
        if image_name.startswith('sha256:'):
            _, image_name = image_name.split(':', 1)
        return self._client.images.get(image_name)

    def _image_has_tag(self, tag: str) -> bool:
        assert self._container is not None, 'Container not initialized'
        image = self._container_image(self._container)
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

    def _create_parameters(self) -> Dict[str, Any]:
        return dict(
            environment=self.env,
            ports={f'{source}/tcp': dest for source, dest in self.ports.items()},
            volumes=self.volumes,
            name=self.name,
        )

    def exists(self) -> bool:
        client = self._client
        container = None
        if self.name:
            matching = client.containers.list(filters={'name': self.name})
            if matching:
                container, = matching
        elif self._container is not None:
            if self._container:
                try:
                    container = client.containers.get(self._container.id)
                except NotFound:
                    pass
        if container is None:
            return False

        status = container.status
        if status != 'running':
            raise ContainerFailed(
                container.name,
                self.image_tag,
                reason=f'exists but {status=}',
                logs=container.logs(),
            )

        # check images matches:
        expected_image = client.images.get(self.image_tag)
        actual_image = self._container_image(container)
        if expected_image != actual_image:
            raise MisconfiguredContainer(
                f'image: expected={expected_image}, actual={actual_image}'
            )

        expected_params = self._create_parameters()
        attrs = container.attrs

        # check environment matches:
        expected_environment = expected_params.pop('environment')
        actual_environment = dict(row.split('=', 1) for row in attrs['Config']['Env'])
        bad_environment = {}
        for key, expected in expected_environment.items():
            actual = actual_environment.get(key)
            if expected != actual:
                bad_environment[key] = f'{expected=} {actual=}'
        if bad_environment:
            text = ', '.join(f'{key}: {text}' for (key, text) in bad_environment.items())
            raise MisconfiguredContainer(f'environment: {text}')

        # check ports match:
        expected_ports = expected_params.pop('ports')
        all_ports = {}
        for source, dest in container.ports.items():
            if source.endswith('/tcp') and dest is not None:
                all_ports[source] = dest[0]['HostPort']
        actual_ports = {}
        for source, dest in expected_ports.items():
            actual_port = all_ports.get(source)
            if actual_port is not None:
                actual_ports[source] = 0 if dest == 0 else actual_port
        if expected_ports != actual_ports:
            raise MisconfiguredContainer(
                f'ports:\n'
                f'expected={pformat(expected_ports)}\n'
                f'  actual={pformat(all_ports)}'
            )

        # check volumes match:
        expected_volumes = expected_params.pop('volumes')
        actual_volumes = {}
        for m in attrs['Mounts']:
            if m['Type'] == 'bind':
                if m['Mode']:
                    mode = m['Mode']
                else:
                    # podman:
                    mode = 'rw' if m['RW'] else 'ro'
                actual_volumes[m['Source']] = {'bind': m['Destination'], 'mode': mode}
        if expected_volumes != actual_volumes:
            raise MisconfiguredContainer(
                f'volumes:\n'
                f'expected=\n{json.dumps(expected_volumes, indent=4, sort_keys=True)}\n'
                f'  actual=\n{json.dumps(actual_volumes, indent=4, sort_keys=True)}'
            )

        expected_params.pop('name')
        assert not expected_params, f'unchecked parameters: {expected_params}'
        return container is not None

    def create(self) -> None:
        assert self._container is None
        client = self._client

        try:
            client.images.get(self.image_tag)
        except ImageNotFound:
            pull = True
        else:
            pull = False
        if pull or self.always_pull:
            client.images.pull(self.image, tag=self.version)

        params = self._create_parameters()
        self._container = _container = client.containers.create(self.image_tag, **params)
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
            raise ContainerFailed(_container.name, self.image_tag, reason, _container.logs())

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
