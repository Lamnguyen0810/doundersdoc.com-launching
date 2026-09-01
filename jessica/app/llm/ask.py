"""Ask: a question against the cached document. Answers must reference clause numbers."""
from sqlalchemy.orm import Session

from app.config import settings
from app.llm.client import call, document_block
from app.llm.review import SYSTEM
from app.parsing import clauses_to_text


def answer(db: Session, *, job_id: str | None, clauses: list[dict], history: list[dict], question: str) -> str:
    doc_text = clauses_to_text(clauses)
    first = {
        "role": "user",
        "content": [
            document_block(doc_text),
            {
                "type": "text",
                "text": (
                    "Answer questions about this document only. Cite clause references in square "
                    "brackets, e.g. [2.1]. If the document does not address the question, say so."
                ),
            },
        ],
    }
    ack = {"role": "assistant", "content": "Understood. Ask me anything about this document."}
    msgs = [first, ack] + [{"role": m["role"], "content": m["content"]} for m in history]
    msgs.append({"role": "user", "content": question})
    msg = call(
        db,
        purpose="ask",
        job_id=job_id,
        model=settings.CLAUDE_MODEL_ASK,
        max_tokens=1500,
        system=SYSTEM,
        messages=msgs,
    )
    return "".join(b.text for b in msg.content if b.type == "text").strip()
