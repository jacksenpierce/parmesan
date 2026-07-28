from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CorpusHead(BaseModel):
    """Portable compare-and-swap identity for one authoritative corpus state."""

    model_config = ConfigDict(extra="forbid", strict=True)

    corpus_id: str
    snapshot_uuid: str
    database_sequence: int = Field(ge=0)

    def semantic_key(self) -> tuple[str, str, int]:
        return self.corpus_id, self.snapshot_uuid, self.database_sequence
