import csv, re, zipfile, xml.etree.ElementTree as ET
from collections import defaultdict

SCRATCH = "/Users/a/.gemini/antigravity/brain/30bf29c6-684c-4e9b-89c2-241419a8f438/scratch"

def norm_tg(s):
    s = s.lower().strip().replace("ӯ", "у").replace("ӣ", "и").replace("ъ", "")
    s = re.sub(r"([бвгғджзйкқлмнпрстфхҳчҷш])\1", r"\1", s)
    return s.replace("ья", "я").replace("ье", "е").replace("ьё", "ё").replace("ью", "ю")

def expand_opt(hw):
    m = re.match(r"^([^\(]+)\(([^\)]+)\)$", hw)
    return [m.group(1), m.group(1) + m.group(2)] if m else [hw]

# Load Farhangi 2006 (exact clean file first, then oftob_tj2ru)
f2006 = defaultdict(list)
with open(f"{SCRATCH}/farhangi_2006_clean.txt", encoding="utf-8") as f:
    for ln in f:
        m = re.match(r"^([А-ЯЁҒӢҚӮҲҶ][А-ЯЁҒӢҚӮҲҶ\-'()]*(?:\s+[IVX]+)?)\s+(.+)$", ln.strip())
        if m:
            hw = re.sub(r"\s+[IVX]+$", "", m.group(1)).lower()
            for v in expand_opt(hw):
                f2006[norm_tg(v)].append((v, m.group(2)))

# Load dictionary.csv
with open("/Users/a/Dev/tajikdictionaryios/data/source/dictionary.csv", encoding="utf-8") as f:
    app = list(csv.DictReader(f))

# 1. Check all zero-overlap entries in f2006
def toks(s):
    return set(re.findall(r"[а-яё]{3,}", s.lower()))

mismatches = []
for i, r in enumerate(app, 2):
    tg = r["tg"].strip()
    ntg = norm_tg(tg)
    if ntg not in f2006:
        continue
    # Prefer exact headword match if available
    exact = [b for hw, b in f2006[ntg] if hw == tg.lower()]
    entries = exact if exact else [b for _, b in f2006[ntg]]
    book_ru = " | ".join(entries)
    rt = toks(r["ru"])
    bt = toks(book_ru)
    # Exclude stem-only differences (first 4 chars)
    rt4 = {t[:4] for t in rt}
    bt4 = {t[:4] for t in bt}
    if rt4 and bt4 and not (rt4 & bt4) and "см." not in book_ru.lower():
        mismatches.append((i, tg, r["pos"], int(r["frequency"] or 0), r["ru"], r["en"], book_ru))

print(f"Strong RU 4-char-stem zero-overlap mismatches against Farhangi 2006: {len(mismatches)}")
for m in sorted(mismatches, key=lambda x: -x[3])[:60]:
    print(f"  L{m[0]} f={m[3]:>3} {m[1]} ({m[2]}): APP_RU={m[4]!r} || BOOK={m[6][:100]!r}")

# 2. Check English entries with suspicious words or broken patterns
en_issues = []
bad_en_patterns = [
    (r"\bquite\b(?!\s+(a|good|well|often|enough|so|the|different|sure|right|clear|another))", "quite vs quiet?"),
    (r"\bgentile\b", "gentile vs gentle?"),
    (r"\bnucleolus\b", "nucleolus vs kernel?"),
    (r"\bclever piece of work\b", "clever piece"),
    (r"\b(about|for)\s+(grain|horse|child|clothes|gate|person|fruit|bread|water|dog)\b", "machine-translated parenthetical"),
    (r";\s*(a|an|the|of|with|in|on|at|for|to|by|from)\s*$", "dangling preposition"),
]
for i, r in enumerate(app, 2):
    en = r["en"]
    for pat, label in bad_en_patterns:
        if re.search(pat, en, re.I):
            en_issues.append((i, r["tg"], label, en[:80]))
            break
print(f"\nSuspicious EN patterns: {len(en_issues)}")
for x in en_issues[:35]:
    print(" ", x)
