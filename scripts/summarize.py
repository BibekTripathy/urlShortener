"""Turn JUnit XML files in results/ into SUMMARY.md and update the README block."""

import re
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

root = Path(sys.argv[1])
results = root / "results"
suites = {"Backend (pytest)": "backend-junit.xml", "Frontend (vitest)": "frontend-junit.xml"}

rows, failures = [], []
for name, fname in suites.items():
    f = results / fname
    if not f.exists():
        rows.append(f"| {name} | – | – | – | – | not run |")
        continue
    total = fail = skip = 0
    secs = 0.0
    for case in ET.parse(f).getroot().iter("testcase"):
        total += 1
        secs += float(case.get("time") or 0)
        if case.find("failure") is not None or case.find("error") is not None:
            fail += 1
            failures.append(f"- `{name}` {case.get('classname')}::{case.get('name')}")
        elif case.find("skipped") is not None:
            skip += 1
    status = "✅ pass" if fail == 0 else "❌ fail"
    rows.append(f"| {name} | {total} | {total - fail - skip} | {fail} | {secs:.2f}s | {status} |")

stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
table = "\n".join([
    f"_Last run: {stamp}_",
    "",
    "| Suite | Tests | Passed | Failed | Time | Status |",
    "|---|---|---|---|---|---|",
    *rows,
    *(["", "**Failures**", *failures] if failures else []),
])

(results / "SUMMARY.md").write_text(f"# Test results\n\n{table}\n\nRaw reports: "
                                    + ", ".join(f"[{v}]({v})" for v in suites.values()) + "\n")

readme = root / "README.md"
text = readme.read_text()
block = f"<!-- TESTS:START -->\n{table}\n<!-- TESTS:END -->"
text = re.sub(r"<!-- TESTS:START -->.*?<!-- TESTS:END -->", lambda _: block, text, flags=re.S)
readme.write_text(text)
print(table)
