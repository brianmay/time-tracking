from typing import Any, Callable, Optional, TypeVar

T = TypeVar('T')

def register(tag: str, end_tag: Optional[str]) -> Callable[[T], T]: ...

class Node:
    def render(self, context: Any) -> str: ...

class Expression:
    def __init__(self, expr: str) -> None: ...
    def eval(self, contact: Any) -> str: ...
