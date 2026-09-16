"""Read-only inspection of current raw / pending / prepared state before V2 build."""
from __future__ import annotations

import hashlib
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
YOLO = ROOT / "data" / "processed" / "yolo"
PENDING = YOLO / "labels_pending"
IMAGES = YOLO / "images"
LABELS = YOLO / "labels"
CLS = {0: "HEALTHY", 1: "DAMAGED", 2: "ROTTEN", 3: "SPROUTED"}
IMG_EXT = {".jpg", ".jpeg", ".png"}


def stem_label(name: str) -> str:
    return name[:-8] if name.endswith(".xml.txt") else Path(name).stem


def group_key(stem: str) -> str:
    g = re.sub(r"_v[0-9]+$", "", stem)
    return g.replace("onion_sample_s-", "onion_sample_s_")


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    rows, issues = [], []
    if not text:
        return rows, ["EMPTY"]
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            issues.append(f"BAD_FIELDS({len(parts)})")
            continue
        try:
            cid = int(float(parts[0]))
            nums = [float(x) for x in parts[1:]]
        except ValueError:
            issues.append("PARSE")
            continue
        if cid not in CLS:
            issues.append(f"BAD_ID:{cid}")
        if any(not (0.0 <= n <= 1.0) for n in nums):
            issues.append("OOB")
        if nums[2] <= 0 or nums[3] <= 0:
            issues.append("NONPOS_WH")
        rows.append((cid, nums))
    return rows, issues


def scan(base: Path, exts=None):
    out = {}
    for dp, _, fs in os.walk(base):
        for f in fs:
            p = Path(dp) / f
            if exts and p.suffix.lower() not in exts:
                continue
            out[p.stem] = p
    return out


def main():
    raw = scan(RAW, IMG_EXT)
    raw_txt = scan(RAW, {".txt"})
    pending = {k: v for k, v in scan(PENDING, {".txt"}).items() if k.lower() != "classes"}

    print(f"RAW images: {len(raw)}  RAW stray txt: {sorted(raw_txt)}")
    print(f"PENDING labels: {len(pending)}")

    # prepared splits
    prepared = defaultdict(dict)
    for split in ("train", "val", "test"):
        for p in sorted((IMAGES / split).glob("*")):
            prepared[split][p.stem] = p

    print("\n== prepared counts ==")
    for split in ("train", "val", "test"):
        n = len(prepared[split])
        nlab = len(list((LABELS / split).glob("*.txt")))
        print(f"  {split}: imgs={n} labels={nlab}")

    # pending-only (not in prepared)
    prepared_stems = set()
    for s in prepared:
        prepared_stems |= set(prepared[s])
    raw_stems = set(raw)

    print("\n== NEW / UNUSED ==")
    new_pending = sorted(set(pending) - prepared_stems)
    print(f"pending not in prepared ({len(new_pending)}):")
    by_grp = defaultdict(list)
    for s in new_pending:
        by_grp[group_key(s)].append(s)
    for g in sorted(by_grp):
        print(f"  {g}: {sorted(by_grp[g])}")

    print(f"\nraw images missing pending label ({len(raw_stems - set(pending))}):")
    for s in sorted(raw_stems - set(pending)):
        print(f"  {s}")
    print(f"pending labels missing raw image ({len(set(pending) - raw_stems)}):")
    for s in sorted(set(pending) - raw_stems):
        print(f"  {s}")

    print(f"\nprepared stems with no raw source ({len(prepared_stems - raw_stems)}):")
    for s in sorted(prepared_stems - raw_stems):
        print(f"  {s} (in {[sp for sp in prepared if s in prepared[sp]]})")

    print("\n== class of pending vs prepared (where both) ==")
    mism = []
    for s in sorted(prepared_stems & set(pending)):
        pr, pi = parse(pending[s])
        sp = [sp for sp in prepared if s in prepared[sp]][0]
        lp = LABELS / sp / (s + ".txt")
        lr, li = parse(lp)
        if [c for c, _ in pr] != [c for c, _ in lr]:
            mism.append((s, [c for c, _ in pr], [c for c, _ in lr]))
    print(f"pending-label class mismatch count={len(mism)}")
    for m in mism:
        print(f"  {m}")

    print("\n== grouped pending by class / group ==")
    gc = defaultdict(set)
    for s in pending:
        rows, iss = parse(pending[s])
        for c, _ in rows:
            gc[group_key(s)].add(c)
    mixed = {g: c for g, c in gc.items() if len(c) > 1}
    print(f"groups with mixed classes in pending: {len(mixed)}")
    for g, c in sorted(mixed.items()):
        print(f"  {g}: {sorted(c)}")

    cnt = Counter()
    for s in pending:
        rows, _ = parse(pending[s])
        for c, _ in rows:
            cnt[c] += 1
    print(f"pending label-level class counts: {dict(sorted(cnt.items()))}")
    gcnt = Counter()
    for g, c in gc.items():
        for x in c:
            gcnt[x] += 1
    print(f"pending group-level class counts: {dict(sorted(gcnt.items()))}")

    # hashes for duplicate detection
    print("\n== duplicate image detection (raw, sha256) ==")
    h = defaultdict(list)
    for s, p in raw.items():
        h[sha(p)].append(s)
    dups = {k: v for k, v in h.items() if len(v) > 1}
    print(f"duplicate hash groups: {len(dups)}")
    for k, v in sorted(dups.items(), key=lambda kv: kv[1]):
        cls = [[c for c, _ in parse(pending[s])[0]] if s in pending else "NO_LABEL" for s in sorted(v)]
        print(f"  {sorted(v)} classes={cls}")

    print("\n== prepared image hashes vs raw ==")
    ph = defaultdict(list)
    for split in ("train", "val", "test"):
        for s, p in prepared[split].items():
            ph[sha(p)].append((split, s))
    for k, v in sorted(ph.items(), key=lambda kv: kv[1]):
        if len(v) > 1:
            print(f"  DUP-IN-PREPARED: {v}")

    print("\n== stray raw txt content ==")
    for s, p in raw_txt.items():
        print(f"  {p}: {p.read_text(encoding='utf-8', errors='replace')!r}")
        if s in pending:
            print(f"    pending {pending[s]}: {pending[s].read_text(encoding='utf-8', errors='replace')!r}")


if __name__ == "__main__":
    main()
