"""Generated reference docs must match the code."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gen_reference", ROOT / "scripts" / "gen_reference.py")
gen_reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_reference)


@pytest.mark.parametrize("page", sorted(gen_reference.PAGES))
def test_reference_page_is_current(page):
    committed = (ROOT / "docs" / "reference" / page).read_text()
    assert committed == gen_reference.PAGES[page](), (
        f"docs/reference/{page} is stale; run: uv run python scripts/gen_reference.py"
    )


def test_relative_links_resolve():
    """Every relative markdown link in README.md and docs/ points at a file that exists."""
    import re

    broken = []
    for md in [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]:
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", md.read_text()):
            if not re.match(r"[a-z]+:", target) and not (md.parent / target).exists():
                broken.append(f"{md.relative_to(ROOT)} -> {target}")
    assert not broken, broken
