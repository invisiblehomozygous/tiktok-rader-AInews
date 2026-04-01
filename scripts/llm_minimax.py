"""
MiniMax LLM Client Implementation

Uses Anthropic SDK format to call MiniMax API.
"""

import time
import threading
import hashlib
from pathlib import Path
import anthropic
from llm_client import LLMClient, LLMError, LLMRateLimitError, LLMInvalidResponseError


class MiniMaxClient(LLMClient):
    """
    MiniMax API client using Anthropic SDK compatibility layer.
    
    Model: MiniMax-M2.5-highspeed
    Base URL: https://api.minimax.io/anthropic
    """
    
    DEFAULT_BASE_URL = "https://api.minimax.io/anthropic"
    DEFAULT_MODEL = "MiniMax-M2.5-highspeed"
    
    def __init__(self, api_key: str, base_url: str = None, model: str = None):
        """
        Initialize MiniMax client.
        
        Args:
            api_key: MiniMax API key
            base_url: Optional override for API endpoint
            model: Optional model override
        """
        if not api_key:
            raise ValueError("API key is required")
            
        self.api_key = api_key
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        
        try:
            self.client = anthropic.Anthropic(
                base_url=self.base_url,
                api_key=api_key
            )
        except Exception as e:
            raise LLMError(f"Failed to initialize MiniMax client: {e}")
    
    def get_model_name(self) -> str:
        """Return model identifier."""
        return self.model
    
    def call(self, system_prompt: str, user_prompt: str, max_tokens: int = 15000, **kwargs) -> str:
        """
        Call MiniMax API.
        
        Args:
            system_prompt: System instructions
            user_prompt: User query
            max_tokens: Max tokens to generate
            temperature: Optional temperature (default 0.7)
            
        Returns:
            Response text
            
        Raises:
            LLMRateLimitError: On rate limiting
            LLMError: On other API failures
        """
        temperature = kwargs.get('temperature', 0.7)
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            }
                        ]
                    }
                ]
            )
            
            # Extract content from response
            content_blocks = message.content
            response_text = ""
            
            for block in content_blocks:
                if block.type == "text":
                    response_text += block.text
                elif block.type == "thinking":
                    # Skip thinking blocks
                    pass
            
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
            index_content = f"[{seq}] {ts} | model={self.model} | user_prompt_len={len(user_prompt)} chars | response_len={len(response_text)} chars | {debug_file.name}\n"
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
                f.write(response_text)
                f.write("\n=== END ===\n")
            
            return response_text
            
        except anthropic.RateLimitError as e:
            raise LLMRateLimitError(f"MiniMax rate limit exceeded: {e}")
        except anthropic.APIError as e:
            raise LLMError(f"MiniMax API error: {e}")
        except Exception as e:
            raise LLMError(f"Unexpected error calling MiniMax: {e}")


def create_minimax_client(api_key: str) -> MiniMaxClient:
    """Factory function for creating MiniMax client."""
    return MiniMaxClient(api_key)
