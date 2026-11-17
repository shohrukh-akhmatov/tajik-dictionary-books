# Tajik Dictionary Reference Books & Lexical Datasets

Reference dictionaries, explanatory books, lexical datasets, and alignment scripts used to audit and align the offline dictionary in [`tajikdictionaryios`](https://github.com/shohrukh-akhmatov/tajikdictionaryios) and [`tajikdictionaryandroid`](https://github.com/shohrukh-akhmatov/tajikdictionaryandroid).

## Contents

### `books/`
- `farhangi-tafsirii-zaboni-tojiki-j1.pdf` / `j2.pdf` — *Фарҳанги тафсирии забони тоҷикӣ* (Volumes 1 & 2, Academy of Sciences of Tajikistan, via khirad.tj)
- `farhangi_tojiki_rusi_2006.zip` / `.doc` / `_clean.txt` — *Фарҳанги тоҷикӣ ба русӣ* (2006, D. Saymiddinov et al., Academy of Sciences of Tajikistan, decoded to clean UTF-8 Tajik Unicode)
- `ru-tj.08.pdf` — *Новый русско-таджикский словарь* (A. Tagoev)

### `datasets/`
- `egslava_rus_taj.csv`, `egslava_taj_rus.csv` — Digitized *Русско-таджикский словарь* (1985, M. S. Osimi) & *Таджикско-русский словарь* (from `egslava/russian_tajik_dictionary`)
- `oftob_ru2tj.xlsx`, `oftob_tj2ru.xlsx`, `oftob_tj2en.xls`/`.csv`, `oftob_en2tj.xls`/`.csv` — Bilingual Russian–Tajik & English–Tajik tables (from `Oftobcom/dictionaries`)
- `kaikki-tg.jsonl` — Wiktionary Tajik lexical extract (from `kaikki.org`)
- `openrussian/` — OpenRussian CC BY-SA 4.0 Russian–English dictionary CSVs (from `Badestrand/russian-dictionary`)

### `scripts/`
- `audit_dict.py`, `check_candidates.py`, `inspect_anomalies.py` — Audit scripts for detecting mistranslations, non-Tajik loan/corrupted rows, broken phrase splits, and frequency inversions
- `align_dictionary.py` — Alignment script used to clean `data/source/dictionary.csv` and recalibrate frequencies
