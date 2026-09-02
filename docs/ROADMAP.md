# GRACI roadmap

> Classification: current authorization and sequencing view
> Authority: Product Owner direction; entries do not authorize work unless explicitly marked authorized
> Verified against: accepted Phase 8E Stage 1 commit `023a5ff9c78b549ac9d5d80ac3a3f1b92048ca12`
> Last verified: 2026-09-02

| Objective | State | Meaning |
|---|---|---|
| Development-process handoff and durable memory foundation | **COMPLETE / PRODUCT OWNER ACCEPTED** | A fresh Codex session reconstructed the current product state from the repository alone; the temporary bootstrap package was then authorized for removal |
| Phase 8D: System Health & Trusted Runtime Context | **COMPLETE / PROMOTED / DEPLOYED / PRODUCT OWNER ACCEPTED** | Commit `a0a61b7` is on `origin/main`; an authorized reputable-build repair preserved Code Integrity, repeat run `1df4990ca2ed4dbb87f3f4478027fcf0` passed through five minutes, and the Product Owner accepted the phase |
| Optional 4090 llama.cpp upgrade | **COMPLETE / PRODUCT OWNER ACCEPTED** | Official b10675 is deployed; both models passed after a new boot, b10516 rollback was exercised, gaming impact is verified, and 3090 sufficiency plus MO2 priority remain intact |
| One-way 3090-to-4090 certificate remoting | **COMPLETE / PRODUCT OWNER ACCEPTED** | Passwordless HTTPS WinRM maps only the 3090 client certificate to `GRACI_Remote`; password access is break-glass only |
| 4090 telemetry 1.0.1 acceptance closure | **COMPLETE / PRODUCT OWNER ACCEPTED** | Controlled boot startup, one-process/resource behavior, fresh telemetry, and HUD reacquisition passed in `ACC-0006` and the Product Owner accepted the bounded capability |
| Phase 8E: Read-only Obsidian knowledge and governance review | **DESIGN AND STAGE 1 PRODUCT OWNER ACCEPTED / STAGE 2 AUTHORIZED** | Accepted Stage 1 commit `023a5ff` is on `origin/main`. The [accepted design](PHASE_8E_OBSIDIAN_DESIGN.md) uses a generated one-way local projection. Stage 2 may now implement and verify the synthetic local Windows viewer boundary; Obsidian, real data, deployment, and Stages 3 through 5 remain unauthorized |
| Phase 9: Permission-gated internet research, tool, and MCP qualification | **REQUIRED PRODUCT OBJECTIVE / IMPLEMENTATION NOT AUTHORIZED** | For a knowledge gap, ask to search the internet and return a sourced answer; for a missing tool or MCP, create or locate candidates, evaluate them in a sandbox, and require separate Product Owner approval before production installation and use |
| Phase 10: Governed document ingestion, RAG, and corrective learning | **REQUIRED PRODUCT OBJECTIVE / IMPLEMENTATION NOT AUTHORIZED** | Safely ingest approved documents including PDFs, retrieve relevant local knowledge with source traceability, and record confirmed mistakes, corrections, and lessons without allowing memory to grant authority or silently change GRACI |
| Phase 11: Scheduled Product Owner-authorized proactive work | **REQUIRED PRODUCT OBJECTIVE / IMPLEMENTATION NOT AUTHORIZED** | Run explicitly approved recurring tasks, such as a daily résumé-based job search, without requiring a new prompt each day while remaining inside the approved schedule, information, actions, privacy, and notification boundaries |
| Phase 12: Human-quality document creation and style validation | **REQUIRED PRODUCT OBJECTIVE / IMPLEMENTATION NOT AUTHORIZED** | Create human-facing documents in a natural, audience-appropriate style without em dash punctuation, canned AI language, excessive formatting, fabricated facts, or false authorship claims, then validate the finished artifact before delivery |
| Phase 13: Unified planning and governed execution | **REQUIRED PRODUCT OBJECTIVE / IMPLEMENTATION NOT AUTHORIZED** | Turn an approved request into a visible plan, select only the capabilities the task needs, track progress and dependencies, recover safely, and preserve one authoritative task outcome |
| Phase 14: Permission center, approval inbox, and activity history | **REQUIRED PRODUCT OBJECTIVE / IMPLEMENTATION NOT AUTHORIZED** | Give the Product Owner one clear place to inspect, approve, reject, modify, pause, revoke, and audit one-time, project, schedule, tool, account, and external-action requests |
| Phase 15: Secure credentials and everyday service connectors | **REQUIRED PRODUCT OBJECTIVE / IMPLEMENTATION NOT AUTHORIZED** | Add least-privileged credential storage and governed connections for email, calendars, contacts, tasks, files, messaging, and other approved services with separate read, draft, send, change, and delete permissions |
| Phase 16: Safe browser and desktop action | **REQUIRED PRODUCT OBJECTIVE / IMPLEMENTATION NOT AUTHORIZED** | Let GRACI navigate approved websites and applications, prepare forms and actions, show previews, request confirmation for consequential steps, and retain evidence and recovery options |
| Phase 17: Multimodal understanding and media workflows | **REQUIRED PRODUCT OBJECTIVE / IMPLEMENTATION NOT AUTHORIZED** | Understand and create approved images, scans, charts, audio, and video through governed local capabilities or qualified tools while preserving privacy, provenance, and human-quality output |
| Phase 18: Resilience, backup, recovery, and measurable improvement | **REQUIRED PRODUCT OBJECTIVE / IMPLEMENTATION NOT AUTHORIZED** | Protect memory, governance, schedules, tools, and configuration with tested recovery, then measure task outcomes and use accepted evidence to improve future recommendations and workflows |
| Next implementation objective | **PHASE 8E STAGE 2 AUTHORIZED** | Implement and verify the dedicated local Windows viewer boundary with synthetic data. Obsidian installation, real data, network changes, automatic refresh, Stage 3 and Phases 9 through 18 remain unauthorized |
| Ordinary runtime capability selection | **PRODUCT DIRECTION** | Eventually choose routing, review, memory, optional compute, recovery, and verification according to task/policy/latency/resources rather than invoking all subsystems on every turn |
| Wake word, VAD authority, always listening, or unscheduled autonomous follow-up | **DEFERRED / UNAUTHORIZED** | Scheduled work is limited to Phase 11 standing grants; these broader interaction and autonomy modes require separate Product Owner decisions and governed implementation |
| External/cloud runtime assistance | **FUTURE GOVERNED CAPABILITY** | Denied by default; no runtime path exists |

## Phase 8D implementation and closure

Phase 8D now implements typed, timestamped runtime-readiness observations; trusted
local date/time/timezone; 3090/router/Qwen/GLM availability and load state; optional
4090 reachability, MO2, eligibility, and endpoint/model health; STT/TTS resource
readiness; freshness and recovery transitions; bounded trusted conversational system
context; loopback/UI projection; and bounded resident lifecycle evidence.

The startup/readiness contract distinguishes:

- missing;
- access denied / unknown;
- registered;
- launcher succeeded;
- process alive; and
- runtime ready.

Runtime readiness comes from owned-process and actual endpoint behavior, not task
registration or exit code. The implementation adds no repair, routing, microphone,
cloud, or autonomous execution authority.

The controlled cold-start procedure is recorded in
[`ACC-0003`](acceptance/ACC-0003-phase8d-cold-start.md). The first run preserved the
resident/browser success but failed overall when Windows Code Integrity blocked
unsigned b10516 router code. The Product Owner then authorized a security-preserving
repair. Official-release b9637 matched its published SHA-256 digest, passed the
unchanged active reputation policy, supported every pinned GRACI flag, and completed
an isolated CUDA-build router/model request using the pinned `--n-gpu-layers all`
setting before deployment. No Code Integrity, Smart App Control, signing, trust, or
allowlist setting was changed.

Repeat run `1df4990ca2ed4dbb87f3f4478027fcf0` followed a full shutdown and new boot.
Both launchers returned `0`; one resident instance, browser/health endpoint, primary
router/model inventory, and lifecycle heartbeats remained valid at the sustained 60,
120, and 300 second checkpoints. The automated summary is `PASS`.

Phase 8D is deployed, automated cold-start validated, and Product Owner accepted.
`GRACI-ISSUE-001` is closed. The separately bounded 4090 llama.cpp procedure is
deployed and live validated as recorded in [`ACC-0004`](acceptance/ACC-0004-4090-llama-upgrade.md).
The 4090 upgrade and one-way certificate remoting are Product Owner accepted. The
separately authorized telemetry 1.0.1 technical closure passed as recorded in
[`ACC-0006`](acceptance/ACC-0006-4090-telemetry.md), and the Product Owner accepted
that bounded capability on 2026-09-02. At that closure boundary, no later
implementation objective was authorized. The separate current Phase 8E Stage 1
authorization is recorded below.

## Phase 8E required scope: Read-only Obsidian human review

The Product Owner requires an Obsidian interface for human review of GRACI's
important information. The intended view includes canonical governance, rules,
decisions, current status, roadmap, acceptance records, and clearly labelled bounded
views of governed memory, RAG sources, and accepted corrective lessons where
appropriate.

Obsidian must remain a read-only human interface and optional to GRACI's runtime.
The authoritative repository Markdown and canonical structured memory remain the
sources of truth. The interface must not create competing authoritative copies,
write back to governed data, parse Markdown to grant authority, or become required
for GRACI to operate. Detailed design, implementation, testing, deployment, and
acceptance require separate Product Owner authorization.

The Product Owner accepted the design choices and the Stage 1 fixture-only
implementation. The [`phase8e`](../phase8e/README.md) package now provides the typed
catalog, exact local Git-commit reader, exact-ID synthetic memory renderer, complete
hash manifest, active-content and path controls, immutable generation promotion,
and tamper verification. Focused deterministic tests cover the approved adversarial
and failure cases. This implementation is outside ordinary GRACI runtime
composition and has not installed or configured Obsidian, changed Windows security,
read real memory, generated a real-data projection, or deployed. The Product Owner
authorized Stage 2 local Windows boundary work with synthetic data. Stage 3 and
every later stage remain unauthorized.

## Phase 9 required scope: Internet research, tools, and MCPs

Phase 9 follows the human-review foundation so the Product Owner can inspect its
decisions, evidence, research sources, and adopted-tool records. When approved local
knowledge is insufficient to answer an authorized request, GRACI must explain the
gap and ask for bounded internet-search permission unless an applicable current
grant already exists. Approved research must prefer credible primary sources,
identify its sources, distinguish sourced facts from inference, minimize disclosed
context, and locally review the result before answering.

When the gap is a missing capability rather than missing knowledge, GRACI must ask
for a bounded grant to research and evaluate tools on the internet unless an
applicable current grant already exists.

An approved evaluation should normally compare about three credible candidates.
GRACI must screen them for task fit, provenance, licensing, security, privacy,
resource cost, maintainability, and local-first compatibility; install or execute
them only in an isolated evaluation environment; run comparable task-relevant tests;
and return an evidence-backed scorecard, limitations, risks, and recommendation.
Fewer candidates are acceptable when the market does not provide three credible
options, but that limitation must be reported rather than filled with weak choices.

Research or sandbox-evaluation permission does not authorize production use. After
the Product Owner chooses a candidate, a separate explicit approval is required to
install or promote it into production. Production work must preserve rollback,
record the exact reviewed version and provenance, pass focused and integration
tests, and remain bounded to the approved task and capability. No current internet,
download, package-installation, or production-promotion runtime path is created by
this roadmap direction.

Model Context Protocol (MCP) servers and integrations are included in this governed
tool lifecycle. GRACI must be able either to create a bounded MCP for an approved
need or, with applicable internet permission, locate existing MCP candidates. Created
and downloaded MCPs must receive source, dependency, permission, credential,
network, data-flow, and tool-surface review; isolated functional and adversarial
testing; an evidence-backed score; and the same separate Product Owner production
approval. An MCP connection supplies capability, never authority, and production
tools must be explicitly allowlisted and least-privileged.

## Phase 10 required scope: Document ingestion, RAG, and corrective learning

GRACI requires safe local ingestion of Product Owner-approved documents, including
PDF résumés. Ingestion must validate file type and size, prevent embedded content or
document features from gaining execution or authority, extract text locally where
practical, preserve the source, and let the Product Owner review material extraction
errors before it becomes reusable governed memory. OCR or an additional parser, when
needed, must follow the governed tool lifecycle.

GRACI requires a local-first retrieval-augmented generation (RAG) system over
approved knowledge sources. Retrieval must preserve source identity, classification,
freshness, and enough traceability for the Product Owner to inspect why information
was used. Canonical documents and governed memory remain authoritative in their
existing roles; indexes, embeddings, and retrieval caches are derived and
rebuildable. Retrieved text is untrusted context and cannot grant permission,
override governance, or silently become a remembered fact.

GRACI also requires a corrective-learning loop. When the Product Owner corrects a
mistake, or a problem and correction are jointly confirmed, GRACI should record the
problem, relevant context, correction, evidence, scope, and lesson learned in
governed memory. Before similar future work, retrieval should surface applicable
accepted lessons so GRACI can avoid repeating the mistake. Conflicts, later
corrections, and superseded lessons must remain explicit rather than being silently
merged.

For this objective, self-learning means governed, reviewable memory and retrieval.
It does not authorize silent model-weight changes, autonomous policy changes,
permission expansion, or self-promotion. Detailed design, implementation, corpus
selection, memory-write rules, testing, deployment, and acceptance require separate
Product Owner authorization.

## Phase 11 required scope: Scheduled proactive work

GRACI requires a scheduler for explicitly approved recurring tasks. A standing
schedule must identify the task, cadence, start time, expiration or review point,
approved information sources, external-access grant if needed, allowed actions,
resource limits, output destination, notification behavior, and pause/cancel
controls. Within that exact grant, GRACI may run without receiving a new instruction
for every occurrence. It must not invent additional scheduled work or broaden a
schedule because related work appears useful.

For a daily job-search schedule, GRACI may use an approved locally ingested résumé,
derive only the minimum search terms needed, search public listings when the standing
grant includes internet access, remove duplicates, rank matches, and deliver a dated
report with links and reasons. The full résumé should remain local unless the Product
Owner separately authorizes disclosure. Searching and reporting do not authorize
creating accounts, applying, uploading the résumé, contacting employers, scheduling
interviews, accepting terms, or spending money.

Every run must retain truthful evidence of its authority, inputs, sources, actions,
results, failures, and next scheduled time. Expired, paused, revoked, ambiguous, or
unsafe schedules fail closed. Each recurring task requires its own scope; a general
request for “other daily tasks” cannot become unlimited standing authority. Detailed
design, implementation, deployment, and acceptance require separate Product Owner
authorization.

## Phase 12 required scope: Human-quality document creation

Every human-facing document created or substantially revised by GRACI must read like
careful professional writing prepared for its actual audience and purpose. This
includes Markdown, plain text, email drafts, reports, résumés, letters, proposals,
Word documents, PDFs, presentations, and explanatory text in spreadsheets.

GRACI must use clear sentences, natural transitions, specific wording, restrained
headings, and formatting that helps the reader. It must not use the Unicode em dash
character or a double-hyphen substitute as prose punctuation. Standard hyphens remain
appropriate for compound words, identifiers, file names, and other ordinary uses.
GRACI must also avoid canned introductions and conclusions, repetitive summaries,
empty filler, excessive bullets or bold text, vague claims, fake quotations, and
other formulaic patterns associated with low-quality AI-generated writing.

The requirement is a quality and style standard, not permission to misrepresent
authorship. Facts, citations, provenance, required disclosures, and document metadata
must remain truthful. Source code, machine-readable formats, logs, immutable evidence,
quoted source material, and historical records are not rewritten merely to match a
prose style. New document-generation workflows require format-appropriate rendering,
proofreading, and visual or structural validation before delivery.

## Phase 13 required scope: Unified planning and governed execution

GRACI requires one ordinary task lifecycle that can use existing and future
capabilities without invoking every subsystem on every request. It should understand
the authorized goal, identify dependencies, present or retain an appropriate plan,
select local models, memory, RAG, review, tools, optional compute, and recovery only
when justified, and track work through completion or a truthful stop.

Plans and model suggestions do not create authority. Each step remains bounded by
the active task and applicable grants. The task record should show progress,
important decisions, evidence, failures, repairs, pending approvals, and one
authoritative final outcome.

## Phase 14 required scope: Permission center and approval inbox

The Product Owner requires one understandable place to review GRACI's requested and
active permissions. It should cover one-time, task, project, schedule, internet,
tool, MCP, connector, credential, disclosure, submission, communication, purchase,
deployment, and production-promotion decisions. Each item should explain the action,
reason, information involved, risk, duration, and effect of approval.

The same interface should provide a private approval inbox for prepared work and
scheduled findings. The Product Owner must be able to approve, reject, edit, pause,
resume, revoke, and inspect history without needing to understand internal technical
details. Revocation and expiry must take effect predictably and fail closed.

## Phase 15 required scope: Credentials and service connectors

GRACI requires protected credential handling and governed connectors for everyday
services such as email, calendars, contacts, task lists, files, messaging, and other
Product Owner-approved systems. Secrets must remain in an operating-system or
equivalent protected store and must not appear in prompts, memory, logs, source, or
documents.

Connector permissions must be least-privileged and separated by action. Reading,
searching, drafting, sending, editing, deleting, sharing, and administrative changes
must not inherit authority from one another. Every connector requires identity,
scope, expiry or review, audit, error handling, and revocation behavior.

## Phase 16 required scope: Browser and desktop action

GRACI requires governed control of approved websites and desktop applications. It
should be able to navigate, gather information, prepare forms, stage files, and
preview an intended action. Consequential steps such as submission, publication,
purchase, deletion, account creation, communication, or acceptance of terms require
the applicable explicit approval.

Computer control must use narrow targets, verify the visible state before action,
detect unexpected changes, retain useful evidence, and preserve recovery where
practical. A prepared action must not be mistaken for an executed action.

## Phase 17 required scope: Multimodal understanding and media workflows

GRACI requires governed understanding of photographs, screenshots, scans, diagrams,
charts, audio, and video in addition to text documents. It should support tasks such
as receipt and contract review, visual troubleshooting, chart interpretation,
transcription, and media planning.

Creation workflows should support images, audio, and video through approved local
capabilities or tools qualified under Phase 9. Source rights, personal information,
provenance, disclosure, output quality, and human review remain explicit. Media
creation does not bypass tool, internet, document-quality, or production approval.

## Phase 18 required scope: Resilience and measurable improvement

GRACI requires versioned local backup and tested restoration for canonical memory,
governance, schedules, approved tool records, connector configuration, and other
critical state. Recovery procedures must distinguish backup existence from a
successful restore and must preserve the authoritative 3090 and local-first design.

GRACI should measure whether recommendations and completed tasks achieved their
accepted goals. Useful signals include Product Owner approval or rejection, task
completion, correction, repeated failure, tool score, schedule usefulness, and
downstream outcome. These measurements may improve future retrieval, planning, and
recommendations, but they cannot silently change policy, authority, or production
behavior.
