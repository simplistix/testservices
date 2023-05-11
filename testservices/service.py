from typing import Type, Optional, Any


class Service:

    def available(self) -> bool:
        """
        Returns ``True`` if this service can be used.
        """
        return True

    def start(self) -> None:
        """
        Do any work needed to start this service.
        """

    def get(self) -> Any:
        """
        Return an object that makes most sense to use this service.
        This method may be called many times during the life of the service.
        """
        return self

    def stop(self):
        """
        Do any work needed to stop this service and clean up anything required.
        """

    def __enter__(self):
        self.start()
        return self.get()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class Dependency:
    service: Type[Service]
    name: Optional[str]
