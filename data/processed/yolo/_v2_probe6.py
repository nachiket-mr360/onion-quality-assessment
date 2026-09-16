"""Find pending labels whose lines are not exactly 5 whitespace-separated fields."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PENDING = ROOT / "data" / "processed" / "yolo" / "labels_pending"

bad = []
for p in sorted(PENDING.rglob("*.txt")):
    if p.name.lower() == "classes.txt":
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        ok_len = len(parts) == 5
        try:
            cid = int(float(parts[0]))
            nums = [float(x) for x in parts[1:]]
            ok_num = True
        except (ValueError, IndexError):
            ok_num = False
            nums = []
        if not ok_len or not ok_num or not (0.0 <= nums[0] <= 1.0 and 0.0 <= nums[1] <= 1.0) or nums[2] <= 0 or nums[3] <= 0:
            bad.append((str(p.relative_to(ROOT)), i, len(parts), line))

print(f"suspect lines: {len(bad)}")
for b in bad:
    print(f"  {b[0]} line {b[1]} fields={b[2]}\n    {b[3]!r}")
