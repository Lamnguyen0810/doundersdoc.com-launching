"""
Review pipeline. One structured call extracts issues and rubric scores (forced tool use with
a strict schema, so the output is always valid JSON); code computes the grade; a second small
call drafts the negotiation email from the issues alone (no document re-read).
"""
from sqlalchemy.orm import Session

from app.config import settings
from app.llm.client import call, document_block
from app.llm.rubric import RUBRIC, compute_grade
from app.parsing import clauses_to_text

SYSTEM = """You are Jessica, the contract-review assistant of Founders Doc, a Singapore law firm
serving startups from pre-seed to Series C. You review contracts from the stated party's
perspective, in plain English, for founders who are not lawyers. You are precise about clause
references, you distinguish what is unusual from what is merely unfavourable, and you never
invent clauses that are not in the document. You are not giving legal advice; you are helping
the reader understand the document and decide what to negotiate or send to a lawyer."""

REVIEW_TOOL = {
    "name": "record_review",
    "description": "Record the structured review of the contract.",
    "input_schema": {
        "type": "object",
        "properties": {
            "document_type": {"type": "string", "description": "e.g. Adviser agreement, NDA, SaaS MSA"},
            "summary": {"type": "string", "description": "3–4 sentences a founder can read in 20 seconds."},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "clause_ref": {"type": "string"},
                        "title": {"type": "string"},
                        "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                        "explanation": {"type": "string", "description": "Why it matters to this party."},
                        "market_position": {
                            "type": "string",
                            "description": "How this compares with what is usual for this document type.",
                        },
                        "current_wording": {"type": "string"},
                        "proposed_wording": {"type": "string"},
                    },
                    "required": [
                        "clause_ref", "title", "severity", "explanation",
                        "market_position", "current_wording", "proposed_wording",
                    ],
                },
            },
            "rubric": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "enum": [r["key"] for r in RUBRIC]},
                        "score": {"type": "integer", "minimum": 0, "maximum": 4},
                        "reason": {"type": "string"},
                    },
                    "required": ["key", "score", "reason"],
                },
            },
        },
        "required": ["document_type", "summary", "issues", "rubric"],
    },
}


def run_review(db: Session, *, job_id: str, clauses: list[dict], perspective: str) -> dict:
    doc_text = clauses_to_text(clauses)
    rubric_lines = "\n".join(f"- {r['key']}: {r['label']}" for r in RUBRIC)

    instructions = f"""Review this contract from the perspective of: {perspective}.

1. Identify every issue worth raising, ranked by severity. Quote the current wording exactly
   and propose replacement wording that a reasonable counterparty could accept.
2. Score each rubric item from 0 (seriously harmful or missing where expected) to 4 (protective
   and market-standard) for this party, with a one-sentence reason:
{rubric_lines}
3. Give a short summary.

Use the record_review tool for your entire answer."""

    msg = call(
        db,
        purpose="review",
        job_id=job_id,
        model=settings.CLAUDE_MODEL_REVIEW,
        max_tokens=8000,
        system=SYSTEM,
        tools=[REVIEW_TOOL],
        tool_choice={"type": "tool", "name": "record_review"},
        messages=[{"role": "user", "content": [document_block(doc_text), {"type": "text", "text": instructions}]}],
    )
    tool_use = next(b for b in msg.content if b.type == "tool_use")
    data = tool_use.input

    scores = {r["key"]: r["score"] for r in data["rubric"]}
    grade, letter = compute_grade(scores)
    order = {"high": 0, "medium": 1, "low": 2}
    issues = sorted(data["issues"], key=lambda i: order.get(i["severity"], 3))

    email = draft_negotiation_email(db, job_id=job_id, issues=issues, perspective=perspective,
                                    document_type=data["document_type"])

    return {
        "document_type": data["document_type"],
        "summary": data["summary"],
        "issues": issues,
        "rubric": data["rubric"],
        "grade": grade,
        "letter": letter,
        "email_draft": email,
    }


def draft_negotiation_email(db: Session, *, job_id: str, issues: list[dict], perspective: str,
                            document_type: str) -> str:
    top = [i for i in issues if i["severity"] in ("high", "medium")][:6]
    if not top:
        return ""
    bullet = "\n".join(f"- Clause {i['clause_ref']} ({i['title']}): propose \"{i['proposed_wording']}\"" for i in top)
    prompt = f"""Draft a short, courteous negotiation email from {perspective} to the counterparty
about this {document_type}. Ask for the following changes, grouped sensibly, without legal jargon,
and end by offering a call. Do not add issues not listed. Plain text, no subject line.

{bullet}"""
    msg = call(
        db,
        purpose="negotiation_email",
        job_id=job_id,
        model=settings.CLAUDE_MODEL_ASK,
        max_tokens=1200,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if b.type == "text").strip()
