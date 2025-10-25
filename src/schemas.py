from __future__ import annotations
from pydantic import BaseModel, Field

class RunRequest(BaseModel):
    limit: int = Field(0, description="Max files to process this run (0 = all)")
