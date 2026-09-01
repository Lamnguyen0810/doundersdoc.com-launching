# FD Launcher & "Launch FD AI" button — proposed way forward

*Draft for discussion · 1 September 2026*

---

## 1. Where we are

The Founders Doc marketing mockup (Mockup E) carries the "Launch FD AI" call to action in four places: the sticky nav, the hero, the closing CTA band and the footer. A fifth entry point, "Try it free" in the announcement bar, points to the same destination under a different name.

The FD AI landing page (v180526) is a separate design system: different typeface (Switzer vs Source Serif / Inter), different tokens, its own nav, and a product-style upload dropzone as the hero. Its own primary button reads "Open Jessica".

For the prototype we have plugged the landing page into the mockup as a full-screen view (an embedded frame with a "Back to Founders Doc" bar). That is the right tool for a clickable mockup and the wrong tool for production: framed content is largely invisible to search engines, analytics inside the frame is not captured by the parent page unless separately instrumented, keyboard and screen-reader navigation across the frame boundary is inconsistent, and the two design systems cannot share tokens.

So there are really three decisions bundled inside "the launch button":

1. **Where** the button sends people (architecture).
2. **What** the destination is — a landing page, or the product itself (journey).
3. **What the button says** — and whether "FD AI", "Jessica" and "Try it free" are the same thing (naming).

---

## 2. What the research says

**Architecture.** The dominant SaaS pattern is a marketing site on the root domain and the product on `app.` — used by the likes of YNAB, SendGrid and Optimizely. The reasons are practical rather than aesthetic: separate hosting and deploy cadence (Webflow/WordPress for marketing, cloud infrastructure for the app), cleaner cookie and auth scoping, and no risk of marketing URLs colliding with product routes. SEO guidance, by contrast, favours sub-folders over sub-domains for *content* that should pool authority — but a logged-in product carries no SEO value, so the app is the one thing that gains nothing from being on the root.

**Frames.** Every source reviewed lists the same costs: content not indexed, analytics blind spots, accessibility gaps, no shared styling, and a foreign-looking result. The recommended alternative is a real page transition — "the way Google Drive opens a Sheet in its own context, with a header that gets you back".

**Button copy.** Across 110 SaaS pricing pages, "Get Started" and "Start Free Trial" account for 57% of all primary CTAs; 69% include the word "free"; and "Start" / "Get" open two-thirds of all buttons. Products whose CTA does *not* mention "free" ("Request demo", "Contact sales") have effectively no self-serve adoption — the wording signals the go-to-market model. The consistent advice is that a CTA should name what happens next; "Learn more" and bare "Launch" leave the visitor guessing.

**Naming.** One product should have one name in the funnel. Spellbook, Genie and Robin each use a single product name from ad to app. Our current chain runs "Try it free" → "Launch FD AI" → "foundersdoc.ai" → "Open Jessica", which is three brands for one click.

---

## 3. Options considered

| Option | 🏗️ Structure | ✅ For | ⚠️ Against | 🎯 Verdict |
|---|---|---|---|---|
| **A. Keep the embedded overlay** | Landing page framed inside the marketing site | Zero routing work; both designs untouched | Not indexable; analytics blind; a11y gaps; two design systems on one URL | 🟡 Prototype only |
| **B. Same site, sub-folder** `foundersdoc.com/fd-ai` | Landing page becomes a page on the marketing site | Shares domain authority; one CMS; one nav | Forces the landing page into the marketing design system — loses its product feel; the *app* still needs a home | 🟡 Good for the landing page, not the app |
| **C. Product domain + app sub-domain** `foundersdoc.ai` → `app.foundersdoc.ai` | Marketing on `.com`; product landing on `.ai`; the tool on `app.` | Matches how the landing page already brands itself; independent deploys; clean auth; industry-standard | Two domains to maintain; the `.ai` landing page must earn its own SEO | 🟢 **Recommended** |
| **D. Straight to the product** | Button opens the app directly, no landing page | Shortest path for returning users | Cold visitors hit an upload box with no context; loses the "free first review" pitch | 🟢 As a *returning-user* shortcut only |

---

## 4. Recommendation

Adopt **C**, with **D** layered on for people who have used the product before.

### 4.1 Architecture

| Layer | 🌐 URL | 📦 What lives there | 🛠️ Stack |
|---|---|---|---|
| Marketing site | `foundersdoc.com` | Mockup E: firm, lawyers, resources, consultation booking | CMS / static |
| Product landing | `foundersdoc.ai` | The v180526 page: proposition, upload dropzone, pricing, trust signals | Static, own design system |
| The tool | `app.foundersdoc.ai` | Jessica: review, draft, ask; auth; billing | Application infra |

The marketing site links *out* to the product; it never embeds it. The landing page's dropzone posts *into* the app, so a first-time visitor's upload carries straight through to their first review without a second landing.

### 4.2 The launch button — behaviour

| Visitor | 🖱️ Click "Launch FD AI" goes to | 🧭 Why |
|---|---|---|
| First visit | `foundersdoc.ai` (landing, dropzone in view) | Needs the free-review pitch and trust signals before uploading |
| Has an FD AI session cookie | `app.foundersdoc.ai` (workspace) | Returning users should not re-read the pitch; Option D shortcut |
| Announcement bar "Try it free" | `foundersdoc.ai#upload` | Same destination as the primary CTA, scrolled to the dropzone |

Every link carries UTM parameters (`utm_source=site&utm_medium=cta&utm_content=nav|hero|band|footer`) so we can see which of the four placements actually earns the click. Same tab, not a new one — a new tab breaks the back button and reads as leaving the brand.

### 4.3 Naming and copy

| Where | ❌ Now | ✅ Proposed | 💬 Rationale |
|---|---|---|---|
| Product name (everywhere) | FD AI / Jessica / foundersdoc.ai | **FD AI**, with Jessica as the assistant's name *inside* the product | One name in the funnel; Jessica stays as the persona users talk to |
| Nav & hero primary button | Launch FD AI | **Try FD AI free** | Names the product, the action and the cost; "free" is present in 69% of high-performing CTAs |
| Closing CTA band | Launch FD AI | **Review a contract free** | Names what happens next; matches the "free first review" chip |
| Footer link | Launch FD AI | **Open FD AI** | Footer is a utility list; the plain verb is right here |
| Landing page nav button | Open Jessica | **Open FD AI** | Removes the third brand from the click chain |
| Announcement bar | Try it free | **Try FD AI free** | Same words as the hero, so the two buttons visibly do the same thing |
| Secondary button | Book a consultation | *(unchanged)* | Correctly signals the lawyer path, distinct from the self-serve path |

Keep exactly two CTAs on the marketing site — self-serve (FD AI) and human (consultation). Do not add a third.

### 4.4 Retire the frame

| Item | 🔁 Change |
|---|---|
| `#fdai` overlay + `<iframe>` | Remove before launch; replace with plain `<a href="https://foundersdoc.ai?utm_…">` |
| "Back to Founders Doc" bar | Move to the landing page's own nav as a small "Founders Doc ↗" link back to `.com` |
| Embedded landing HTML | Deploy as its own page at `foundersdoc.ai` |

---

## 5. Phased plan

| Phase | 📅 Timing | 🚀 Deliverables | 📏 Done when |
|---|---|---|---|
| **0 — Decide** | Week 1 | Sign off on C + D; confirm the single product name | This document approved |
| **1 — Landing live** | Weeks 2–3 | `foundersdoc.ai` deployed as a real page; dropzone wired to the app; back-link to `.com` | Page indexable; Lighthouse a11y ≥ 90 |
| **2 — Buttons** | Week 3 | All five entry points relabelled and repointed with UTMs; overlay removed | Analytics shows clicks by placement |
| **3 — Returning-user shortcut** | Weeks 4–5 | Session-cookie check routes known users to `app.` | Repeat visitors skip the landing |
| **4 — Test copy** | Weeks 5–9 | A/B "Try FD AI free" vs "Review a contract free" on the hero | ≥ 95% confidence or 4 weeks, whichever first |

---

## 6. What we'll measure

| Metric | 🎯 Target | 📍 Where |
|---|---|---|
| CTA click-through (all placements) | Baseline in Phase 2, then +20% after copy test | Marketing site analytics |
| Landing → first upload | ≥ 25% of landing sessions | `foundersdoc.ai` |
| First upload → account created | ≥ 60% | App |
| Returning users hitting the landing page | Trending to 0 | App + landing |

---

## 7. Open questions

1. Is `foundersdoc.ai` intended to be the product's public name, or only its address? The landing page currently treats the domain as the wordmark.
2. Should the dropzone accept an upload *before* sign-up (upload → result preview → account), or gate on email first? Fewer fields before value consistently lifts conversion; the trade-off is anonymous processing of client documents.
3. Does the firm want any "Launch" language at all? "Launch" suits a feature announcement; for an evergreen button it implies something heavier than a contract review.
