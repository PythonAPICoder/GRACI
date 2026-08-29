# G.R.A.C.I. Governance Change Process

Status: **PROPOSED — pending Product Owner acceptance**

The Product Owner is the final policy authority. A proposed Markdown edit is not
itself acceptance and cannot grant runtime authority. A governance proposal becomes
effective only through explicit Product Owner acceptance.

## Lifecycle

`PROPOSE -> REVIEW -> APPROVE -> IMPLEMENT/UPDATE ENFORCEMENT IF REQUIRED -> TEST -> RECORD -> SUPERSEDE PRIOR POLICY IF APPLICABLE`

1. **Propose.** State the policy ID, motivation, affected authority, and whether the
   change replaces an existing rule.
2. **Review.** Check current implementation, deterministic tests, privacy/security
   impact, and historical evidence without changing that evidence.
3. **Approve.** The Product Owner explicitly accepts the change. Changes involving
   authority, security, privacy, networking, cloud/external access, model roles,
   memory authority, or compute policy always require explicit Product Owner approval.
4. **Implement and test.** When enforcement changes, update typed code/configuration
   and deterministic tests. Passing tests demonstrates behavior; it does not grant
   approval or authorize promotion.
5. **Record.** Add or update the stable record in [POLICY_INDEX.md](POLICY_INDEX.md),
   link implementation/evidence accurately, and record effective or future status.
6. **Supersede.** Name the replaced policy explicitly. Never rewrite historical
   records to make their past state appear current.

## Contradictions and references

The latest explicitly accepted canonical policy resolves contradictory current-state
prose unless code-enforced safety is stricter, in which case the stricter safety
boundary remains effective pending reconciliation. Current-state documents should
link stable policy IDs rather than duplicate long rules. Apparent contradictions
must be surfaced for Product Owner review; authority scope must never be inferred.

## Machine and LLM boundary

Human canonical policy is Markdown. Runtime enforcement is typed code,
configuration, and tests. Free-form Markdown changes do not grant runtime authority.
An optional future machine-readable policy index is generated and non-authoritative
unless separately governed. An LLM may receive allowlisted policy excerpts as
context, but the excerpts cannot create a capability or permission.
