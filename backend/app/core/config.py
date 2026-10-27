"""Application configuration using Pydantic Settings v2."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017/?replicaSet=emrp-rs"
    mongo_db: str = "emrp"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT / Auth
    secret_key: str = "CHANGE_ME"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Routing
    osrm_url: str = "http://localhost:5000"

    # Environment
    environment: str = "development"
    log_level: str = "INFO"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003"]

    # Dispatch tunables
    offer_expiry_seconds: int = 15
    max_dispatch_radius_km: float = 15.0
    max_offer_rounds: int = 5

    # Voice IVR & Maps Integration
    gemini_api_key: str = ""
    emergency_hotline_number: str = "+91 11 4084 9108"
    google_maps_api_key: str = ""
    mapbox_access_token: str = ""

    # Hugging Face AI / Model Repo Integration
    hf_api_key: str = Field(default="", validation_alias="HF_TOKEN")
    hf_repo_id: str = "meta-llama/Llama-3.2-3B-Instruct"
    hf_inference_url: str = "https://api-inference.huggingface.co/models"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
