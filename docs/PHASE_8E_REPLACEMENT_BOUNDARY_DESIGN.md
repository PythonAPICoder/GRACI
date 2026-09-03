# Phase 8E replacement viewer-boundary design

> Classification: repository-only replacement design
> Authority: PO-DEC-039
> State: DESIGN APPROVED; IMPLEMENTATION AND DEPLOYMENT NOT AUTHORIZED
> Replaces: current use of the rejected Stage 2 AppLocker architecture

## Goal and boundary

Provide a read-only human view of deterministic GRACI projections without letting
the viewer write canonical sources or promoted generations. The solution must not
enable AppLocker, WDAC, Smart App Control, Code Integrity policy, or another
machine-wide application-control subsystem.

This design does not authorize Windows account, ACL, firewall, service, registry,
scheduled-task, policy, application, or live projection changes. It does not assume
that any prior Phase 8E host state exists or does not exist.

## Narrowest-control architecture

```text
approved canonical inputs
        |
bounded deterministic exporter
        |
maintainer-only staging generation
        |
strict inert-content validation + exact manifest and hashes
        |
same-volume promotion into generation-immutable projection
        |
validated explicit launcher
        |
dedicated standard viewer identity + constrained Obsidian profile
```

There is no reverse path from the viewer to canonical inputs or governed memory.
The viewer is optional and is not required for normal GRACI operation.

## Control layers

### Dedicated standard viewer identity

The viewer must be a non-administrative identity used only for human review. Its
exact existence, SID, memberships, profile, and permissions must be inspected in a
separately authorized deployment. This design does not create or modify that
identity.

### Filesystem separation

- Canonical source roots remain inaccessible to the viewer.
- Staging is maintainer-only and inaccessible to the viewer.
- Projection generations are readable by the viewer but not writable, deletable,
  renameable, ownership-changeable, or permission-changeable by it.
- Application state is separate from projected content and is writable only where
  the approved viewer application requires it.
- Promotion is same-volume and generation-based. Finalization must apply and verify
  the intended projection permissions before the pointer can select a generation.

ACLs are necessary for write isolation but do not make readable script text
non-executable. Content controls below are therefore mandatory.

### Inert exported content

The projection allowlist is limited to deterministic review data required by the
accepted viewer. The initial design permits UTF-8 Markdown, constrained JSON, and
explicitly approved static viewer configuration. The exporter and final validator
must reject:

- executable or library formats;
- PE content, including an `MZ` signature regardless of extension;
- PowerShell, batch, command, JavaScript, VBScript, Python, shell, and comparable
  executable scripts;
- shortcuts, internet shortcuts, application references, and executable URI
  schemes;
- archives, installers, disk images, and nested containers;
- alternate data streams, device paths, UNC paths, symlinks, junctions, and other
  reparse points;
- Obsidian community plugins and unapproved executable extensions;
- raw HTML, active embeds, remote media, and links that bypass the existing safe
  renderer;
- files not named in the exact manifest.

File extension alone is not trusted. Validation must inspect bounded file bytes,
path form, encoding, size, and content markers before promotion and again before
launch.

### Exact manifest and hashes

Each generation retains its source identities, source versions, output-relative
paths, byte lengths, and SHA-256 hashes. Validation must prove:

- the pointer identifies one canonical generation ID;
- every path is relative, normalized, contained, and unique;
- every manifest entry exists with the exact size and hash;
- no unmanifested files or alternate streams exist;
- the manifest and pointer are themselves authentic within the accepted local
  projection model;
- verification fails closed on any mismatch.

### Generation immutability

The exporter writes only to a new staging generation. It validates the complete
tree before promotion. A failed export or validation never modifies the selected
generation. The viewer receives access only after permission finalization succeeds.
Rollback selects a previously validated immutable generation and does not rewrite
canonical input or historical evidence.

### Constrained viewer configuration

The approved viewer baseline has no community plugins, no projection writeback, no
automatic refresh, no reverse synchronization, and no authority derived from note
content. Optional core features are disabled unless required and explicitly
validated. Network isolation is not a prerequisite in this replacement design;
any future firewall change crosses the Host System Change Approval boundary.

### Explicit validated launcher

The future launcher must:

1. fail if the exact viewer identity cannot be established;
2. verify the exact approved executable identity, publisher, version, and hash;
3. validate the pointer, manifest, output hashes, path containment, content
   allowlist, absence of reparse points, and absence of unexpected files;
4. verify that the viewer lacks projection mutation rights and source or staging
   access under a separately approved test procedure;
5. refuse to launch if any check is missing, stale, ambiguous, or failed;
6. launch only the exact application and exact selected projection path;
7. never query or require AppLocker, WDAC, Smart App Control, Code Integrity policy,
   or another global application-control state.

## Threat coverage and limits

| Threat | Primary controls | Limit |
|---|---|---|
| Viewer writes canonical data | Dedicated identity and source ACL separation | Requires separately approved real-token validation |
| Viewer changes projection | Generation ACL and immutable promotion | Another privileged host process can still change local files |
| Exported content executes | Strict type, byte, path, and active-content validation | Does not contain an unknown viewer application exploit |
| Unmanifested tampering | Complete manifest, hashes, and verify-on-open | Local privileged compromise is outside this boundary |
| Note text grants authority | Runtime never consumes projection as permission | Human review is still required for misleading content |
| Viewer application compromise | Standard identity and narrow filesystem access | Strong exploit containment would require a separately evaluated sandbox or VM |

If containment of a compromised viewer becomes a requirement, evaluate an
AppContainer, disposable virtual machine, or equivalent isolated environment. Do
not silently substitute a machine-wide application-control policy.

## Repository implementation stages

1. Implement platform-neutral content and manifest validation against synthetic
   fixtures only.
2. Add negative fixtures for disguised executables, scripts, shortcuts, archives,
   alternate streams, traversal, reparse metadata, active content, and unmanifested
   files.
3. Implement a host-independent launcher decision component that returns a bounded
   launch plan but performs no process or host mutation.
4. Review the repository implementation and request separate authority for any
   user-local validation.
5. Before any host deployment, submit the complete Host System Change Approval
   request required by `HOST-001` for each host resource that would change.

Only the design is approved now. None of these implementation or deployment stages
is authorized by PO-DEC-039 unless it is already part of this repository-only
remediation.

## Required future acceptance

A later deployment acceptance must prove the intended read-only behavior, ordinary
GRACI independence, absence of an AppLocker dependency, application usability, and
complete rollback. If any proposed step changes host configuration, its separate
approval and validation must precede execution.
