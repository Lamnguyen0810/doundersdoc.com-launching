# Jessica — FD AI backend

The contract review, draft and ask backend for [Founders Doc](https://foundersdoc.com). FastAPI + HTMX,
Postgres-as-queue worker, Claude API, Supabase for auth/storage, Fly.io in Singapore.

Architecture and rationale: [`docs/Jessica_Backend_Proposal.md`](docs/Jessica_Backend_Proposal.md).

## What works today (week-1 scaffold)

- Upload a DOCX/PDF/TXT → clauses parsed and stored
- Anonymous upload before sign-up; documents re-parented on first login
- Background **Review** job: structured issues, lawyer-owned rubric → deterministic grade, negotiation email
- **Ask** the document (signed-in users), with clause references
- Magic-link sign-in via Supabase Auth
- Retention: anonymous documents purged after 24 h, signed-in after 30 days; manual delete
- Audit log and per-call LLM usage log
- Tests run with no API key (model stubbed) — CI on every push, deploy on `main`

Not yet: Draft (templates), Stripe, lawyer handoff, tracked-change DOCX. See the week plan in the proposal.

## Run locally (5 minutes)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # defaults use SQLite + local storage; add ANTHROPIC_API_KEY to run real reviews
uvicorn app.main:app --reload   # http://localhost:8000
python -m app.worker            # second terminal — runs the review jobs
pytest -q
```

Without `ANTHROPIC_API_KEY` uploads still work; the worker will fail the review job with a clear error.

## Launch it (GitHub → Supabase → Fly)

### 1. Push to GitHub

```bash
git init && git add -A && git commit -m "Jessica backend scaffold"
gh repo create foundersdoc/jessica --private --source=. --push   # or create the repo in the GitHub UI and push
```

### 2. Supabase (Singapore)

1. Create a project — **Region: Southeast Asia (Singapore)**.
2. **Authentication → Providers → Email**: enable, keep "Confirm email" on (magic links).
   **Authentication → URL configuration**: add `https://<your-app>.fly.dev/auth/login` and `http://localhost:8000/auth/login` to redirect URLs.
3. **Storage**: create a bucket named `documents`, **private**.
4. Copy from **Project Settings → API**: Project URL, `anon` key, `service_role` key.
5. Copy from **Project Settings → Database**: the **Session pooler** connection string; change the prefix to `postgresql+psycopg://`.

### 3. Database schema

```bash
# with DATABASE_URL in .env pointing at Supabase
alembic revision --autogenerate -m "initial"
alembic upgrade head
git add alembic/versions && git commit -m "initial migration"
```

### 4. Fly.io

```bash
fly auth login
fly launch --no-deploy --copy-config --name jessica-ai --region sin   # accept fly.toml as-is
fly secrets set \
  SECRET_KEY="$(openssl rand -hex 32)" \
  DATABASE_URL="postgresql+psycopg://..." \
  SUPABASE_URL="https://xxx.supabase.co" \
  SUPABASE_ANON_KEY="..." \
  SUPABASE_SERVICE_KEY="..." \
  ANTHROPIC_API_KEY="sk-ant-..." \
  BASE_URL="https://jessica-ai.fly.dev"
fly deploy
fly scale count web=1 worker=1
```

### 5. Continuous deploy from GitHub

`fly tokens create deploy -x 999999h` → add the value as the repository secret **`FLY_API_TOKEN`**.
Every push to `main` now runs tests, then deploys.

### 6. Point the domain

`fly certs add app.foundersdoc.ai`, then add the CNAME it gives you. Set `BASE_URL` accordingly and add the
new URL to Supabase redirect URLs. Finally, wire the landing page dropzone at `foundersdoc.ai` to
`POST https://app.foundersdoc.ai/documents` (see the launcher proposal in `docs/`).

## Project layout

```
app/
  main.py          FastAPI app, middleware, routers
  config.py        settings from .env
  db.py models.py  SQLAlchemy 2.0 models (see proposal §4)
  auth.py          Supabase JWT verification, anonymous sessions
  storage.py       Supabase Storage / local files
  parsing.py       DOCX/PDF → clauses
  jobs.py          Postgres queue (SKIP LOCKED)
  worker.py        worker process entry point
  retention.py     expiry + purge
  llm/             client wrapper, rubric, review, ask
  routers/         pages, auth, documents
  templates/       Jinja + HTMX
alembic/           migrations
tests/             pytest; model calls are stubbed
docs/              proposals
```

## Conventions

- The grade is computed in `app/llm/rubric.py`, never by the model. Lawyers edit weights there.
- Every model call goes through `app/llm/client.py` so it is logged to `llm_calls`.
- Long-running work is a job. Nothing over ~5 s runs inside a request.
- Model IDs live in `.env` (`CLAUDE_MODEL_REVIEW`, `CLAUDE_MODEL_ASK`), not in code.
