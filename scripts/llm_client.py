"""
LLM Client Interface

Abstract base class defining the contract for LLM implementations.
Callers use call_llm(), implementations provide the actual HTTP logic.

Pattern: Linux VFS-style interface (struct file_operations)
- Interface is explicit (ABC)
- Implementations are swappable
- Callers don't know which implementation they're using
"""

from abc import ABC, abstractmethod
from typing import Optional


class LLMClient(ABC):
    """
    Abstract base class for LLM clients.
    
    Similar to Linux's struct file_operations - defines the contract
    that all LLM implementations must satisfy.
    """
    
    @abstractmethod
    def call(self, system_prompt: str, user_prompt: str, max_tokens: int = 8000, **kwargs) -> str:
        """
        Call the LLM with system and user prompts.
        
        Args:
            system_prompt: System instructions/context
            user_prompt: The actual query/content
            max_tokens: Maximum tokens to generate
            **kwargs: Implementation-specific options
            
        Returns:
            Response text from the LLM
            
        Raises:
            LLMError: On API failure, rate limiting, etc.
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier for logging/debugging."""
        pass


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded - caller should retry with backoff."""
    pass


class LLMInvalidResponseError(LLMError):
    """Response parsing failed - malformed JSON or unexpected format."""
    pass


class LLMConfigError(LLMError):
    """Configuration error - missing API key, invalid base URL, etc."""
    pass


def call_llm(client: LLMClient, system_prompt: str, user_prompt: str, 
             max_tokens: int = 8000, **kwargs) -> str:
    """
    Universal entry point for LLM calls.
    
    This is the VFS layer - callers use this, not implementation classes directly.
    
    Args:
        client: LLMClient implementation instance
        system_prompt: System instructions/context
        user_prompt: The actual query/content
        max_tokens: Maximum tokens to generate
        **kwargs: Implementation-specific options
        
    Returns:
        Response text from the LLM
    """
    return client.call(system_prompt, user_prompt, max_tokens, **kwargs)
