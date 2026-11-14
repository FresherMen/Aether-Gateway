import os
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class GatewaySettings(BaseSettings):
    """
    Central Configuration for Aether AI Gateway.
    Adheres to Twelve-Factor app principles by reading environment variables
    and .env files with strong type validation via Pydantic Settings.
    """
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server Settings
    GATEWAY_HOST: str = "0.0.0.0"
    GATEWAY_PORT: int = 8000
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Downstream LLM Provider API Keys & Routing
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq API Key for primary fast inference")
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API Key for primary/fallback")

    PRIMARY_PROVIDER: str = "groq"
    PRIMARY_MODEL: str = "llama-3.3-70b-versatile"

    FALLBACK_PROVIDER: str = "gemini"
    FALLBACK_MODEL: str = "gemini-3.5-flash-lite"

    # Semantic Cache Parameters
    CACHE_ENABLED: bool = True
    CACHE_SIMILARITY_THRESHOLD: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold (0.90 = highly strict semantic equivalence)"
    )
    CACHE_MAX_ENTRIES: int = 10000
    CACHE_TTL_SECONDS: int = 86400  # 24 hours
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Circuit Breaker & Fault-Tolerance Parameters
    CB_FAILURE_THRESHOLD: int = Field(
        default=3,
        description="Consecutive 429/5xx errors before tripping circuit to OPEN"
    )
    CB_RECOVERY_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        description="Time to wait in OPEN state before testing with HALF_OPEN probe"
    )
    CB_SUCCESS_THRESHOLD: int = Field(
        default=2,
        description="Successful probe calls required to heal and re-CLOSE circuit"
    )

    # Token-Bucket Rate Limiter Defaults (Per API Key / Tenant)
    DEFAULT_RPM: int = 60       # 60 Requests Per Minute
    DEFAULT_TPM: int = 40000    # 40,000 Tokens Per Minute
    USD_TO_INR_RATE: float = 87.0

    # Pricing Rate Cards (USD per 1,000,000 Tokens) for Real-Time Cost Attribution
    MODEL_PRICING: Dict[str, Dict[str, float]] = {
        "llama-3.3-70b-versatile": {
            "prompt_per_1m": 0.59,
            "completion_per_1m": 0.79
        },
        "gemini-3.5-flash-lite": {
            "prompt_per_1m": 0.075,
            "completion_per_1m": 0.30
        },
        "default": {
            "prompt_per_1m": 0.50,
            "completion_per_1m": 1.00
        }
    }

# Global Singleton Instance
settings = GatewaySettings()

