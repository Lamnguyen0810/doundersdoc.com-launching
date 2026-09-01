# Jessica AI — backend proposal for a solo Python build

*Draft for discussion · 1 September 2026*
*Constraints: one builder · Python · priorities in order: speed to launch → cost → SG/PDPA confidentiality → lawyer handoff*

---

## 1. Design principles

Because one person is building and running this, every choice below optimises for the smallest number of moving parts that can still deliver Review, Draft and Ask credibly.

| Principle | 🧭 What it means in practice |
|---|---|
| **One language, one repo** | FastAPI serves the API *and* the app UI (Jinja + HTMX). No separate frontend build, no second deploy pipeline |
| **Rent, don't run** | Managed Postgres, auth, storage, payments, email. You write product code, not infrastructure |
| **Two processes, not twelve** | A web process and a worker process. No microservices, no Kubernetes, no message broker |
| **The database is the queue** | Background jobs live in a Postgres table. Removes Redis entirely — one fewer bill, one fewer thing to break at 2 a.m. |
| **No vector database in v1** | A contract fits in the model's context window. Ask works by caching the whole document, not by retrieval. Add search only when multi-document matters arrive |
| **Lawyer-authored templates, model-adapted** | Draft never invents an NDA from nothing; it adapts the firm's own precedents. Faster to build, and it is what "backed by lawyers" should mean |

---

## 2. Architecture

```mermaid
flowchart LR
    subgraph Client
        L[foundersdoc.ai<br/>landing + dropzone]
        A[app.foundersdoc.ai<br/>HTMX UI]
    end

    subgraph Fly.io — Singapore
        W[FastAPI web]
        K[Worker<br/>polls jobs table]
    end

    subgraph Supabase — Singapore
        DB[(Postgres<br/>+ jobs table)]
        ST[(Storage<br/>uploaded docs)]
        AU[Auth]
    end

    C[Claude API]
    S[Stripe]
    R[Resend<br/>email]

    L -->|upload| W
    A --> W
    W --> DB
    W --> ST
    W --> AU
    W -->|enqueue| DB
    K -->|claim job| DB
    K --> ST
    K -->|Review · Draft · Ask| C
    W --> S
    K --> R
```

### 2.1 Component choices

| Layer | ✅ Choice | 💡 Why this over the alternatives |
|---|---|---|
| **Web framework** | FastAPI + Pydantic v2 + Jinja2 + HTMX | Async, typed, fast to write. HTMX gives an interactive app without a JavaScript build step |
| **Database** | Postgres on Supabase (region: Singapore) | Managed, backed up, in-region. Supabase also gives auth and storage from the same account |
| **Auth** | Supabase Auth (magic link + Google) | Zero password handling. FastAPI verifies the JWT; no session code to write |
| **File storage** | Supabase Storage (private bucket) | Encrypted at rest, signed URLs, in-region, same bill |
| **Background jobs** | Postgres `jobs` table + worker loop (`SELECT … FOR UPDATE SKIP LOCKED`) or the `procrastinate` library | A review takes 30–120 s; it cannot run inside the HTTP request. Postgres-as-queue needs no Redis |
| **Hosting** | Fly.io, `sin` region — one web machine, one worker machine | Cheap, in Singapore, scales by changing a number. Railway or Render are fine substitutes |
| **LLM** | Claude API via the Python SDK | Native PDF input, structured JSON outputs, prompt caching, citations — each removes code you would otherwise write. See §3 |
| **Payments** | Stripe Checkout + webhooks | Hosted checkout page, so no card data ever touches the server |
| **Email** | Resend (or Postmark) | Magic links, "your review is ready", lawyer handoff notifications |
| **Errors & logs** | Sentry + `structlog` | Free tiers cover a solo builder for a long time |
| **LLM observability** | An `llm_calls` table (prompt hash, tokens, latency, cost, model) | Enough to watch spend and debug quality without another vendor. Langfuse later if needed |
| **Migrations** | Alembic | Boring and correct |

### 2.2 What is deliberately *not* in v1

| ❌ Left out | 🔜 When to add it |
|---|---|
| Vector database / RAG | When users need to ask across many documents at once |
| Separate React/Next frontend | If a designer or second engineer joins |
| Redis, Celery, RabbitMQ | Probably never at this scale |
| Fine-tuned models | Never before there is labelled data from real reviews |
| Word add-in | After web traction — it is a second product |

---

## 3. The three AI workflows

All three share a single document-preparation step: upload → store → extract text with clause structure → cache in the model's context. Prompt caching matters here: the document is sent once and every subsequent Review, Ask or redline call reuses it, which is the biggest single cost lever available. See [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching).

### 3.1 Review

| Step | ⚙️ Implementation |
|---|---|
| **Input** | DOCX → `python-docx` (keeps paragraph/clause numbering); PDF → sent to the model directly using native [PDF support](https://platform.claude.com/docs/en/build-with-claude/pdf-support), with `pymupdf` text as a fallback |
| **Issue extraction** | One call with [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) against a fixed JSON schema: `issues[{clause_ref, title, severity, explanation, suggested_fix, market_position}]` |
| **Grade out of 100** | Deterministic. The model scores each item on a lawyer-written rubric (assignment, liability caps, IP, termination, governing law…); *code* computes the total and letter grade. This keeps the grade explainable and matches the "How Jessica grades a contract" resource on the site |
| **Redlines** | v1: a clause-by-clause table of current vs proposed wording in the UI. v2: a downloadable DOCX with genuine tracked changes (`w:ins`/`w:del` written into the document XML) |
| **Negotiation email** | A second, small call that takes the issues JSON and drafts the email — no document re-read |
| **Perspective** | The user states which side they are on (e.g. "I am the adviser"). Everything above is conditioned on it |

### 3.2 Ask

| Step | ⚙️ Implementation |
|---|---|
| **Context** | The full document, cached. No retrieval layer |
| **Answers** | Use the [citations](https://platform.claude.com/docs/en/build-with-claude/citations) feature so every answer points at the clause it came from — the difference between a chatbot and a tool a founder will trust |
| **History** | `messages` table per document; the conversation is replayed on each turn |

### 3.3 Draft

| Step | ⚙️ Implementation |
|---|---|
| **Templates** | Two to start — NDA and services agreement — written by the firm's lawyers as DOCX with `{{placeholders}}` and optional clause blocks |
| **Intake** | A short structured form (parties, term, governing law, mutual/one-way, key commercial terms) |
| **Generation** | The model fills placeholders, selects optional blocks and adapts wording to the intake; `python-docx` renders the DOCX |
| **Guard-rail** | The model may not add clauses that are not in the firm's clause library. It adapts; it does not free-write |

---

## 4. Data model

| Table | 🗂️ Key fields | 📝 Notes |
|---|---|---|
| `users` | id, email, created_at | Mirrors Supabase Auth |
| `workspaces` | id, name, owner_id, plan | One per user in v1; makes teams possible later |
| `documents` | id, workspace_id, filename, storage_path, mime, page_count, sha256, expires_at | `expires_at` drives retention |
| `document_text` | document_id, clauses JSONB | Parsed structure, so re-parsing is never needed |
| `jobs` | id, type, payload, status, attempts, locked_at, result | The queue |
| `reviews` | id, document_id, perspective, grade, letter, rubric JSONB, issues JSONB, email_draft | One row per run |
| `messages` | id, document_id, role, content, citations JSONB | Ask history |
| `drafts` | id, workspace_id, template_id, intake JSONB, storage_path | Draft outputs |
| `matters` | id, document_id, review_id, status, assigned_lawyer, notes | Lawyer handoff |
| `credits` / `subscriptions` | workspace_id, balance, stripe_customer_id | Billing |
| `audit_log` | actor, action, object, ip, at | PDPA accountability |
| `llm_calls` | job_id, model, tokens_in, tokens_out, cached_tokens, ms, cost | Spend and quality |

---

## 5. API surface (v1)

| Endpoint | 🔐 Auth | 🎯 Purpose |
|---|---|---|
| `POST /documents` | anonymous or user | Upload; returns `document_id`. Anonymous uploads get a 24-hour session |
| `POST /documents/{id}/review` | anonymous or user | Enqueue a review; returns `job_id` |
| `GET /jobs/{id}` | owner | Poll status; HTMX polls this and swaps in the result |
| `GET /reviews/{id}` | owner | Grade, issues, redline table, email |
| `POST /documents/{id}/ask` | user | One turn of Ask |
| `POST /drafts` | user | Create from template + intake |
| `POST /matters` | user | "Send to a lawyer" |
| `POST /webhooks/stripe` | Stripe signature | Credit top-ups, subscription events |
| `DELETE /documents/{id}` | owner | Immediate purge, file and rows |

**First-visit flow (ties to the landing page dropzone):** upload anonymously → review runs → user sees the grade and the top issue → enters an email to see the full report → account created, document re-parented, session merged. Unclaimed anonymous documents are purged after 24 hours.

---

## 6. Confidentiality and PDPA

Third priority, but cheap to get right from day one and expensive to retrofit.

| Concern | 🛡️ Measure |
|---|---|
| Data at rest | Supabase Postgres + Storage in the Singapore region, encrypted at rest; private bucket with short-lived signed URLs |
| Data in transit | TLS everywhere; the only outbound call carrying document content is to the Claude API |
| Cross-border processing | The Claude API processes content outside Singapore. PDPA permits this with comparable protection in place; disclose it in the privacy policy and DPA. If a client ever requires in-region inference, Claude is also offered through cloud providers with Asia-Pacific regions — a swap of the SDK client, not a rewrite |
| Provider data use | Confirm the current [API data retention terms](https://platform.claude.com/docs) and whether zero-data-retention applies to your account; state the answer plainly in the privacy policy |
| Retention | Default: files deleted 30 days after last access (configurable per workspace); a nightly job enforces `expires_at`; users can purge immediately |
| Access | Row-level ownership checks on every query; no shared "admin sees everything" path without an audit entry |
| Accountability | `audit_log` on upload, view, download, delete, share, handoff |
| Secrets | Fly secrets / environment only; nothing in the repo |

---

## 7. Lawyer handoff (v1 minimum, room to grow)

| Version | 🤝 What happens when a user clicks "Send to a lawyer" |
|---|---|
| **v1** | A `matters` row is created; the firm receives an email (Resend) with the document, the review and the user's note; the user sees "A lawyer will be in touch within one business day" |
| **v1.5** | The same event posts to a Slack channel the firm already uses (a Slack connector exists) |
| **v2** | Lawyer-side view in the app: claim the matter, add notes, upload the finished document, trigger e-signature through Docusign |

---

## 8. Build plan — eight weeks, one builder

| Week | 🚀 Ship | ✅ Done when |
|---|---|---|
| **1** | Repo, FastAPI skeleton, Supabase auth + storage, upload endpoint, DOCX/PDF parsing, `jobs` table + worker loop, Fly deploy | A file can be uploaded and its clauses viewed in the browser |
| **2–3** | Review pipeline end to end: structured issues, rubric grade, clause table, negotiation email; HTMX result page with polling | A real adviser agreement returns a grade and ranked issues in under two minutes |
| **4** | Ask with cached document context and citations | Questions return clause-referenced answers |
| **5** | Draft: two templates, intake form, DOCX output | An NDA can be generated and downloaded |
| **6** | Stripe Checkout + webhooks; credits; retention job; `audit_log`; privacy policy text; "Send to a lawyer" email | Someone can pay and the firm receives a handoff |
| **7** | Anonymous-upload flow from the landing dropzone; account merge; Sentry; `llm_calls` dashboard page | The landing page dropzone produces a signed-up user |
| **8** | Tracked-change DOCX redlines; prompt tuning on 20 real documents with a lawyer scoring output; closed beta | Ten founders have run a review; grades agree with a lawyer's view on ≥ 8 of 10 |

Weeks 2–3 are the risk. If the review output is not good enough by the end of week 3, stop and fix quality before building Ask and Draft — nothing downstream matters if the grade is not trustworthy.

---

## 9. Running cost (before revenue)

| Item | 💷 Roughly per month | Note |
|---|---|---|
| Fly.io — web + worker | US$10–25 | Two small machines in `sin` |
| Supabase Pro | US$25 | Postgres, auth, storage, backups |
| Resend / Sentry / Stripe | US$0 fixed | Free tiers; Stripe is percentage only |
| Domain + DNS | ~US$2 | |
| Claude API | Usage-based | A 30-page contract is roughly 20–30k input tokens and 3–5k output; with caching, follow-up Ask turns are a fraction of that. Check current per-token pricing in the platform docs and price each review with margin |

Fixed cost is in the region of **US$40–55 a month**; the variable cost is the model, which is exactly what credits or a per-review price should recover.

---

## 10. Risks

| Risk | 📉 Impact | 🧯 Mitigation |
|---|---|---|
| Review quality is uneven across contract types | Trust collapses | Rubric is fixed and lawyer-written; start with the three contract types the firm sees most; week-8 scoring gate |
| Redlines in real DOCX are fiddly (OOXML tracked changes) | Slips schedule | Ship the clause table first; DOCX redlines are a v2 feature, not a launch blocker |
| Solo builder is a single point of failure | Outage nobody notices | Sentry alerts to phone; Fly auto-restart; Supabase daily backups; a one-page runbook |
| Model or API changes | Breakage | Pin model IDs in config, not code; `llm_calls` makes regressions visible |
| Client asks for in-region inference | Deal risk | Architecture isolates the LLM client; document the swap path now |

---

## 11. Decisions needed from you

1. **Grading rubric** — which lawyer owns it, and can it be written in week 1 alongside the code?
2. **Templates** — are the NDA and services agreement precedents ready as DOCX, or do they need drafting first?
3. **Pricing model** — credits per review, or a monthly subscription? This decides the Stripe setup in week 6.
4. **Anonymous upload** — comfortable with a review running before sign-up (recommended for conversion), or gate on email first?
5. **Handoff owner** — who at the firm receives matters, and by what channel today?
