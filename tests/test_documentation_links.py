"""Guard against broken inline links in distributed Markdown documentation."""
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_distributed_markdown_relative_links_exist():
    files = list(ROOT.glob("*.md"))
    for directory in (ROOT / "docs", ROOT / "examples", ROOT / "tests" / "fixtures"):
        files.extend(directory.rglob("*.md"))

    broken = []
    for source in files:
        text = source.read_text(encoding="utf-8")
        for raw_target in re.findall(r"(?<!!)\[[^]]*\]\(([^)]+)\)", text):
            target = raw_target.strip().split()[0].strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative = urllib.parse.unquote(target.split("#", 1)[0])
            if relative and not (source.parent / relative).resolve().exists():
                broken.append(f"{source.relative_to(ROOT)}: {target}")

    assert not broken, "Broken relative Markdown links:\n" + "\n".join(broken)
