from pydantic import BaseModel, ConfigDict, Field


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "unavailable"
    model: str | None = None
    temperature: float = Field(default=0.0, ge=0, le=2)

