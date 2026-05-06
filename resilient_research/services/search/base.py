"""Abstract base class for all search providers."""

from abc import ABC, abstractmethod


class AbstractSearchProvider(ABC):
    """All search providers must implement this interface."""

    name: str = "base"

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[str]:
        """Return a list of result URLs matching *query*."""
        ...
