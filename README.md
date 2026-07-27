# Market Gap Agent

An autonomous competitive-intelligence agent. Given a company (name + description) and a
seed list of 3–5 competitors, it ingests real discussion from Reddit and a second public
source, extracts evidence-backed claims, clusters domain-wide pain points, and produces
`competitive_brief.md` + `evidence.json`.

Built on LangChain's **deepagents** subagent pattern (`create_deep_agent(subagents=[...])`)
and exposed as a FastAPI service.

## Governing principle

> LLM subagents produce candidate structured output. Deterministic Python decides what is
> allowed to exist.

Fetching, cleaning, dedupe, quote verification, gap computation, conflict detection,
confidence scoring, and file rendering are plain, unit-tested Python. Only claim
extraction, pain-point clustering, entity resolution, and (optionally) prose synthesis are
LLM work — and every LLM output passes a grounding validator before it enters the system.
See [Grounding](#grounding-how-claims-and-pain-points-are-tied-to-evidence) below.

## Test company

The same fictional company is used throughout (`sample_input.json`) so the seed list stays
comparable to real, currently-discussed products:

```json
{
  "company_name": "Flowdeck",
  "company_description": "Flowdeck is a project management SaaS for cross-functional product teams, combining task boards, timeline views, and lightweight docs so teams can plan sprints and track delivery without stitching together separate tools.",
  "competitors": ["Asana", "ClickUp", "Monday.com", "Trello"]
}
```

## Architecture

```
app/
├── domain/      # Pydantic models: Competitor, Document, Evidence, Claim, PainPoint, Gap,
│                #   ConflictSet, SkippedSource, GroundingReport, EvidenceBundle
├── sources/     # pluggable ingestion adapters: reddit.py, serper.py, hackernews.py
├── analysis/    # grounding, dedupe, conflicts, gaps, confidence, intake, pain points
│                #   -- all deterministic, all unit tested
├── agents/      # deepagents subagent graph (llm.py, prompts.py, tools.py, subagents.py, graph.py)
├── reporting/   # evidence.json + competitive_brief.md rendering (Jinja2, template-driven)
├── runs/        # pipeline orchestration + in-process run store
└── api/         # FastAPI routes
```

### Subagent topology (deepagents)

The main `create_deep_agent` graph is an **orchestrator only** — it plans and delegates via
the auto-provided `task()` tool; it never authors a claim itself.

| Subagent | Form | Role |
|---|---|---|
| `intake_validator` | dict `SubAgent` | Resolves the target + seed competitors into distinct real entities (canonical name, domain, one-liner). Catches aliases a string match would miss ("Meta"/"Facebook"). Its `record_intake` tool call is re-validated deterministically in `app/analysis/intake.py`, which is authoritative for duplicate collapse and the min-competitor gate. |
| `research_scout` | dict `SubAgent` | Per company: crafts search queries and calls the ingestion tools (`search_reddit`, `search_serper`, `search_hackernews`). Never quotes or summarizes — the tools write documents into the store directly, so the model cannot fabricate one. |
| `claim_extractor` | `CompiledSubAgent` (forced structured output) | Per document: extracts 0–8 claims about a named company, each with a verbatim `quote`. Every claim is checked by `GroundingValidator` before it exists anywhere else in the system. |
| `pain_point_clusterer` | `CompiledSubAgent` | Groups negative/neutral claims (by id only) into labeled clusters. Whether a cluster is `domain_wide` vs `company_specific` is decided by Python (≥2 companies touched), never by the model. |
| `brief_writer` | dict `SubAgent` | Optional narrative prose for the brief, constrained to a supplied citation index; dangling citations are stripped post-hoc. |

Deliberately **not** subagents: gap computation, conflict detection, dedupe, and confidence
scoring. Each of these is a set/arithmetic operation once claims are grounded — letting an
LLM "decide" them is exactly how a plausible-sounding but wrong gap gets invented.

### Two orchestration modes

- **`pipeline`** (the default the tests and demo exercise): every stage is called directly —
  deterministic query templates for ingestion, the compiled `claim_extractor` /
  `pain_point_clusterer` subagents invoked as plain runnables, everything else in Python.
  A flaky agent tool-loop can never lose the artifacts.
- **`agent`**: the full `create_deep_agent` graph in `app/agents/graph.py`, with the
  orchestrator delegating intake and research to subagents via `task()`. Same adapters and
  validators underneath. Set `ORCHESTRATION_MODE=agent` to use it.

## Ingestion, step by step, per competitor

For the target and each accepted competitor:

1. Generate queries (`"{company} review"`, `"{company} pricing complaints"`,
   `"{company} alternatives"`, `"{company} vs"`, `"{company} support experience"`).
2. **Reddit** (`app/sources/reddit.py`, required) — hits `reddit.com/search.json`, no auth.
   Cleans HTML/whitespace (`sources/normalize.py`), builds a `Document` with a stable id
   (`sha256(platform|url)`), stores it.
3. **Serper.dev** (`app/sources/serper.py`) — a search-engine API call whose organic results
   are classified by domain into `linkedin` / `g2` / `news` / `web` platforms. This is the
   ["LinkedIn" substitution](#the-linkedin-substitution) source. Returns a `no_api_key` skip
   (not a crash, not a fabricated result) if `SERPER_API_KEY` isn't set.
4. **Hacker News** (`app/sources/hackernews.py`) — Algolia's public search API, no key
   required. This is the keyless fallback for requirement #2 if Serper is unavailable.
5. Any adapter failure — connection error, timeout, 403, 429, or an empty result set — is
   classified into a `SkippedSource` (`unreachable` / `blocked` / `rate_limited` / `empty` /
   `no_api_key` / `parse_error`) and logged; ingestion continues with whatever succeeded.
6. Documents are deduped across sources by normalized-text `content_hash`
   (`app/analysis/dedupe.py::merge_documents`), so the same post mirrored on two URLs
   collapses into one document with a merged company list.

## Grounding: how claims and pain points are tied to evidence

`app/analysis/grounding.py` is the anti-hallucination control, used at two chokepoints:

1. **On extraction** — every candidate claim from `claim_extractor` must carry a `quote`
   that is a verbatim, contiguous span of the exact document it was extracted from. The
   validator checks in two tiers: an exact substring match, then a normalization-tolerant
   match (smart quotes, dashes, collapsed whitespace — mapped back to real character
   offsets) for cases where formatting was mangled but the text wasn't paraphrased. There is
   **no fuzzy/embedding similarity match** — that is exactly how a paraphrase would sneak in.
   Quotes under 25 or over 600 characters are rejected. Every rejection is recorded in a
   `GroundingReport` (never silently dropped) and reported in the brief's methodology
   section.
2. **On render** — before `evidence.json` is written, every `Evidence` object attached to a
   `Claim` or `PainPoint` is re-verified against the actual fetched document text
   (`app/reporting/evidence.py::_reverify_all`). If anything fails, the run does not silently
   produce a file — this is an assertion, not a hope.

Pain points work the same way one level up: the clusterer may only reference `claim_id`s it
was given (unknown ids are dropped), and every pain point's evidence list is a deduped union
of its member claims' already-grounded evidence.

Conflicting opinions are preserved structurally, not by prompting: a claim's identity key
includes its `stance`, so a positive and a negative claim about the same
`(company, dimension)` are never merged into one claim by dedupe. `app/analysis/conflicts.py`
groups any such pair into a `ConflictSet` with both sides' evidence, and the brief template
renders a dedicated "Conflicting Signals" section that always shows both.

## The LinkedIn substitution

LinkedIn blocks automated scraping and has no public API for this use case. Rather than
attempt to scrape it (which would fail or violate its terms), we surface LinkedIn — and G2 —
company pages through **Serper.dev search-result snippets**: a normal search-engine query,
whose organic results are classified by domain, gives back a title/snippet/URL for LinkedIn
and G2 pages the same way it would for a news article. We quote only the snippet text
actually returned by the search API and cite the search-result URL — we never fetch or parse
the LinkedIn/G2 page itself. This satisfies "public search-engine results that surface
LinkedIn company pages" directly, and if `SERPER_API_KEY` is unset the run still proceeds
(logged as `no_api_key` skips) using Hacker News as the second required source.

## Running it

```bash
cp .env.example .env   # fill in an LLM key; SERPER_API_KEY is optional
make install
make test               # or: pytest -q
make demo                # runs sample_input.json -> artifacts/demo/
make run                 # or: docker compose up --build
```

API:

```bash
curl -X POST localhost:8000/api/v1/runs -H "Content-Type: application/json" -d @sample_input.json
curl localhost:8000/api/v1/runs/<run_id>
curl localhost:8000/api/v1/runs/<run_id>/brief
curl localhost:8000/api/v1/runs/<run_id>/evidence
```

> **Note on this delivery:** the sandbox used to build this repository has no LLM API key
> and blocks outbound requests to reddit.com (confirmed: Hacker News' keyless API returned
> `200`, Reddit returned `403` — itself a live example of the graceful-skip path in
> `tests/test_sources_failures.py`). Claim extraction requires a real model call, so
> `artifacts/demo/` was not generated in this environment. Running `make demo` with a real
> `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`, `LLM_PROVIDER=openai`) from a network that can
> reach Reddit will produce real `competitive_brief.md` + `evidence.json` for the sample
> input above.

## Tests

`make test` (or `pytest -q`), 20 tests, no network and no LLM calls (an autouse fixture in
`tests/conftest.py` blocks real `httpx` calls unless a test opts in via `respx`):

- `test_sources_failures.py` — **required**: unreachable, blocked (403), rate-limited (429),
  and empty responses each degrade to the right `SkippedSource` reason with no exception and
  no documents; a missing `SERPER_API_KEY` is a graceful `no_api_key` skip, not a crash.
- `test_dedupe.py` — **required**: the same complaint extracted from two different sources
  merges into one `Claim` with both pieces of evidence attached (and higher confidence than
  a single-source claim); byte-identical text at two URLs collapses to one `Document`.
- `test_conflicts.py` — **required**: opposing opinions about the same company/dimension
  survive dedupe as two claims (stance is part of the identity key), get grouped into a
  `ConflictSet` with full attribution, and both quotes appear in the rendered brief's
  "Conflicting Signals" section.
- `test_grounding.py`, `test_intake.py`, `test_api.py` — supporting coverage for the
  quote-verification tiers, duplicate-competitor collapse, and the FastAPI run lifecycle.

## One limitation

The run store is in-process memory (wiped on restart) and Reddit's public JSON endpoint
rate-limits or blocks by source IP unpredictably (see the note above) — so document recall
for the required source varies by where this is deployed, and a run can legitimately finish
`partial` through no fault of the code.

## One improvement with more time

Replace the label-based pain-point clustering with an embedding-based clustering pass (plus
a human-in-the-loop review step before a pain point is marked domain-wide), and move the run
store to Redis so runs survive a restart and can be resumed/cancelled properly.
