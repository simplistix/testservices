from typing import Mapping

from .service import Service


class Collection:

    services: Mapping[str, Service]
