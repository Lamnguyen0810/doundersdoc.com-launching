"""Thin wrapper around the Anthropic SDK that records every call to llm_calls."""
import time

import anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LLMCall

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def call(db: Session, *, purpose: str, job_id: str | None, **kwargs) -> anthropic.types.Message:
    t0 = time.perf_counter()
    msg, ok = None, 1
    try:
        msg = client().messages.create(**kwargs)
        return msg
    except Exception:
        ok = 0
        raise
    finally:
        latency = int((time.perf_counter() - t0) * 1000)
        usage = getattr(msg, "usage", None)
        db.add(
            LLMCall(
                job_id=job_id,
                purpose=purpose,
                model=kwargs.get("model", ""),
                tokens_in=getattr(usage, "input_tokens", 0) or 0,
                tokens_out=getattr(usage, "output_tokens", 0) or 0,
                cached_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                latency_ms=latency,
                ok=ok,
            )
        )
        db.commit()


def document_block(text: str) -> dict:
    """The contract goes in one cached block so Review, email and Ask all reuse it."""
    return {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}
