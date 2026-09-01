# FD AI — development plan

*From today's demo to a product founders pay for. One builder, Python.*

**Current focus (decided 1 Sep 2026):** make **Review** and **Draft** excellent. FD AI is one assistant with a free-form chat
as its primary surface; Review and Draft are things it can do, not separate products. Ask, billing, accounts and the lawyer
handoff stay scaffolded until these two are right.

The repository already contains two entry points that share the same parser and review pipeline:

| Entry point | 🎯 Purpose | 💾 State | 🔐 Auth | ▶️ Run |
|---|---|---|---|---|
| `demo.py` | Show it working today | In memory, lost on restart | None | `uvicorn demo:app` |
| `app/` | The real product | Postgres via SQLAlchemy | Supabase | `uvicorn app.main:app` + `python -m app.worker` |

Everything below moves features from the first column to the second. The demo is never thrown away — it stays as the quickest way to try a prompt or rubric change.

---

## Stage 0 — Demo (today)

| ✅ Have | 📌 To show |
|---|---|
| Upload DOCX/PDF → clauses | The "Or try the sample adviser agreement" button — a full review in one click |
| Live review with `ANTHROPIC_API_KEY`, canned review without | Grade, ranked issues with current vs proposed wording, the rubric that produced the grade, the negotiation email |
| FD AI chat with streaming; drafts export to .docx | Click **Draft an NDA** — a full agreement in ~20 s, assumptions in [brackets], then "Download as .docx" |
| Sample adviser agreement with eight deliberate problems | Point at clause 3 (adviser can stall fundraising) — the kind of thing a founder misses |

**Demo script (3 minutes):** open `/` → click the sample button → while it runs, explain that the grade is computed from a lawyer-written rubric, not asked of the model → open the review → scroll to the email → say "this is the free first review; the button after it is *Send to a lawyer*."

---

## Stage 1 — Make the review trustworthy (weeks 1–2)

Nothing else matters until the output is right on real documents. Do this in `demo.py`; it is the fastest loop.

| # | 🔨 Task | ✅ Done when |
|---|---|---|
| 1.1 | Collect 15–20 real contracts the firm has reviewed (adviser, NDA, SaaS/services, CARE/SAFE) | Folder of anonymised DOCX/PDF |
| 1.2 | A lawyer scores each with the rubric in `app/llm/rubric.py`; adjust weights and item wording until the rubric *reads* like the firm's view | Rubric signed off by a lawyer |
| 1.3 | Run all documents through the demo; compare Jessica's grade and top three issues with the lawyer's | Agreement on grade band (±1 letter) for ≥ 80% |
| 1.4 | Tune the system prompt and tool schema in `app/llm/review.py` for the misses; add a "document type" hint so NDAs are not judged like MSAs | Re-run 1.3 |
| 1.5 | Add a tiny eval script `scripts/eval_reviews.py` that runs the folder and prints a table | One command shows regressions |

---

## Stage 2 — Persist and sign in (weeks 3–4)

Switch the demo's dictionaries for the tables that already exist in `app/models.py`.

| # | 🔨 Task | ✅ Done when |
|---|---|---|
| 2.1 | Create the Supabase project (Singapore); run `alembic revision --autogenerate && alembic upgrade head` | Tables exist |
| 2.2 | Run `app/` locally against it; upload → worker → review works with a real database | Same flow as the demo, but it survives a restart |
| 2.3 | Magic-link sign-in (already coded in `routers/auth.py`); confirm the anonymous-upload → sign-in → document re-parenting path | Upload anonymously, sign in, document is yours |
| 2.4 | Deploy to Fly.io (`fly.toml` is ready; README §4) with GitHub Actions deploying on `main` | `https://<app>.fly.dev` runs a review |
| 2.5 | Retention job and manual delete verified in production | Anonymous document disappears after 24 h |

---

## Stage 3 — Draft, properly (weeks 5–6)

| # | 🔨 Task | ✅ Done when |
|---|---|---|
| 3.1 | Chat + drafting already work in `demo.py` via `app/llm/chat.py`; port to `app/` with `messages` persisted per chat | Conversations survive a restart |
| 3.2 | Lawyers supply two DOCX templates — NDA and services agreement — with `{{placeholders}}` and optional clause blocks | Templates in `templates/` |
| 3.3 | Give the assistant the templates as tools: when a user asks for an NDA it drafts *from the firm's template*, not from scratch | Drafts match the firm's house style |
| 3.4 | Guard-rail: the model may only use clauses in the firm's library | A test asserting no foreign clauses |

---

## Stage 4 — Money and handoff (week 7)

| # | 🔨 Task | ✅ Done when |
|---|---|---|
| 4.1 | Stripe Checkout + `/webhooks/stripe`; credits decrement per review (first review free) | Someone pays and gets credits |
| 4.2 | "Send to a lawyer": `matters` row + email to the firm with the document and review | Firm receives a handoff |
| 4.3 | Privacy policy and terms updated: Singapore storage, model-provider processing, retention | Live on the site |

---

## Stage 5 — Launch (week 8)

| # | 🔨 Task | ✅ Done when |
|---|---|---|
| 5.1 | Wire the `foundersdoc.ai` landing page dropzone to `POST app.foundersdoc.ai/documents` | Landing → review with no second landing |
| 5.2 | Repoint the four "Launch FD AI" buttons per `docs/FD_Launcher_Proposal.md` | Done |
| 5.3 | Closed beta with ten founders; Sentry on; watch `llm_calls` for cost per review | Ten reviews, cost known, grades sane |
| 5.4 | Tracked-change DOCX redlines (nice-to-have; ship after launch if it slips) | Download opens in Word with changes marked |

---

## Deliberately skipped until there is traction

| ❌ Not now | 🔜 Trigger to revisit |
|---|---|
| Vector database / multi-document search | Users ask questions across several contracts |
| React/Next frontend | A designer or second engineer joins |
| Word add-in | Web product has paying users |
| Fine-tuning | A few hundred lawyer-scored reviews exist |
| In-region model hosting | A client contract requires it (the LLM client is isolated, so it is a swap) |

---

## How to work day to day

1. Prompt or rubric change → run `demo.py`, click the sample, judge the output. Thirty-second loop.
2. Feature work → `app/`, with `ruff check app tests && pytest -q` before every commit. Tests stub the model.
3. Anything that touches a table → Alembic migration in the same commit.
4. Use Claude Code inside the repo for the build; `CLAUDE.md` carries these rules so it follows them.
