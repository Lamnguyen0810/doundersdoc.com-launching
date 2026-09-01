"""Runs upload → job → worker → review end to end with the model call stubbed out."""
from types import SimpleNamespace

from app.llm.rubric import RUBRIC
from tests.test_smoke import make_docx

FAKE_REVIEW = {
    "document_type": "Adviser agreement",
    "summary": "A short adviser agreement with a generous, uncliffed equity grant.",
    "issues": [
        {
            "clause_ref": "2.2", "title": "No vesting cliff", "severity": "high",
            "explanation": "Options vest from month one, so a departing adviser keeps equity.",
            "market_position": "A 3–6 month cliff is usual for adviser grants.",
            "current_wording": "vest monthly over 24 months with no cliff",
            "proposed_wording": "vest monthly over 24 months, subject to a 3-month cliff",
        },
        {
            "clause_ref": "7", "title": "Short notice", "severity": "low",
            "explanation": "30 days is workable but short.", "market_position": "Common.",
            "current_wording": "30 days' written notice", "proposed_wording": "60 days' written notice",
        },
    ],
    "rubric": [{"key": r["key"], "score": 3, "reason": "ok"} for r in RUBRIC],
}


class FakeMessages:
    """Stands in for anthropic.Anthropic().messages so the logging wrapper still runs."""

    def create(self, **kwargs):
        if kwargs.get("tool_choice"):
            content = [SimpleNamespace(type="tool_use", input=FAKE_REVIEW)]
        else:
            content = [SimpleNamespace(type="text", text="Dear counterparty, could we add a 3-month cliff?")]
        usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0)
        return SimpleNamespace(content=content, usage=usage)


def test_worker_completes_review(client, monkeypatch):
    import app.llm.client as llm_client
    from app import worker
    from app.db import SessionLocal
    from app.jobs import claim, finish
    from app.models import Job, LLMCall

    monkeypatch.setattr(llm_client, "client", lambda: SimpleNamespace(messages=FakeMessages()))

    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    r = client.post("/documents", files={"file": ("a.docx", make_docx(), mime)},
                    data={"perspective": "the company"}, follow_redirects=False)
    job_id = r.headers["location"].split("job=")[1]

    db = SessionLocal()
    job = claim(db)
    assert job and job.id == job_id and job.status == "running"
    finish(db, job, worker.handle_review(db, job))
    db.refresh(job)
    assert job.status == "done"
    assert job.result["letter"] == "B" and job.result["grade"] == 75

    status = client.get(f"/jobs/{job_id}")
    assert "Review ready" in status.text
    page = client.get(f"/reviews/{job.result['review_id']}")
    assert page.status_code == 200
    assert "No vesting cliff" in page.text and "3-month cliff" in page.text
    assert db.query(LLMCall).count() == 2  # review + email, both logged
    assert db.query(Job).filter_by(status="queued").count() == 0
    db.close()
