"""Keep the harness-specific SKILL.md copies in lockstep and standard-compliant.

EvalSurfer ships one portable agentskills.io skill in several locations so it
works with zero config across harnesses (Claude Code, Cursor, OpenClaw, Hermes,
OpenCode, Codex, ...). Every copy must be byte-identical and must carry the
required ``name`` / ``description`` frontmatter.
"""

from __future__ import annotations

import hashlib
import os
import re
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_NAME = "eval-surfer"
_SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules"}


def _discover_skill_files(root: str) -> list[str]:
    """Find every copy of *this* skill's SKILL.md, including under hidden dirs.

    Scoped to ``<...>/eval-surfer/SKILL.md`` so unrelated skills that happen
    to live in the repo (e.g. under ``.cursor/skills/``) are ignored. ``glob``
    skips hidden directories on Python < 3.11, so walk the tree explicitly to
    keep discovery portable across supported versions.
    """

    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        if os.path.basename(dirpath) == SKILL_NAME and "SKILL.md" in filenames:
            found.append(os.path.join(dirpath, "SKILL.md"))
    return sorted(found)


SKILL_PATHS = _discover_skill_files(HERE)

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as file:
        return file.read()


class SkillParityTest(unittest.TestCase):
    def test_at_least_the_three_known_copies_exist(self) -> None:
        rels = {os.path.relpath(p, HERE) for p in SKILL_PATHS}
        for expected in (
            os.path.join("skills", "eval-surfer", "SKILL.md"),
            os.path.join(".claude", "skills", "eval-surfer", "SKILL.md"),
            os.path.join(".cursor", "skills", "eval-surfer", "SKILL.md"),
        ):
            self.assertIn(expected, rels)

    def test_all_copies_are_byte_identical(self) -> None:
        digests = {
            os.path.relpath(p, HERE): hashlib.sha256(read_bytes(p)).hexdigest()
            for p in SKILL_PATHS
        }
        unique = set(digests.values())
        self.assertEqual(
            len(unique), 1, f"SKILL.md copies have drifted apart:\n{digests}"
        )

    def test_frontmatter_has_required_fields(self) -> None:
        for path in SKILL_PATHS:
            with self.subTest(path=os.path.relpath(path, HERE)):
                text = read_bytes(path).decode("utf-8")
                match = _FRONTMATTER.match(text)
                self.assertIsNotNone(match, "missing YAML frontmatter block")
                block = match.group(1)
                self.assertRegex(block, r"(?m)^name:\s*\S+", "missing 'name'")
                self.assertRegex(
                    block, r"(?m)^description:\s*\S+", "missing 'description'"
                )


if __name__ == "__main__":
    unittest.main()
