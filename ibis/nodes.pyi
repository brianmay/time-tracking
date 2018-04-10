from typing import Any, Callable, Optional, TypeVar

T = TypeVar('T')

def register(tag: str, end_tag: Optional[str]) -> Callable[[T], T]: ...

class Node:
    def render(self, context: Any) -> str: ...
