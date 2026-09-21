from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.services.news_normalizer import safe_url


class SourceEntryError(ValueError):
    pass


class SourceDefinition(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,127}$")
    name: str = Field(min_length=1, max_length=200)
    publisher: str = Field(min_length=1, max_length=200)
    homepage: str
    country: str = Field(min_length=2, max_length=8)
    region: Literal["world", "china", "us", "japan", "europe", "asia", "middle-east", "africa", "oceania", "americas"]
    language: str = Field(pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")
    category: Literal["world", "politics", "business", "technology", "science", "health", "climate", "culture", "sports"]
    source_type: Literal["official_rss", "rsshub"] = "official_rss"
    feed_url: str = ""
    rsshub_path: str | None = None
    enabled: bool = True
    priority: int = Field(100, ge=1, le=1000)
    notes: str | None = None
    user_agent: str | None = None
    crawler: bool = False
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("homepage")
    @classmethod
    def homepage_is_url(cls, value):
        if not safe_url(value):
            raise ValueError("homepage requires HTTP(S) URL without credentials")
        return value

    @model_validator(mode="after")
    def feed_is_valid(self):
        if self.source_type == "official_rss" and not safe_url(self.feed_url):
            raise ValueError("official_rss requires HTTP(S) feed_url")
        if self.source_type == "rsshub" and (not self.rsshub_path or not self.rsshub_path.startswith("/") or self.rsshub_path.startswith("//") or ".." in self.rsshub_path):
            raise ValueError("rsshub requires an absolute local route path")
        return self


class SourcesFile(BaseModel):
    version: Literal[1] = 1
    sources: list[SourceDefinition]

    @model_validator(mode="after")
    def unique_sources(self):
        ids = [s.id for s in self.sources]
        urls = [s.feed_url if s.source_type == "official_rss" else s.rsshub_path for s in self.sources]
        if len(set(ids)) != len(ids) or len(set(urls)) != len(urls):
            raise ValueError("Duplicate source id or feed URL")
        return self


def load_sources(path: str | Path = "config/sources.yaml") -> list[SourceDefinition]:
    try:
        with Path(path).open(encoding="utf-8") as f:
            return SourcesFile.model_validate(yaml.safe_load(f)).sources
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise SourceEntryError(f"Invalid source registry: {type(exc).__name__}") from exc


def source_domain(url: str) -> str:
    return urlsplit(url).hostname or ""