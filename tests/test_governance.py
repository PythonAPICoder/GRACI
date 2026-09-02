"""Deterministic checks for the canonical human governance layer."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE = ROOT / "governance"
INDEX = GOVERNANCE / "POLICY_INDEX.md"
POLICY_ID = re.compile(
    r"^(AUTH|AUTONOMY|EXTERNAL|TOOL|LOCAL|COMPUTE|STORAGE|MODEL|MEMORY|HUMANVIEW|SELFDEV|VOICE|DOCSTYLE|VALIDATION|EVIDENCE)-\d{3}$")
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def anchor_for(heading):
    value = heading.strip().lower()
    value = re.sub(r"[^a-z0-9 -]", "", value)
    return re.sub(r"[ -]+", "-", value).strip("-")


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.documents = {
            path.name: path.read_text(encoding="utf-8")
            for path in GOVERNANCE.glob("*.md")
        }

    def test_required_canonical_files_exist(self):
        self.assertEqual(set(self.documents), {
            "CHANGE_PROCESS.md", "CURRENT_POLICY.md", "POLICY_INDEX.md"})

    def test_index_has_unique_well_formed_ids_and_all_categories(self):
        rows = [line for line in self.documents["POLICY_INDEX.md"].splitlines()
                if line.startswith("| ") and not line.startswith("| ID ")]
        ids = [line.split("|")[1].strip() for line in rows]
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(set(ids)))
        for policy_id in ids:
            self.assertRegex(policy_id, POLICY_ID)
        self.assertEqual({policy_id.split("-")[0] for policy_id in ids},
                         set(POLICY_ID.pattern[2:].split(")", 1)[0].split("|")))

    def test_all_relative_links_and_markdown_anchors_resolve(self):
        for name, text in self.documents.items():
            source = GOVERNANCE / name
            for target in LINK.findall(text):
                path_text, _, fragment = target.partition("#")
                target_path = (source.parent / path_text).resolve() if path_text else source
                with self.subTest(source=name, target=target):
                    self.assertTrue(target_path.is_file())
                    if fragment and target_path.suffix.lower() == ".md":
                        headings = [anchor_for(line.lstrip("# "))
                                    for line in target_path.read_text(encoding="utf-8").splitlines()
                                    if line.startswith("#")]
                        self.assertIn(fragment, headings)

    def test_authority_boundary_and_future_capabilities_are_explicit(self):
        current = self.documents["CURRENT_POLICY.md"]
        self.assertEqual(current.count("**External or cloud assistance is denied unless"), 1)
        self.assertIn("Free-form Markdown must never be", current)
        self.assertIn("future capability, not a", current)
        self.assertIn("Research and sandbox evaluation never authorize production promotion", current)
        self.assertIn("The required future Obsidian capability is a human review interface", current)
        self.assertIn("An MCP provides capability, never task authority", current)
        self.assertIn("embeddings, indexes, chunks, and caches", current)
        self.assertIn("Corrective learning does not change model weights, policy,", current)
        self.assertIn("convert one recurring task into general autonomous-follow-up authority", current)
        self.assertIn("No general document-upload or PDF-ingestion runtime path", current)
        self.assertIn("does not authorize transmitting the full résumé", current)
        self.assertIn("must not install, enable, configure, or\ndeploy BitLocker", current)
        self.assertIn("does not authorize real governed memory, real-data projection", current)
        self.assertIn("must not use the Unicode em dash character", current)
        self.assertIn("not permission to conceal or misrepresent", current)
        self.assertNotIn(".obsidian", "\n".join(self.documents))

    def test_current_status_is_distinct_from_behavior_and_future_capability(self):
        current = self.documents["CURRENT_POLICY.md"]
        index = self.documents["POLICY_INDEX.md"]
        change = self.documents["CHANGE_PROCESS.md"]
        self.assertIn("Status: **CURRENT: accepted by the Product Owner**", current)
        self.assertIn("Status: **CURRENT: accepted by the Product Owner**", change)
        self.assertIn("`CURRENT / IMPLEMENTED BEHAVIOR`", index)
        self.assertIn("`CURRENT / FUTURE CAPABILITY`", index)
        self.assertNotIn("PROPOSED", "\n".join(self.documents))
        self.assertNotIn("pending Product Owner acceptance", "\n".join(self.documents))

    def test_reviewed_authorization_safety_rules_are_explicit(self):
        current = self.documents["CURRENT_POLICY.md"]
        required = (
            "If authorization, scope, or applicability is absent, ambiguous,",
            "prior tasks, prior projects, convenience, or model inference cannot create current",
            "project completion or closure for permission",
            "must be established explicitly by the Product Owner",
            "the grant is inactive and",
            "ASK PRODUCT OWNER IF NONE",
            "accepted current governance for a **future capability**",
            "requires explicit Product Owner approval through the governance change process",
            "Every promotion or deployment of a self-developed change to G.R.A.C.I. requires",
            "this policy creates no such delegation",
        )
        for wording in required:
            with self.subTest(wording=wording):
                self.assertIn(wording, current)


if __name__ == "__main__":
    unittest.main()
