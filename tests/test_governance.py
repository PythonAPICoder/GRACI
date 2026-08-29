"""Deterministic checks for the canonical human governance layer."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE = ROOT / "governance"
INDEX = GOVERNANCE / "POLICY_INDEX.md"
POLICY_ID = re.compile(
    r"^(AUTH|AUTONOMY|EXTERNAL|LOCAL|COMPUTE|MODEL|MEMORY|SELFDEV|VOICE|VALIDATION|EVIDENCE)-\d{3}$")
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
        self.assertNotIn(".obsidian", "\n".join(self.documents))


if __name__ == "__main__":
    unittest.main()
