import csv, re, zipfile, xml.etree.ElementTree as ET, json
from collections import defaultdict

SCRATCH = "/Users/a/.gemini/antigravity/brain/30bf29c6-684c-4e9b-89c2-241419a8f438/scratch"

def norm_tg(s):
    s = s.lower().strip().replace("ӯ", "у").replace("ӣ", "и").replace("ъ", "")
    s = re.sub(r"([бвгғджзйкқлмнпрстфхҳчҷш])\1", r"\1", s)
    return s.replace("ья", "я").replace("ье", "е").replace("ьё", "ё").replace("ью", "ю")

def expand_opt(hw):
    m = re.match(r"^([^\(]+)\(([^\)]+)\)$", hw)
    return [m.group(1), m.group(1) + m.group(2)] if m else [hw]

# Load all Tajik reference headwords
ref_tg_all = set()
f2006_exact = defaultdict(list)
with open(f"{SCRATCH}/farhangi_2006_clean.txt", encoding="utf-8") as f:
    for ln in f:
        m = re.match(r"^([А-ЯЁҒӢҚӮҲҶ][А-ЯЁҒӢҚӮҲҶ\-'()]*(?:\s+[IVX]+)?)\s+(.+)$", ln.strip())
        if m:
            hw = re.sub(r"\s+[IVX]+$", "", m.group(1)).lower()
            for v in expand_opt(hw):
                ref_tg_all.add(norm_tg(v))
                f2006_exact[v].append(m.group(2))

with zipfile.ZipFile(f"{SCRATCH}/oftob_tj2ru.xlsx") as z:
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strs = ["".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")) for si in root.findall("s:si", ns)]
    sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    for row in sheet.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
        vals = []
        for c in row:
            t = c.attrib.get("t")
            v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
            vals.append("" if v is None or v.text is None else (strs[int(v.text)] if t == "s" else v.text))
        if len(vals) >= 2 and vals[0].strip() and vals[0] not in ("TJ", "HTTP://OFTOB.COM"):
            for v in expand_opt(vals[0].strip().lower()):
                ref_tg_all.add(norm_tg(v))

with open(f"{SCRATCH}/egslava_taj_rus.csv", encoding="utf-8", errors="replace") as f:
    for ln in f:
        if "%" in ln:
            hw = ln.split("%", 1)[0].strip().lower()
            for v in expand_opt(hw):
                ref_tg_all.add(norm_tg(v))

with open(f"{SCRATCH}/oftob_tj2en.csv", encoding="utf-8") as f:
    for r in csv.reader(f):
        if len(r) >= 2 and r[0].strip():
            ref_tg_all.add(norm_tg(r[0]))

with open(f"{SCRATCH}/kaikki-tg.jsonl", encoding="utf-8") as f:
    for ln in f:
        try:
            o = json.loads(ln)
            if o.get("word"):
                ref_tg_all.add(norm_tg(o["word"]))
        except Exception:
            pass

# Also extract all Tajik words appearing in egslava_rus_taj.csv
with open(f"{SCRATCH}/egslava_rus_taj.csv", encoding="utf-8", errors="replace") as f:
    for ln in f:
        for w in re.findall(r"[а-яёғӣқӯҳҷ]{2,}", ln.lower()):
            if re.search(r"[ғӣқӯҳҷ]", w):
                ref_tg_all.add(norm_tg(w))

with open("/Users/a/Dev/tajikdictionaryios/data/source/dictionary.csv", encoding="utf-8") as f:
    app = list(csv.DictReader(f))

unattested_single = []
for i, r in enumerate(app, 2):
    tg = r["tg"].strip()
    if " " in tg or "-" in tg:
        continue
    if tg[0].isupper():
        continue
    if norm_tg(tg) not in ref_tg_all:
        unattested_single.append((i, tg, r["pos"], int(r["frequency"] or 0), r["ru"], r["en"]))

print(f"Single-word lowercase entries not attested in ANY of the 5 reference sources: {len(unattested_single)}")
for x in sorted(unattested_single, key=lambda x: -x[3])[:60]:
    print(" ", x)
EOF
