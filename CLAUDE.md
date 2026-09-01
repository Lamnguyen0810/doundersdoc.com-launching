# Working on FD AI with Claude Code

Read `README.md`, `PLAN.md` and `docs/Jessica_Backend_Proposal.md` first. `demo.py` is the in-memory demo; `app/` is the product. The proposal's week plan (§8) is the roadmap;
its data model (§4) matches `app/models.py`.

## Rules
- Python 3.12, FastAPI, SQLAlchemy 2.0 (sync), Jinja + HTMX. No new frameworks without a reason in the PR.
- The grade is deterministic (`app/llm/rubric.py`). Never let the model output a grade directly.
- All model calls go through `app/llm/client.call` so they are logged.
- Anything slower than ~5 s is a job (`app/jobs.py`), handled in `app/worker.py`.
- Every new table or column needs an Alembic migration (`alembic revision --autogenerate`).
- British spelling in UI copy. Plain English; the reader is a founder, not a lawyer.
- Run `ruff check app tests && pytest -q` before committing. Tests must not need an API key — stub `app.llm.client.client`.

## Product direction
FD AI is one assistant (`app/llm/prompts.py`) with a chat as the main surface. Review and Draft are the focus; do not build Ask/billing/handoff further until told.

## Next up (from the proposal)
1. Week 4 — move Ask to a job if latency grows; add citations.
2. Week 5 — Draft: `templates/` DOCX with placeholders, intake form, `python-docx` render.
3. Week 6 — Stripe Checkout + webhook (`/webhooks/stripe`), credits decrement per review, "Send to a lawyer" email.
4. Week 8 — tracked-change DOCX redlines (`w:ins`/`w:del`).
