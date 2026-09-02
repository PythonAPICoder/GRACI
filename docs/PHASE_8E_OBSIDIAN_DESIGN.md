# Phase 8E design: Obsidian knowledge and governance review foundation

> Classification: Product Owner-authorized design proposal
> Authority: advisory design; canonical policy remains under `governance/`
> Designed against: local `main` commit `08b2ffdc5c4530d652cde5ee4d2c428f6979f9eb`
> Prepared: 2026-09-02
> Status: PRODUCT OWNER-ACCEPTED DESIGN; STAGES 1-3 PRODUCT OWNER ACCEPTED; STAGES 4-5 NOT AUTHORIZED

PO-DEC-035 authorizes a separate follow-on design and synthetic-only implementation
for the personalized-memory outcome established by PO-DEC-034. It does not authorize
real personal data, deployment, automatic updates, commit, push, or Stages 4-5.

## Purpose and fixed boundaries

Phase 8E gives the Product Owner a clear local view of GRACI knowledge and
governance. It does not create a second knowledge system. The repository Markdown
and canonical governed memory keep their existing roles and authority. Obsidian is
an optional human review application that GRACI can lose without losing runtime
function, policy, memory, evidence, or recovery capability.

PO-DEC-034 clarifies the central product goal after the accepted Stage 3 foundation:
the vault must show GRACI's approved long-term knowledge about the Product Owner,
including preferences, working methods, taught task procedures, corrections, and
lessons, and GRACI must reuse that knowledge in later relevant work. The current
read-only synthetic viewer is a security foundation, not the completed learning
system. Runtime memory capture and retrieval require a separately authorized design.

This proposal applies `HUMANVIEW-001`, `HUMANVIEW-002`, `AUTH-002`, `MEMORY-001`,
`MEMORY-002`, `MEMORY-003`, and `MEMORY-005`. In particular:

- Markdown displayed by the review interface cannot grant a capability or
  permission.
- A projected copy is always derived, even when its source bytes came from a
  canonical file.
- Obsidian cannot write to the repository, governed memory, acceptance evidence,
  run records, future RAG sources, or future corrective-learning records.
- GRACI runtime code does not read the projection, Obsidian settings, or Obsidian
  state.
- The 3090 remains authoritative and independently sufficient. The 4090, shared
  storage, network access, and cloud services are not required.
- No watcher, scheduler, automatic memory write, external access, plugin, or
  background synchronization is introduced by Phase 8E.
- A future G.R.A.C.I. maintainer may replace the derived projection after the
  underlying personal memory is explicitly approved. The viewer stays read-only,
  and the approval does not permit unrelated source writeback or automatic refresh.

## Design baseline findings

This isolated worktree began clean at the authorized commit `08b2ffd`. It is in
detached-HEAD state; the local `main` ref also points to `08b2ffd`, while
`origin/main` points to `e412d1c`.

At design time, `CURRENT_STATUS.md` said that both local `main` and `origin/main`
were at `e412d1c`. That statement was stale relative to inspected Git state. The
authorized Stage 1 documentation reconciliation now records local `main` at
`08b2ffd`, `origin/main` at `e412d1c`, and this implementation worktree detached at
`08b2ffd`. Several current documents still retain recorded verification commits
older than `08b2ffd`; the intervening repository changes were reviewed for this
design, but their verification markers were not silently advanced. A Phase 8E
projection must label sources `Changed since recorded verification` when Git shows
that the source changed after its recorded verification commit.

The repository defines canonical memory as a host-selected absolute local root but
does not configure one fixed production path in ordinary runtime composition. No
real memory root or record content was inspected for this design. Selecting that
root and any content-bearing record IDs remains a later explicit decision.

## Review corpus

The first implementation should use a small explicit source catalog. Inclusion in
the catalog means only that a source may be displayed. It does not promote the
source's authority.

| Information | Canonical source | Initial Phase 8E view | Boundary |
|---|---|---|---|
| Current governance and change control | `governance/CURRENT_POLICY.md`, `POLICY_INDEX.md`, and `CHANGE_PROCESS.md` | Full derived rendering with source commit and hash | Highest repository-level normative source; the rendering is not policy |
| Documentation authority and workflow | `AGENTS.md`, `docs/INDEX.md`, and `docs/DEVELOPMENT.md` | Full derived rendering | Workflow guidance remains subordinate to governance |
| Product and architecture | `docs/PRODUCT.md` and `CURRENT_ARCHITECTURE.md` | Full derived rendering | Descriptive and directional, not a permission source |
| Current status, issues, capability, and roadmap | `CURRENT_STATUS.md`, `docs/KNOWN_ISSUES.md`, `docs/CAPABILITY_MATRIX.md`, and `docs/ROADMAP.md` | Full derived rendering with freshness warnings | Status, sequencing, and evidence state stay distinct from implementation authority |
| Product Owner decisions | `docs/decisions/DECISION_INDEX.md` and later allowlisted decision records | Full derived rendering | A record reports a decision; the projected copy cannot create or amend one |
| Acceptance | `docs/acceptance/ACCEPTANCE_INDEX.md` and allowlisted `ACC-*` records | Full derived rendering | Each acceptance remains limited to its recorded scope |
| Historical phase material | `docs/history/` and phase records | Index and links only in the initial view | Historical records are not current instructions and should be opened only when needed |
| Governed memory | Host-selected canonical JSON root on the 3090 | Bounded generated notes from explicitly approved records | JSON remains canonical; content is untrusted context and may be sensitive |
| Run evidence | `runs/` and bounded operational evidence | Acceptance-linked summaries only; no bulk raw projection | Raw records may contain tasks or model output and are not reusable memory |
| Future RAG information | Future approved source registry and retrieval records | A not-implemented status note until Phase 10 defines a schema | No corpus, embedding, chunk, index, or cache is implied by Phase 8E |
| Future corrective learning | Future accepted correction and lesson records | A not-implemented status note until Phase 10 defines write and acceptance rules | No current automatic correction-record or retrieval loop exists |

The initial source catalog must be code or typed configuration reviewed with the
implementation. It must not infer authority or inclusion from arbitrary Markdown
front matter, note text, folder names, links, or model output.

### Governed memory view

Current canonical memory is local JSON with schema versions 1 and 2. Records can
contain content, scope, type, provenance, status, version, timestamps, and, for
schema 2, relevance, expiry, and supersession fields. The Phase 8E view should not
enumerate all records by default.

The recommended first release has two modes chosen at generation time:

1. **Metadata-only**, the default. Show ID, schema, scope, type, provenance origin,
   status, version, timestamps, relevance key, expiry, supersession relation, source
   hash, and validation or conflict diagnostics. Do not show `content` or free-form
   `source_ref`.
2. **Approved-content**, opt-in per record. Show content only for record IDs the
   Product Owner explicitly includes in that generation. Preserve the exact source
   ID and hash, mark the content `UNTRUSTED CONTEXT`, and display superseded,
   expired, tombstoned, corrupt, or conflicting state without resolving it.

The exporter must use the existing memory validator for supported schemas or an
equivalent read-only validator. It must not repair, migrate, update, expire,
supersede, tombstone, or otherwise mutate a record. Corrupt or unsupported records
produce metadata-only diagnostics without their raw bytes being rendered.

Future RAG and corrective-learning records need their own accepted schemas and
source catalogs in Phase 10. Phase 8E may later render them, but it must not design
their write authority by implication.

## Architecture options

### Option A: open the repository directly

Obsidian could open the repository or its documentation directory as a vault. This
has the lowest projection complexity and shows current working files immediately.
It also couples a review tool to the development tree, encourages Obsidian state in
the repository, exposes unrelated files and uncommitted work, gives same-user
plugins and links a route to broader data, and makes accidental edits easy. Labels
would be inconsistent because the source documents were not all written as vault
pages. A same-user read-only user-interface setting is not an enforceable write
boundary.

This option is not recommended for the accepted baseline. It may be useful only as
an explicitly approved developer convenience outside Phase 8E acceptance, with no
claim of security isolation.

### Option B: generate a one-way review projection

A local exporter reads only explicitly cataloged sources, produces a versioned
staging generation, validates it, and promotes it to a separate review location.
Every note carries visible provenance and authority labels. Canonical files and
memory are never opened for write. Obsidian receives access only to the projection.

This adds an exporter, manifest, refresh procedure, storage cost, and the risk that
the view becomes stale. Those costs are bounded and testable. The architecture
provides meaningful source separation, consistent labels, privacy filtering,
deterministic link handling, and a recoverable last-known-good view.

**Recommendation:** use Option B. Do not support direct repository mode in the
accepted Phase 8E implementation. A generated projection is the only option that
cleanly separates human review from canonical source storage while preserving a
usable graph and navigation experience.

## Recommended data flow

```text
explicit local source catalog
          |
          v
repository commit objects + canonical memory opened read-only
          |
          v
bounded local exporter under a non-viewer identity
          |
          v
new staging generation -> structural and security validation
          |
          v
immutable versioned projection + hash-verified manifest
          |
          v
Obsidian under a restricted local viewer identity

There is no reverse path from Obsidian to exporter inputs or GRACI runtime.
```

For repository documents, the exporter should read an explicitly resolved local Git
commit, not the mutable working tree. A generation records the full commit ID. The
source catalog distinguishes documents that are canonical policy, accepted
decisions, current descriptive material, historical evidence, or workflow guidance.
Git history proves version identity, not Product Owner acceptance.

For governed memory, the exporter receives the absolute host-selected memory root
through a separately reviewed local setting. It reads direct child UUID JSON files
only. The memory root must not live inside the review projection.

Each generation is complete and self-contained. The exporter writes a new staging
directory, closes all handles, validates every output, then promotes the generation
as the current view. It never updates the current generation in place. The last
known good generation stays available for rollback. If Windows cannot safely switch
the current view while Obsidian is open, refresh stops and reports that condition.

## Labels and manifest

Every rendered note must begin with a plain-language banner. The same facts must be
present in a machine-readable generation manifest. Labels are display metadata, not
runtime authority.

| Label | Required value |
|---|---|
| Source | Repository-relative path and full commit, or memory ID and record version |
| Source type | Governance, decision, acceptance, current state, architecture, historical evidence, governed memory, future RAG, or corrective lesson |
| Review classification | `ProductOwnerReview`, `SensitiveLocal`, or `Excluded` |
| Authority class | Canonical governance, accepted decision record, scoped acceptance record, descriptive current source, canonical governed memory, historical source, or future placeholder |
| View status | Always `Derived read-only projection` for generated notes |
| Source hash | SHA-256 of the exact source bytes used |
| Generated | Timezone-aware local generation time and UTC equivalent |
| Freshness | One of the states below |
| Conflict | `None`, `Reported`, `Corrupt`, `Unsupported`, or `Unknown` with linked details |

Proposed freshness states are:

- `Verified at source commit`: the source's recorded verification commit equals the
  projected source commit.
- `Changed since recorded verification`: Git shows the source changed after its
  recorded verification commit.
- `No recorded verification`: the source has no recognized verification metadata.
- `Historical`: the source is intentionally historical and receives no currentness
  claim.
- `Future capability not implemented`: the note describes an accepted future
  objective without claiming implementation.
- `Projection stale`: a newer approved source generation is known or the configured
  maximum age has elapsed.
- `Unknown`: freshness could not be established and the view fails closed rather
  than calling the source current.

Freshness parsing is presentation logic only. It cannot change authority,
acceptance, source inclusion, or runtime behavior. When two sources conflict, the
view shows both claims, their source types, versions, and the applicable repository
precedence guidance. It must not ask a model to merge or choose between them.

The generation manifest should record exporter version, catalog version, generation
ID, source commit, source paths or memory IDs, source and output hashes, inclusion or
exclusion reason, link diagnostics, validation results, generation times, and the
prior generation ID. A manifest hash detects later projection modification. It is
integrity evidence for the view, not a signature of Product Owner acceptance.

## Threat model

The protected assets are canonical policy and documentation, canonical governed
memory, acceptance evidence, private information, Product Owner understanding of
authority and freshness, and GRACI runtime independence.

| Threat | Failure | Required controls |
|---|---|---|
| Writeback | Obsidian or a viewer changes a canonical file or memory record | One-way projection, source opened read-only, separate viewer identity, source ACL without viewer write/delete/change rights, no import or reverse-sync command, source hashes checked before and after acceptance |
| Plugins | A community or unexpected plugin reads broader files, changes notes, runs code, or uses the network | No community plugins in the accepted baseline, no plugin directory content, restricted identity, outbound network block for the exact application, settings verification before launch |
| Scripts and active content | Markdown, HTML, URI handlers, templates, or attachments cause execution | Text-only renderer, raw HTML and active embeds escaped, no executable attachments, no shell/template plugin, execution denied from projection paths, adversarial fixtures |
| Links and embeds | A note opens an external site, private local path, image tracker, or application URI | Rewrite only cataloged relative Markdown links, disable remote embeds, render unsupported schemes as inert text, mark external references without making them active by default |
| Path escape | Relative paths, absolute paths, UNC paths, device paths, symlinks, junctions, or reparse points escape an approved root | Resolve and compare every path against its configured root, reject traversal and alternate data streams, reject reparse points, allow direct child UUID JSON memory files and cataloged repository paths only |
| Secrets and sensitive content | Credentials, tokens, private keys, personal data, prompts, or unrelated memory appear in the projection | Explicit source and record allowlists, metadata-only memory default, field allowlist, bounded secret scan, no environment or raw run export, fail closed on uncertain classification, local encrypted storage where already available |
| Stale projection | The Product Owner mistakes an old view for current state | Prominent generation age and source commit, maximum-age warning, currentness comparison during refresh, no silent refresh failure, last successful generation and failure notice shown together |
| Prompt injection and false authority | Displayed content tells a human or later model to ignore policy or claims that viewing grants permission | Untrusted-content banners, authority-class labels, active-content escaping, no GRACI runtime consumption, no Markdown-to-permission parser, adversarial instruction fixtures |
| Accidental authority inference | A copy, graph edge, backlink, tag, or popular note looks authoritative | `Derived read-only projection` on every note, source type and scope visible, graph styling cannot alter labels, no generated conclusions presented as decisions or acceptance |
| Projection tampering | A same-host process modifies rendered notes after validation | Read-only content ACL for the viewer, manifest and output hashes, verify-on-open launcher or explicit verification step, preserve prior generation |
| Exporter compromise or error | The exporter leaks data, changes sources, or creates a misleading view | Minimal local implementation, no network, no model calls, explicit schemas and catalogs, separate input/output roots, source before/after hashes, deterministic tests, failure without promotion |

Obsidian note text remains untrusted even when it originated in canonical policy.
The source's authority comes from the repository and accepted governance, not from
the rendering application.

## Least-privilege Windows design

The enforceable baseline should use a dedicated standard local viewer identity,
provisionally named `GRACI_Review`. The name is not approved configuration. The
identity has no administrator membership, no GRACI runtime role, no 4090 remoting
credential, and no access to credential stores used by GRACI.

The recommended access matrix is:

| Location or capability | Exporter identity | Viewer identity | GRACI runtime |
|---|---|---|---|
| Selected repository commit objects | Read | No access | Existing access unchanged |
| Canonical memory root | Read only for approved export | No access | Existing governed access unchanged |
| Projection staging | Create and validate | No access | No access |
| Promoted projection content | Replace by generation | Read and traverse only | No access required |
| Obsidian local settings | No access required | Write only where Obsidian needs local user state | No access |
| Network | None | Block outbound for Obsidian | Existing policy unchanged |
| Executable launch from projection | Denied | Denied | Not applicable |

NTFS permissions should remove inherited broad write access at the projection root.
The viewer receives read and traverse on promoted content but not create, append,
write, delete, rename, ownership, or permission-change rights. The exporter can
create staging and promote a validated generation, but it receives only read access
to inputs. A deployment operator, not Obsidian, owns ACL changes.

Obsidian requires some per-vault state. Its configuration directory should be
pre-created during a separately authorized deployment, restricted to the viewer,
and limited to approved core behavior. Community plugins remain disabled and absent.
If Obsidian cannot operate while content remains read-only, that is an acceptance
failure, not a reason to grant source write access.

Windows Firewall should block outbound traffic from the exact reviewed Obsidian
executable. An application-control rule should deny execution from the projection
and staging roots. The exact control can be WDAC, AppLocker, or the strongest
available supported mechanism selected during implementation. BitLocker or an
equivalent existing at-rest control should protect sensitive local projections, but
Phase 8E must first inspect and report the host's actual protection rather than
assume it.

Stage 2 subsequently confirmed that `E:` is not BitLocker-protected. The Product
Owner accepted that physical-security risk and prohibited installing, enabling,
configuring, or deploying BitLocker on either system. That later decision supersedes
BitLocker as a prerequisite without authorizing real data or a later Phase 8E stage.

## Update, verification, failure, and recovery

### Refresh

Each personalized-memory change requires explicit current Product Owner approval. A
direct verbal or PTT request to remember a stated preference, method, task procedure,
correction, or lesson may approve that exact memory. After the canonical memory is
accepted, a future G.R.A.C.I. maintainer may include it in a bounded vault refresh
without asking the Product Owner to repeat the lesson. The refresh still uses an
exact local Git commit, catalog version, memory-view mode, and approved memory IDs.
One approval does not permit unrelated memory changes or become standing automatic
write permission. The refresh makes no network request and performs no model call.

The exporter performs these steps:

1. Resolve and record all input roots, the full Git commit, catalog, and requested
   memory IDs.
2. Reject missing, ambiguous, external, reparse-point, unapproved, or unsupported
   inputs.
3. Hash source bytes and generate a complete staging projection using only
   allowlisted fields and deterministic transformations.
4. Escape active content, rewrite approved internal links, and report every omitted
   or unresolved link.
5. Validate labels, schemas, hashes, link targets, path containment, secret checks,
   and the absence of executable content and plugin payloads.
6. Recheck input hashes. If any input changed, discard staging and report a source
   race.
7. Promote the complete generation and record it as current. Never modify a prior
   generation in place.

### Verification

The review launcher or a separate read-only check verifies the manifest, every
output hash, ACL expectations, generation age, source commit availability, and
approved settings before opening the view. A failure must remain visible. The tool
must not relabel a failed or stale generation as current.

### Failure behavior

Any parse, validation, link, path, ACL, source-race, secret, or promotion uncertainty
fails closed. The current last-known-good projection remains unchanged. The failed
staging generation is not opened. A local diagnostic identifies the generation,
source, check, and safe recovery action without including excluded content or
secrets.

Obsidian launch failure, projection deletion, or projection corruption has no effect
on GRACI. The Product Owner can continue to use the repository and GRACI normally.

### Rollback and recovery

Rollback selects a previously validated immutable generation after rechecking its
manifest and ACLs. It never changes canonical sources. Recovery can rebuild any
projection from the recorded local source commit and still-available canonical
memory versions. If an old memory version is no longer canonical or available, the
view must report that fact rather than reconstruct content from an old projection
and treat it as canonical.

Generation retention and deletion require a separately approved local retention
rule because projections may contain sensitive memory. Until that rule exists, the
implementation must not automatically delete or retain an unlimited set of real-data
generations.

## Verification plan

### Deterministic tests

- Catalog accepts only exact approved repository paths and supported source types.
- Source resolution rejects traversal, absolute escape, UNC and device paths,
  alternate data streams, symlinks, junctions, and other reparse points.
- Repository export is pinned to the requested commit and ignores working-tree and
  untracked files.
- Every note and manifest entry carries the required source, classification,
  canonical-versus-derived, freshness, hash, and conflict fields.
- Memory metadata-only mode omits content and free-form source references.
- Approved-content mode includes only exact approved record IDs and marks content
  untrusted.
- Superseded, expired, tombstoned, conflicting, corrupt, and unsupported memory
  states remain distinct and are never silently reconciled.
- Raw HTML, scripts, remote images, file links, application URIs, executable
  attachments, and instruction-like content remain inert.
- Secret fixtures fail closed without placing matched material in diagnostics.
- Broken or excluded links are visible diagnostics and cannot escape the
  projection.
- A source change during generation prevents promotion.
- Any staging failure leaves the current generation byte-for-byte unchanged.
- Manifest or note tampering is detected before a clean launch result.
- No exporter module is imported by ordinary GRACI runtime composition.

### Windows and integration tests

- Under the viewer identity, create, edit, append, rename, delete, ownership, and
  ACL-change attempts fail against repository, canonical memory, and projection
  content.
- The viewer can read the promoted notes and only the approved application-state
  location is writable.
- Obsidian starts with no community plugins and cannot reach an external test
  endpoint.
- Obsidian cannot execute a benign probe placed in the projection test fixture.
- Opening, navigating, searching, graphing, and closing a representative projection
  leaves all canonical source hashes unchanged.
- Removing Obsidian and the entire projection does not change GRACI startup,
  conversation, policy tests, memory tests, or 3090-only operation.
- A failed refresh and a rollback both preserve the last-known-good view and produce
  truthful diagnostics.

### Product Owner acceptance criteria

Acceptance remains a separate explicit event. The Product Owner should be able to:

1. Find current governance, policy IDs, decisions, current status, roadmap, known
   issues, capability state, and every durable acceptance record from a home page.
2. Identify, on every note, the exact source, source version, review classification,
   authority class, derived status, freshness, and conflict state.
3. Distinguish policy, current description, implementation, deployment, automated
   verification, live observation, historical evidence, and Product Owner
   acceptance without relying on graph position or styling.
4. Review an approved memory sample and confirm that metadata-only records reveal no
   content while approved-content records remain visibly untrusted and traceable.
5. See explicit not-implemented views for RAG and corrective learning rather than
   empty pages that imply missing data or completed capability.
6. Observe a stale-source warning, a conflict, a corrupt-memory diagnostic, a
   blocked external link, and a failed refresh in controlled fixtures.
7. Confirm that attempted edits do not change canonical or projected content and
   that no community plugin or external connection is active.
8. Confirm that deleting or withholding the projection does not affect GRACI and
   that a prior generation can be restored without changing canonical sources.

Automated PASS, correct ACLs, successful installation, and a usable demonstration
do not establish Product Owner acceptance by themselves.

## Staged implementation proposal and authorization boundaries

### Stage 0: design acceptance

The Product Owner reviews this proposal, selects the architecture and privacy
choices listed at the end, and either accepts the design or requests revisions.
Design acceptance does not authorize code, installation, Windows changes,
deployment, or real-data projection.

### Stage 1: exporter and fixture-only verification, accepted

The accepted implementation adds the typed source catalog, local deterministic
exporter, renderer, manifest, fixture corpus, and focused tests. It uses synthetic
memory only and does not install Obsidian, alter ACLs, or read the real memory root.
The Product Owner acceptance boundary is recorded in `ACC-0007`.

### Stage 2: local projection and Windows hardening, accepted

The Product Owner authorized inspection, exact control selection, implementation,
rollback, and synthetic verification of the dedicated viewer boundary, projection
and staging roots, content ACLs, projection-path application-control rule, and a
bounded local launcher. Exact supported host facts and the selected plan must be
recorded before dependent mutation. This Windows security scope still does not
authorize Obsidian installation, application settings, network or firewall changes,
or reading real memory.

### Stage 3: Obsidian qualification and configuration

The Product Owner reports that Obsidian is already installed but has never been
used. After separate Stage 3 authorization, inspect the exact installed version and
path, verify provenance and hash, test it against the fixture projection, and record
its licenses and update behavior. Configure it only for the isolated viewer. Apply
the exact executable firewall rule and approved local application settings at this
stage. No community plugins are included. Reinstallation, production use, and
future upgrades remain separate decisions.

The first authorized candidate test used the Product Owner's existing per-user
installation. The review token could read the executable and synthetic projection,
but Obsidian did not remain running or register the synthetic vault. The test failed
closed and restored the original permissions and firewall state. This candidate is
not qualified. The Product Owner then authorized a separate copy in the review
profile. The exact verified copy passed the real review-token synthetic test,
including vault registration, note readability, immutable-generation write denial,
and the viewer-only outbound block. The Product Owner retained read access and its
existing Obsidian installation and settings were unchanged. Product Owner acceptance,
routine launch, real data, and later stages remain separate decisions. The Product
Owner subsequently accepted Stage 3 and authorized routine launch, commit, and push.
The promoted launcher passed under the real review token. Real data, automatic
refresh, runtime integration, and Stage 4 remain unauthorized.

### Stage 4: bounded real-data generation

After the Product Owner approves the exact repository commit, source catalog,
memory mode, and any content-bearing memory IDs, generate and verify the first local
projection. Do not include raw run records, unrelated history, future RAG content,
or corrective lessons that lack accepted schemas.

### Stage 5: controlled acceptance and promotion

Run the deterministic, Windows, independence, privacy, failure, rollback, and human
review procedures. Record automated verification, live observation, deployment, and
Product Owner acceptance separately. Commit, push, operational promotion, and any
automatic refresh remain separately authorized actions.

## Prioritized recommendations

1. **Security: use generated projection plus a dedicated viewer identity.** This is
   the strongest control against source writeback and plugin reach. It costs account,
   ACL, and launch complexity. Acceptance should include real denied-write tests.
2. **Security and privacy: default governed memory to metadata-only.** Content
   should require an exact per-generation allowlist. This limits accidental exposure
   while still making lifecycle, provenance, and conflict state reviewable.
3. **Reliability: export from an exact local commit and use immutable generations.**
   This avoids working-tree ambiguity and makes refresh, stale-state detection, and
   rollback deterministic. It costs additional local storage.
4. **Functionality: build one home note around authority and evidence state.** The
   first view should optimize finding policy, decisions, acceptance, current status,
   roadmap, and issues. Graph appearance is secondary to explicit labels.
5. **Reliability and security: keep rendering deterministic and model-free.** A
   model-generated summary could omit scope or invent reconciliation. Phase 8E
   should render and index only source facts through bounded code.
6. **Ease of use: provide one explicit refresh and one verify-and-open action.** The
   interface should show last success, source commit, age, and failure state without
   requiring Git or PowerShell knowledge. Scheduling can be considered only under a
   later explicit grant.
7. **Future compatibility: reserve typed view adapters for RAG and corrective
   lessons, but do not implement their schemas in Phase 8E.** This keeps Phase 10
   authority and data design separate while avoiding a dead-end renderer.

## Product Owner decisions and current authorization

On 2026-09-02, the Product Owner accepted all six design decisions below and then
separately approved creation of the Stage 1 implementation task. After reviewing the
verified candidate, the Product Owner accepted Stage 1 and authorized its commit and
fast-forward push to `main`. The Product Owner also authorized all Stage 2 work
within this design.

1. Accept this design as written or identify required revisions.
2. Approve generated one-way projection as the Phase 8E architecture and reject
   direct repository viewing from the accepted baseline.
3. Approve the initial repository source catalog described in this proposal,
   including index-only treatment of historical phase material and exclusion of raw
   run records.
4. Choose governed-memory scope: recommended metadata-only default, with content
   included only by exact Product Owner-approved memory IDs, or a narrower policy.
5. Approve the dedicated standard viewer identity, source isolation, read-only
   projection ACL, no-community-plugin baseline, outbound network block, and local
   application-control requirement.
6. Authorize Stage 1 fixture-only implementation and tests, while explicitly leaving
   Obsidian installation, Windows configuration, real-memory access, real-data
   generation, deployment, commit, push, and Product Owner acceptance unauthorized.

Stage 2 and Stage 3 are now Product Owner accepted. PO-DEC-033 authorized routine
launch, commit, and push for the exact dedicated Obsidian configuration. PO-DEC-034
records the required product outcome: approved personal knowledge must be readable
in Obsidian and reusable by G.R.A.C.I. Adding or changing a durable memory requires
explicit current Product Owner approval; later in-scope retrieval and projection of
that accepted memory do not require the lesson to be repeated. Separate decisions
are still required for personalized-memory design, real-data source selection, the
first real-data projection, automatic refresh, runtime integration, and Stages 4
and 5.
