"""
OpenRouter LLM Client Implementation

Uses the official OpenAI client library (OpenRouter is OpenAI-compatible).
This is the recommended approach per OpenRouter docs.
"""

import time
import threading
import hashlib
from pathlib import Path
from openai import OpenAI, APIError, RateLimitError
from llm_client import LLMClient, LLMError, LLMRateLimitError, LLMInvalidResponseError


class OpenRouterClient(LLMClient):
    """
    OpenRouter API client using the official OpenAI library.
    
    Provides access to multiple models through OpenRouter's unified API.
    Default model: anthropic/claude-3.5-sonnet
    """
    
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"
    
    def __init__(self, api_key: str, base_url: str = None, model: str = None, 
                 site_url: str = None, site_name: str = None):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key
            base_url: Optional override for API endpoint
            model: Optional model override (e.g., "anthropic/claude-3-opus")
            site_url: Your site URL for OpenRouter rankings
            site_name: Your site name for OpenRouter rankings
        """
        if not api_key:
            raise ValueError("API key is required")
            
        self.api_key = api_key
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self.site_url = site_url
        self.site_name = site_name
        
        # Create OpenAI client pointing to OpenRouter
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=api_key,
        )
    
    def get_model_name(self) -> str:
        """Return model identifier."""
        return self.model
    
    def call(self, system_prompt: str, user_prompt: str, max_tokens: int = 15000, **kwargs) -> str:
        """
        Call OpenRouter API.
        
        Args:
            system_prompt: System instructions
            user_prompt: User query
            max_tokens: Max tokens to generate
            temperature: Optional temperature (default 0.7)
            
        Returns:
            Response text
            
        Raises:
            LLMRateLimitError: On rate limiting (429)
            LLMError: On other API failures
        """
        temperature = kwargs.get('temperature', 0.7)
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Optional headers for OpenRouter rankings
        extra_headers = {}
        if self.site_url:
            extra_headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            extra_headers["X-Title"] = self.site_name
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                extra_headers=extra_headers if extra_headers else None
            )
            
            content = completion.choices[0].message.content
            
            if not content:
                raise LLMInvalidResponseError("Empty content in OpenRouter response")
            
            # Debug: log raw response to run-specific directory
            ts = time.strftime("%Y%m%d_%H%M%S")
            # Thread-safe call counter
            if not hasattr(self, '_call_counter'):
                self._call_counter = 0
            with threading.Lock():
                self._call_counter += 1
                seq = self._call_counter
            sig = f"{self.model[:20]}|{len(system_prompt)}|{len(user_prompt)}"
            h = hashlib.md5(sig.encode()).hexdigest()[:8]
            debug_dir = Path(__file__).parent / "llm_raw_responses" / f"{ts}"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / f"call_{seq:03d}_{h}.txt"
            # Also update index
            index_file = debug_dir / "_index.txt"
            index_content = f"[{seq}] {ts} | model={self.model} | user_prompt_len={len(user_prompt)} chars | response_len={len(content)} chars | {debug_file.name}\n"
            if index_file.exists():
                with open(index_file, 'a', encoding='utf-8') as idx:
                    idx.write(index_content)
            else:
                with open(index_file, 'w', encoding='utf-8') as idx:
                    idx.write(index_content)
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(f"Model: {self.model} | max_tokens: {max_tokens} | temperature: {temperature}\n")
                f.write(f"Timestamp: {ts} | Call seq: {seq}\n\n")
                f.write("=== SYSTEM PROMPT (first 500 chars) ===\n")
                f.write(system_prompt[:500])
                f.write("\n\n=== USER PROMPT (first 500 chars) ===\n")
                f.write(user_prompt[:500])
                f.write("\n\n=== RAW RESPONSE ===\n")
                f.write(content)
                f.write("\n=== END ===\n")
            
            return content
            
        except RateLimitError as e:
            raise LLMRateLimitError(f"OpenRouter rate limit exceeded: {e}")
        except APIError as e:
            raise LLMError(f"OpenRouter API error: {e}")
        except Exception as e:
            raise LLMError(f"Unexpected error calling OpenRouter: {e}")


def create_openrouter_client(api_key: str, model: str = None) -> OpenRouterClient:
    """Factory function for creating OpenRouter client."""
    return OpenRouterClient(api_key, model=model)
