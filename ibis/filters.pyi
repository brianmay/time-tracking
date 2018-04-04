from typing import Callable, TypeVar

T = TypeVar('T')

def register(name: str) -> Callable[[T], T]: ...
