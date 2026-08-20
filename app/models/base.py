from abc import ABC, abstractmethod

class BaseModelProvider(ABC):
    """Base abstract interface for all SERA model providers."""
    
    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if provider credentials and endpoints are valid."""
        pass
