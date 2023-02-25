from typing import List

from .provider import Provider
from .supplier import Supplier


class Service:
    name: str
    providers: List[Provider]
    suppliers: List[Supplier]
