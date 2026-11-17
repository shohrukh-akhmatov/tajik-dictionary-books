import csv, re, zipfile, xml.etree.ElementTree as ET, json, unicodedata
from collections import defaultdict

SCRATCH = "/Users/a/.gemini/antigravity/brain/30bf29c6-684c-4e9b-89c2-241419a8f438/scratch"

def norm_tg(s):
    s = s.lower().strip()
    s = s.replace("ӯ", "у").replace("ӣ", "и").replace("ъ", "")
    # collapse double consonants for 1998/2011/2021 orthography matching
    s = re.sub(r"([бвгғджзйкқлмнпрстфхҳчҷш])\1", r"\1", s)
    s = s.replace("ья", "я").replace("ье", "е").replace("ьё", "ё").replace("ью", "ю")
    return s

def expand_opt_parens(hw):
    # e.g. ДЕҲ(А) -> [деҳ, деҳа]
    m = re.match(r"^([^\(]+)\(([^\)]+)\)$", hw)
    if m:
        return [m.group(1), m.group(1) + m.group(2)]
    return [hw]

# 1. Load Farhangi 2006
f2006_raw = defaultdict(list)
f2006_norm = defaultdict(list)
with open(f"{SCRATCH}/farhangi_2006_clean.txt", encoding="utf-8") as f:
    for ln in f:
        m = re.match(r"^([А-ЯЁҒӢҚӮҲҶ][А-ЯЁҒӢҚӮҲҶ\-'()]*(?:\s+[IVX]+)?)\s+(.+)$", ln.strip())
        if m:
            hw_base = re.sub(r"\s+[IVX]+$", "", m.group(1)).lower()
            for v in expand_opt_parens(hw_base):
                f2006_raw[v].append(m.group(2))
                f2006_norm[norm_tg(v)].append((v, m.group(2)))

# 2. Load oftob_tj2ru.xlsx
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
            for v in expand_opt_parens(vals[0].strip().lower()):
                f2006_raw[v].append(vals[1].strip())
                f2006_norm[norm_tg(v)].append((v, vals[1].strip()))

# 3. Load egslava_taj_rus.csv
try:
    with open(f"{SCRATCH}/egslava_taj_rus.csv", encoding="utf-8", errors="replace") as f:
        for ln in f:
            if "%" in ln:
                hw, body = ln.split("%", 1)
                for v in expand_opt_parens(hw.strip().lower()):
                    f2006_raw[v].append(body.strip())
                    f2006_norm[norm_tg(v)].append((v, body.strip()))
except Exception as e:
    print("egslava_taj_rus err:", e)

# 4. Load OpenRussian (RU -> EN)
ru_to_en = defaultdict(set)
for fn in ("openrussian-adj.csv", "openrussian-nouns.csv", "openrussian-verbs.csv", "openrussian-others.csv"):
    try:
        with open(f"{SCRATCH}/{fn}", encoding="utf-8", errors="replace") as f:
            r = csv.DictReader(f, delimiter="\t")
            for row in r:
                bare = (row.get("bare") or "").strip().lower()
                en = (row.get("translations_en") or "").strip().lower()
                if bare and en:
                    for part in re.split(r"[;,/]", en):
                        p = re.sub(r"\([^)]*\)", "", part).strip()
                        if p:
                            ru_to_en[bare].add(p)
    except Exception:
        pass

# 5. Load oftob_tj2en.csv & kaikki-tg.jsonl
tj2en = defaultdict(list)
with open(f"{SCRATCH}/oftob_tj2en.csv", encoding="utf-8") as f:
    for r in csv.reader(f):
        if len(r) >= 2 and r[0].strip():
            tj2en[norm_tg(r[0])].append(r[1].strip())
with open(f"{SCRATCH}/kaikki-tg.jsonl", encoding="utf-8") as f:
    for ln in f:
        try:
            o = json.loads(ln)
            w = o.get("word", "").strip()
            for s in o.get("senses", []):
                for g in s.get("glosses", []):
                    tj2en[norm_tg(w)].append(g)
        except Exception:
            pass

# 6. Audit dictionary.csv
with open("/Users/a/Dev/tajikdictionaryios/data/source/dictionary.csv", encoding="utf-8") as f:
    app = list(csv.DictReader(f))

print(f"Refs: f2006_norm={len(f2006_norm)}, openrussian_ru={len(ru_to_en)}, tj2en={len(tj2en)}, app={len(app)}")

def toks(s):
    return set(re.findall(r"[а-яё]{3,}", s.lower()))

def en_toks(s):
    return set(re.findall(r"[a-z]{3,}", s.lower()))

bad_ru = []
archaic_only = []
bad_en_vs_or = []
typos_en = []
stray_tajik_in_ru_en = []
broken_semi = []

for i, r in enumerate(app, 2):
    tg = r["tg"].strip()
    ntg = norm_tg(tg)
    ru = r["ru"].strip()
    en = r["en"].strip()
    freq = int(r["frequency"] or 0)

    # Check stray non-ASCII in EN or Tajik chars (ғӣқӯҳҷ) in RU
    if re.search(r"[ғӣқӯҳҷ]", ru.lower()):
        stray_tajik_in_ru_en.append((i, tg, freq, "tg-char-in-ru", ru))
    if re.search(r"[^a-zA-Z0-9\s;,'’\-\.\(\)\/\?!]", en):
        stray_tajik_in_ru_en.append((i, tg, freq, "non-latin-in-en", en))

    # Check broken semicolon splits in EN
    for p in en.split(";"):
        ps = p.strip().lower()
        if ps.endswith((" a", " an", " the", " of", " with", " from", " into")) and len(ps.split()) <= 4:
            broken_semi.append((i, tg, ps, en))

    # Compare RU against Farhangi 2006
    book_entries = f2006_norm.get(ntg, [])
    if book_entries:
        book_ru = " ".join(b for _, b in book_entries)
        rt = toks(ru)
        bt = toks(book_ru)
        if rt and bt and not (rt & bt) and "см." not in book_ru.lower():
            bad_ru.append((i, tg, freq, ru[:60], book_ru[:80]))
        # Check if ALL book senses are archaic/literary (кн./уст.)
        if all(re.match(r"^(кн\.|уст\.|поэт\.)", b.strip()) for _, b in book_entries):
            if freq >= 70:
                archaic_only.append((i, tg, freq, ru[:50], book_ru[:70]))

    # Compare EN against OpenRussian (for single-word RU entries) + tj2en
    ru_items = [re.sub(r"\([^)]*\)", "", x).strip().lower() for x in ru.split(";") if x.strip()]
    or_en_all = set()
    for ritem in ru_items:
        if ritem in ru_to_en:
            or_en_all |= en_toks(" ".join(ru_to_en[ritem]))
    tj2en_all = en_toks(" ".join(tj2en.get(ntg, [])))
    app_en_toks = en_toks(en)
    if or_en_all and tj2en_all and app_en_toks:
        if not (app_en_toks & or_en_all) and not (app_en_toks & tj2en_all):
            bad_en_vs_or.append((i, tg, freq, ru[:45], en[:45], " ".join(tj2en.get(ntg, []))[:60]))

print(f"\n1. Stray Tajik/non-Latin chars in RU/EN: {len(stray_tajik_in_ru_en)}")
for x in stray_tajik_in_ru_en[:20]: print(" ", x)

print(f"\n2. Broken semicolon phrase fragments in EN: {len(broken_semi)}")
for x in broken_semi[:15]: print(" ", x)

print(f"\n3. RU zero overlap with Farhangi 2006: {len(bad_ru)}")
for x in sorted(bad_ru, key=lambda x: -x[2])[:30]: print(" ", x)

print(f"\n4. High-freq (>=70) archaic/literary-only (кн./уст.) entries: {len(archaic_only)}")
for x in sorted(archaic_only, key=lambda x: -x[2])[:25]: print(" ", x)

print(f"\n5. EN disagrees with BOTH OpenRussian AND Oftob TJ-EN: {len(bad_en_vs_or)}")
for x in sorted(bad_en_vs_or, key=lambda x: -x[2])[:30]: print(" ", x)
