import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict

SCRATCH = "/Users/a/.gemini/antigravity/brain/30bf29c6-684c-4e9b-89c2-241419a8f438/scratch"
SRC_CSV = "/Users/a/.gemini/antigravity/brain/30bf29c6-684c-4e9b-89c2-241419a8f438/scratch/baseline_dictionary.csv"
OUT_IOS = "/Users/a/Dev/tajikdictionaryios/data/source/dictionary.csv"
OUT_AND = "/Users/a/Dev/tajikdictionaryandroid/data/source/dictionary.csv"

def norm_tg(s: str) -> str:
    s = s.lower().strip().replace("ӯ", "у").replace("ӣ", "и").replace("ъ", "")
    s = re.sub(r"([бвгғджзйкқлмнпрстфхҳчҷш])\1", r"\1", s)
    return s.replace("ья", "я").replace("ье", "е").replace("ьё", "ё").replace("ью", "ю")

def expand_opt(hw: str):
    m = re.match(r"^([^\(]+)\(([^\)]+)\)$", hw)
    return [m.group(1), m.group(1) + m.group(2)] if m else [hw]

# 1. Load Farhangi 2006 registers (whether entry is literary/archaic/dialectal/poetic/historical)
f2006_entries = defaultdict(list)
with open(f"{SCRATCH}/farhangi_2006_clean.txt", encoding="utf-8") as f:
    for ln in f:
        m = re.match(r"^([А-ЯЁҒӢҚӮҲҶ][А-ЯЁҒӢҚӮҲҶ\-'()]*(?:\s+[IVX]+)?)\s+(.+)$", ln.strip())
        if m:
            hw = re.sub(r"\s+[IVX]+$", "", m.group(1)).lower()
            for v in expand_opt(hw):
                f2006_entries[v].append(m.group(2))

def book_register(tg_lower: str):
    """Returns ('literary_archaic' | 'figurative' | 'colloquial' | 'standard' | 'unknown')."""
    defs = f2006_entries.get(tg_lower, [])
    if not defs:
        return "unknown"
    # If ANY definition is unmarked standard, treat as standard unless marked
    joined = " | ".join(defs)
    if all(re.match(r"^(кн\.|уст\.|ист\.|поэт\.|обл\.|диал\.|редк\.|рел\.)", d.strip()) for d in defs):
        return "literary_archaic"
    if all(re.match(r"^(разг\.|прост\.)", d.strip()) for d in defs):
        return "colloquial"
    # Check if 'пер.' appears early while sense 1 is unrelated (like сермағз)
    if any(re.search(r"\bпер\.", d) for d in defs) and len(defs) == 1 and "1." in defs[0]:
        return "has_figurative"
    return "standard"

# 2. Load 1985 Russian-Tajik Dictionary (oftob_ru2tj.xlsx) primary equivalents weighted by OpenRussian core words
or_ru_set = set()
for fn in ("openrussian-adj.csv", "openrussian-nouns.csv", "openrussian-verbs.csv", "openrussian-others.csv"):
    with open(f"{SCRATCH}/{fn}", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            b = (row.get("bare") or "").strip().lower()
            if b:
                or_ru_set.add(b)

ru2tj_score = defaultdict(int)
with zipfile.ZipFile(f"{SCRATCH}/oftob_ru2tj.xlsx") as z:
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
        if len(vals) >= 2:
            ru_hw = vals[0].strip().lower()
            if ru_hw in ("ru", "http://oftob.com"):
                continue
            weight = 2 if ru_hw in or_ru_set else 1
            # Primary Tajik words before first example/semicolon
            head_part = re.sub(r"\([^)]*\)", "", vals[1].split(";")[0])[:90]
            # Strip Russian POS/register markers
            head_part = re.sub(r"\b(м|ж|с|мн|нескл|сов|несов|разг|кн|уст|перен|прост|спец)\.", "", head_part)
            for idx_w, w in enumerate(re.findall(r"[а-яёғӣқӯҳҷ]{2,}", head_part.lower())[:5]):
                ru2tj_score[w] += weight * (2 if idx_w < 2 else 1)

# 3. Rows to remove (exact (tg, pos, ru_prefix) or exact (tg, pos) matches that are corrupted/non-Tajik/person-name dups)
REMOVE_EXACT = {
    ("деҳа", "adj"),       # corrupted duplicate of 'ҳама' (line 436: 'весь')
    ("се", "n"),           # garbage 'се -> се | se' (keep се num три)
    ("царь", "n"),         # Russian loanword (keep шоҳ/подшоҳ/император)
    ("Эйр", "n"),          # stray 'Эйр -> Эйр | Air'
    ("ванг", "adv"),       # wrong Uzbek/corrupted 'прекрасно; хорошо'
    ("анча", "adv"),       # Uzbek word (not literary Tajik)
    ("аққол", "adv"),      # Uzbek word
    ("инзайлин", "adj"),   # Uzbek-calque dialect
    ("зиқна", "adj"),      # Uzbek word (Tajik is хасис / мумсик)
    ("майнадор", "adj"),   # colloquial/non-literary calque ("with brain" -> clever)
    ("майнанок", "adj"),   # unattested anywhere
    ("кай", "n"),          # wrong duplicate ('царь; император'; keep кай adv 'когда')
    ("парранда", "adj"),   # duplicate/noisy 'летучий; птица' (keep парранда n 'птица')
    ("хунук", "adv"),      # duplicate of хунук adj
    ("ғамгин", "adv"),     # duplicate of ғамгин adj
    ("чунин", "adj"),      # redundant noisy 'этакий' (keep чунин pron 'такой; подобный')
    ("кадом", "adj"),      # redundant noisy 'кой' (keep кадом pron 'какой; который')
    ("бадин", "prep"),     # archaic contraction 'к этому'
}

# Capitalized Tajik person names that duplicate standard words or add clutter
REMOVE_PERSON_NAMES = {
    "Тоза", "Ширин", "Нозук", "Сайёра", "Муборак", "Маъруф", "Фаррух", "Шодмон",
    "Одил", "Анвар", "Аслӣ", "Ҷалил", "Карим", "Раҳим", "Шариф", "Ҳалим",
    "Азиз", "Содиқ", "Муяссар", "Маҳмуд", "Фаридун", "Искандар", "Шералӣ",
    "Садриддин", "Абдулло", "Абдураҳмон", "Алӣ", "Аҳмад", "Муҳаммад", "Юсуф",
    "Ҳасан", "Усмон", "Лоҳутӣ", "Турсунзода", "Раҳмон", "Ғафуров", "Каримов",
    "Эмомалӣ", "Хоҷа", "Хусрав",
}

# 4. Exact book-verified corrections: (tg, pos) -> dict of fields to override
CORRECTIONS = {
    # --- Core 'clever / smart / wise' alignment ---
    ("боақл", "adj"): {"ru": "умный; разумный; рассудительный", "en": "clever; intelligent; smart; sensible", "freq": 88},
    ("доно", "adj"): {"ru": "знающий; мудрый; умный; смышлёный", "en": "wise; clever; smart; knowledgeable; learned", "freq": 88},
    ("оқил", "adj"): {"ru": "умный; разумный; рассудительный; мудрый", "en": "clever; intelligent; wise; reasonable", "freq": 85},
    ("зирак", "adj"): {"ru": "сообразительный; смышлёный; находчивый; умный", "en": "smart; clever; quick-witted; resourceful", "freq": 84},
    ("ҳушманд", "adj"): {"ru": "разумный; сообразительный; рассудительный; умный", "en": "intelligent; smart; clever; sensible", "freq": 80},
    ("бофаросат", "adj"): {"ru": "смышлёный; сообразительный; проницательный", "en": "clever; quick-witted; shrewd; perceptive", "freq": 77},
    ("боақлона", "adj"): {"pos": "adv", "ru": "умно; разумно; благоразумно", "en": "cleverly; intelligently; wisely; sensibly", "freq": 72},
    ("оқилона", "adv"): {"ru": "умно; разумно; рассудительно; мудро", "en": "wisely; cleverly; reasonably", "freq": 72},
    ("сермағз", "adj"): {"ru": "полный (о ядре ореха); наливной (о зерне); содержательный", "en": "full-kerneled; ripe (of grain); substantial", "freq": 48},
    ("ҳушевор", "adj"): {"ru": "разумный; благоразумный (кн.)", "en": "wise; prudent (literary)", "freq": 44},
    ("ақлнок", "adj"): {"ru": "разумный; умный", "en": "sensible; intelligent; clever", "freq": 56},
    ("калладор", "adj"): {"ru": "башковитый; смекалистый (разг.)", "en": "shrewd; sharp-witted (colloq.)", "freq": 52},
    ("базеб", "adj"): {"ru": "красивый; нарядный; изящный", "en": "pretty; handsome; attractive; lovely", "freq": 78},

    # --- Core everyday frequency & translation fixes ---
    ("мурғкабоб", "n"): {"ru": "жаркое из курицы", "en": "roasted chicken", "freq": 56},
    ("кудурат", "n"): {"ru": "огорчение; расстройство; плохое настроение", "en": "distress; trouble; gloomy mood; resentment", "freq": 56},
    ("некӯкорӣ", "n"): {"ru": "доброе дело; добро; добродетель", "en": "good deed; kindness; virtue", "freq": 64},
    ("айн", "n"): {"ru": "глаз; источник; суть; сущность", "en": "eye; spring; source; essence", "freq": 54},
    ("куку", "n"): {"ru": "кукушка", "en": "cuckoo", "freq": 56},
    ("ганда", "adj"): {"ru": "плохой; скверный; неприятный; плохо", "en": "bad; foul; unpleasant; badly", "freq": 82},
    ("диққат", "n"): {"ru": "внимание; сосредоточенность", "en": "attention; focus", "freq": 84},
    ("хабаркашӣ кардан", "v"): {"ru": "доносить; донести; сплетничать; ябедничать", "en": "to inform on; to report; to snitch; to gossip", "freq": 58},
    ("бад", "adj"): {"ru": "плохой; дурной; нехороший; вредный", "en": "bad; poor; harmful", "freq": 93},
    ("хуб", "adj"): {"ru": "хороший; добрый; ладно; хорошо", "en": "good; fine; well", "freq": 95},
    ("нағз", "adj"): {"ru": "хороший; славный; красивый; хорошо", "en": "good; nice; fine; well", "freq": 91},
    ("зебо", "adj"): {"ru": "красивый; прекрасный; прелестный", "en": "beautiful; lovely; pretty", "freq": 91},
    ("хона", "n"): {"ru": "дом; комната; жилище", "en": "house; home; room", "freq": 95},
    ("калид", "n"): {"ru": "ключ", "en": "key", "freq": 88},
    ("парранда", "n"): {"ru": "птица", "en": "bird", "freq": 86},
    ("деҳа", "n"): {"ru": "деревня; село; селение", "en": "village; countryside", "freq": 82},
    ("мошин", "n"): {"ru": "машина; автомобиль", "en": "car; machine; vehicle", "freq": 86},
    ("мӯй", "n"): {"ru": "волосы; волос", "en": "hair", "freq": 82},
    ("ҳадя", "n"): {"ru": "подарок; дар", "en": "gift; present", "freq": 80},
    ("дунё", "n"): {"ru": "мир; свет; вселенная", "en": "world; universe", "freq": 90},
    ("дуньё", "n"): {"ru": "мир; свет; вселенная; богатство", "en": "world; universe; wealth", "freq": 62},
    ("мағз", "n"): {"ru": "мозг; ядро (ореха, плода); сердцевина; суть", "en": "brain; kernel; pit (of fruit); core; pith", "freq": 76},
    ("пучак", "n"): {"ru": "пустой (без ядра); нарыв; фурункул", "en": "empty (without kernel); boil; abscess", "freq": 52},
    ("амн", "n"): {"ru": "мир; спокойствие; безопасность", "en": "peace; quiet; security", "freq": 72},
    ("гармоҳанг", "adj"): {"ru": "приятный; нежный; быстроходный", "en": "pleasant; gentle; swift-footed", "freq": 55},
    ("чистон", "n"): {"ru": "загадка", "en": "riddle; puzzle", "freq": 70},
    ("китобӣ", "adj"): {"ru": "книжный; литературный", "en": "bookish; literary", "freq": 68},
    ("шоҳкор", "n"): {"ru": "шедевр; выдающееся произведение", "en": "masterpiece; great work", "freq": 64},
    ("гандакорӣ", "n"): {"ru": "небрежная работа; дурной поступок", "en": "shoddy work; misconduct", "freq": 52},
    ("тафарруҷгоҳ", "n"): {"ru": "место отдыха; парк; живописное место", "en": "recreation spot; park; scenic place", "freq": 60},
    ("хушзеҳн", "adj"): {"ru": "способный; смышлёный; памятливый", "en": "bright; quick-witted; retentive; clever", "freq": 72},
    ("ҳазор", "num"): {"ru": "тысяча", "en": "thousand", "freq": 88},

    # --- Book-verified corrections for corrupted entries ---
    ("биноӣ", "n"): {"ru": "зрение; проницательность", "en": "vision; eyesight; insight", "freq": 72},
    ("биноӣ", "adj"): {"pos": "n", "ru": "зрение; проницательность", "en": "vision; eyesight; insight", "freq": 72},
    ("нуқл", "adj"): {"pos": "n", "ru": "восточные сладости; засахаренные орехи", "en": "oriental sweets; candied nuts; dragée", "freq": 54},
    ("дор", "n"): {"ru": "виселица; дерево; ствол", "en": "gallows; tree; trunk", "freq": 46},
    ("мавсум", "n"): {"pos": "adj", "ru": "называемый; именуемый", "en": "named; called", "freq": 48},
    ("обғалт", "n"): {"ru": "водоскат (тех.)", "en": "water chute; spillway", "freq": 44},
    ("соҳибкаромат", "adj"): {"ru": "чудотворец; обладающий даром творить чудеса", "en": "miracle-worker; wonderworker", "freq": 46},
    ("тур", "n"): {"ru": "богатырь (кн.); междометие (прогонять собаку)", "en": "hero (literary); shoo (at a dog)", "freq": 42},
    ("сагҷон", "n"): {"pos": "adj", "ru": "живучий; выносливый; терпеливый", "en": "hardy; resilient; tenacious", "freq": 50},
    ("барот", "n"): {"ru": "грамота; рескрипт; чек (ист.)", "en": "charter; writ; warrant (hist.)", "freq": 45},
    ("бандак", "n"): {"ru": "завязка; шнурок; связка (грам.); аффикс", "en": "tie; lace; copula (gram.); affix", "freq": 56},
    ("дониста", "n"): {"pos": "adv", "ru": "сознательно; умышленно; зная", "en": "knowingly; deliberately; intentionally", "freq": 64},
    ("байт", "n"): {"ru": "бейт; двустишие; стих", "en": "couplet; distich; verse", "freq": 64},
    ("анг", "n"): {"ru": "водопроводная труба (уст.); маркировка", "en": "clay water pipe (arch.); marking", "freq": 38},
    ("навбова", "adj"): {"pos": "n", "ru": "раннеспелый плод; первый плод; гостинец (кн.)", "en": "early fruit; firstfruit (literary)", "freq": 42},
    ("ғуч", "adj"): {"pos": "n", "ru": "бойцовый баран", "en": "fighting ram", "freq": 40},
    ("дам", "n"): {"ru": "вздох; дыхание; мгновение; миг", "en": "breath; sigh; moment; instant", "freq": 78},
    ("тӯб", "n"): {"ru": "мяч; кипа; рулон", "en": "ball; bale; roll", "freq": 76},
    ("рахш", "adj"): {"pos": "n", "ru": "блеск; конь; радуга (кн.)", "en": "gleam; steed; rainbow (literary)", "freq": 44},
    ("шомӣ", "adj"): {"ru": "сирийский; дамасский (уст.)", "en": "Syrian; Damascene (arch.)", "freq": 42},
    ("афина", "adv"): {"pos": "n", "ru": "Афины", "en": "Athens", "freq": 55},
    ("дугонагӣ", "n"): {"ru": "двойственность", "en": "duality; doubleness", "freq": 48},
    ("сареҳ", "adj"): {"ru": "ясный; чёткий; внятный; точный", "en": "clear; explicit; distinct; exact", "freq": 62},
    ("ҳаз", "num"): {"pos": "n", "ru": "доля; удел; удовольствие; наслаждение", "en": "share; lot; pleasure; delight", "freq": 46},
    ("киром", "adj"): {"pos": "n", "ru": "щедрые люди; благородные люди (кн.)", "en": "noble people; generous people (literary)", "freq": 42},
    ("наҳзат", "n"): {"ru": "движение; выступление", "en": "movement; uprising", "freq": 56},
    ("сиёҳкорӣ", "n"): {"ru": "подлость; нечестность; злодейство", "en": "baseness; dishonesty; villainy", "freq": 52},
    ("торак", "n"): {"ru": "макушка (головы)", "en": "crown of the head", "freq": 50},
    ("сомит", "n"): {"pos": "adj", "ru": "молчаливый; безмолвный; согласный (звук)", "en": "silent; mute; consonant", "freq": 44},
    ("донг", "n"): {"ru": "донг (старинная мера веса и доли)", "en": "dong (historical unit of weight)", "freq": 38},
    ("савдоӣ", "adj"): {"ru": "одержимый страстью; меланхоличный; беспокойный", "en": "impassioned; obsessed; melancholic", "freq": 48},
    ("самсом", "adj"): {"pos": "n", "ru": "острый меч (кн.)", "en": "sharp sword (literary)", "freq": 38},
    ("ҳазорхона", "n"): {"ru": "книжка (отдел желудка жвачных); сычуг", "en": "omasum (ruminant stomach)", "freq": 40},
    ("муҳиб", "adj"): {"ru": "любящий; искренний друг", "en": "loving; affectionate; sincere friend", "freq": 50},
    ("сагак", "n"): {"ru": "пряжка; застёжка", "en": "buckle; clasp", "freq": 56},
    ("танбал", "n"): {"pos": "adj", "ru": "ленивый; лентяй; лодырь", "en": "lazy; lazybones; idler", "freq": 72},
    ("тиҷоратхона", "adj"): {"pos": "n", "ru": "торговый дом; торговая фирма", "en": "trading house; commercial firm", "freq": 54},
    ("дастгирак", "n"): {"ru": "кухонные рукавицы; прихватка", "en": "oven mitts; potholder", "freq": 54},
    ("зарбат", "n"): {"ru": "молочай (бот.)", "en": "spurge; euphorbia", "freq": 42},
    ("саббоҳ", "adj"): {"ru": "пловец; корабельщик (кн.)", "en": "swimmer; sailor (literary)", "freq": 40},
    ("тик", "adv"): {"pos": "n", "ru": "тик (хлопчатобумажная ткань)", "en": "ticking (cotton fabric)", "freq": 42},
    ("калхот", "n"): {"ru": "коршун (зоол.)", "en": "kite (bird)", "freq": 52},
    ("ғозӣ", "adj"): {"pos": "n", "ru": "гази; борец за веру", "en": "ghazi; warrior for the faith", "freq": 42},
    ("бефарҳанг", "adj"): {"ru": "необразованный; некультурный; непросвещённый", "en": "uncultured; uneducated; unenlightened", "freq": 62},
    ("бунак", "n"): {"ru": "аванс; задаток (уст.)", "en": "advance payment; deposit (arch.)", "freq": 48},
    ("гузаронанда", "adj"): {"ru": "передающий; переносчик", "en": "transmitting; carrier; vector", "freq": 56},
    ("коҷ", "n"): {"ru": "ель (бот.)", "en": "spruce; fir", "freq": 62},
    ("сермаъно", "adj"): {"ru": "многозначный (лингв.)", "en": "polysemous; multi-meaning", "freq": 56},
    ("ток", "adj"): {"pos": "n", "ru": "виноград; виноградная лоза", "en": "grape; grapevine", "freq": 68},
    ("говдум", "n"): {"ru": "говдум (старинный духовой инструмент)", "en": "govdum (traditional wind horn)", "freq": 40},
    ("кӯс", "n"): {"ru": "барабан (кн.)", "en": "drum (literary)", "freq": 42},
    ("поп", "n"): {"ru": "папа римский; папа", "en": "pope", "freq": 56},
    ("хуморӣ", "adj"): {"ru": "испытывающий похмелье; томящийся желанием", "en": "hungover; yearning", "freq": 54},
    ("хӯла", "n"): {"ru": "сплав (металлов)", "en": "alloy", "freq": 58},
    ("хӯлагин", "adj"): {"ru": "сплавной; сделанный из сплава", "en": "alloy; made of alloy", "freq": 52},
    ("замингир", "n"): {"pos": "adj", "ru": "прикованный к постели; лежачий больной", "en": "bedridden", "freq": 46},
    ("сӯлама", "adj"): {"ru": "совершеннолетний; достигший зрелости (разг.)", "en": "of age; mature (colloq.)", "freq": 46},
    ("ҳанг", "n"): {"ru": "вес; мощь; эрудиция", "en": "weight; might; erudition", "freq": 44},
    ("арғун", "n"): {"ru": "быстрый конь; скакун (кн.)", "en": "swift steed; racehorse (literary)", "freq": 40},
    ("кафш", "n"): {"ru": "обувь; туфли", "en": "shoes; footwear", "freq": 76},
    ("раъно", "n"): {"pos": "adj", "ru": "красивый; миловидный; элегантный", "en": "beautiful; lovely; graceful", "freq": 58},
    ("симсор", "n"): {"ru": "маклер; посредник (кн.)", "en": "broker; middleman (literary)", "freq": 42},
    ("қадоқин", "adj"): {"ru": "скреплённый металлическими скобами (о посуде)", "en": "stapled; mended with clamps", "freq": 38},
    ("ризоӣ", "n"): {"pos": "adj", "ru": "молочный (о брате, сестре) (кн.)", "en": "foster; milk-sibling (literary)", "freq": 42},
    ("назарӣ", "adj"): {"ru": "теоретический; зрительный", "en": "theoretical; visual", "freq": 64},
    ("дамгир", "n"): {"ru": "ткань для накрывания плова; душный", "en": "plov pot cloth; stuffy", "freq": 50},
    ("даридагӣ", "adj"): {"pos": "n", "ru": "прореха; разорванное место; дыра", "en": "tear; rip; hole", "freq": 54},
    ("пастоб", "adj"): {"pos": "n", "ru": "отмель; мель", "en": "shoal; shallow", "freq": 48},
    ("сарсарӣ", "n"): {"pos": "adj", "ru": "небрежный; поверхностный; легкомысленный", "en": "careless; superficial; frivolous", "freq": 58},
    ("хушбошӣ", "n"): {"ru": "приветствие; любезности", "en": "greeting; pleasantries", "freq": 56},
    ("чакалак", "n"): {"ru": "роща; мелколесье; заросли", "en": "grove; thicket; brushwood", "freq": 56},
    ("ҳунарпеша", "n"): {"ru": "артист; актёр; ремесленник", "en": "artist; actor; artisan", "freq": 68},
    ("вингос", "n"): {"ru": "визг; повизгивание", "en": "squeal; whine; whimper", "freq": 52},
    ("гулӣ", "n"): {"ru": "гули (цветной ситец)", "en": "floral chintz", "freq": 42},
    ("себурҷа", "adj"): {"ru": "трёхбашенный", "en": "three-towered", "freq": 42},
    ("бадавӣ", "adj"): {"pos": "n", "ru": "бедуин; кочевник", "en": "Bedouin; nomad", "freq": 46},
    ("бостон", "n"): {"pos": "adj", "ru": "древний; античный; старинный", "en": "ancient; antique; old", "freq": 74},
    ("зардак", "n"): {"ru": "морковь; рыжий (разг.)", "en": "carrot; ginger (colloq.)", "freq": 64},
    ("мисмор", "adj"): {"pos": "n", "ru": "гвоздь; металлический гвоздь (кн.)", "en": "nail; iron nail (literary)", "freq": 44},
    ("хонача", "n"): {"ru": "маленький домик; комнатка; клетка", "en": "little house; small room; cell", "freq": 56},
    ("корфармоӣ", "n"): {"ru": "поручение; приказ сделать что-л.", "en": "assignment; order; command", "freq": 56},
    ("дилбаста", "n"): {"pos": "adj", "ru": "влюблённый; привязанный; увлечённый", "en": "attached; devoted; enamored", "freq": 62},
    ("бахшидан", "v"): {"ru": "прощать; простить; дарить; подарить", "en": "to forgive; to pardon; to grant", "freq": 84},
    ("бедониш", "adj"): {"ru": "невежественный; необразованный", "en": "ignorant; uneducated", "freq": 56},
    ("наметавонад", "v"): {"ru": "не может", "en": "cannot; to be unable to", "freq": 80},
    ("рафтан", "v"): {"ru": "идти; уходить; пойти; поехать; ездить", "en": "to go; to leave; to ride; to set out", "freq": 96},
    ("иборат будан", "v"): {"ru": "состоять (из); заключаться", "en": "to consist (of); to be composed (of)", "freq": 80},
    ("маълумотнок", "adj"): {"ru": "знающий; ведающий; образованный", "en": "knowledgeable; educated", "freq": 64},
    ("гуфтугӯӣ", "adj"): {"ru": "разговорный", "en": "colloquial; conversational; spoken", "freq": 66},
    ("фасеҳӣ", "n"): {"ru": "красноречие; ясность и плавность речи", "en": "eloquence; fluency; clarity of speech", "freq": 56},
    ("дилписанд", "n"): {"pos": "adj", "ru": "приятный; милый; желанный", "en": "pleasant; lovely; attractive", "freq": 60},
    ("боадабона", "adv"): {"ru": "вежливо; учтиво; прилично", "en": "politely; courteously; decently", "freq": 64},
    ("айнан", "adj"): {"pos": "adv", "ru": "точно; точь-в-точь; буквально", "en": "literally; word for word; exactly", "freq": 70},
    ("нидоӣ", "adj"): {"ru": "междометный (грам.)", "en": "interjectional (gram.)", "freq": 50},
    ("таҳдидомез", "adv"): {"pos": "adj", "ru": "угрожающий; устрашающий; грозно", "en": "threatening; menacing; menacingly", "freq": 58},
    ("посбонӣ", "adj"): {"pos": "n", "ru": "охрана; караул; несение охраны", "en": "guarding; patrol; watch", "freq": 64},
    ("нигаҳбонӣ", "adj"): {"pos": "n", "ru": "охрана; оберегание; забота", "en": "guarding; protection; care", "freq": 66},
    ("ғайризаминӣ", "adj"): {"ru": "внеземной; неземной", "en": "extraterrestrial; unearthly", "freq": 58},
    ("ақлӣ", "adj"): {"ru": "умственный; интеллектуальный", "en": "mental; intellectual", "freq": 70},
    ("ҷонишинӣ", "adj"): {"pos": "n", "ru": "замена; заместительство; преемственность", "en": "substitution; succession", "freq": 54},
    ("аслиҳадор", "adj"): {"ru": "вооружённый; имеющий оружие", "en": "armed", "freq": 58},
    ("бемурувват", "adj"): {"ru": "жестокий; безжалостный; немилосердный", "en": "cruel; ruthless; merciless", "freq": 58},
    ("бериё", "adj"): {"ru": "искренний; непритворный; неподдельный", "en": "sincere; genuine; unfeigned", "freq": 62},
    ("пайравӣ", "n"): {"ru": "следование; приверженность; подражание", "en": "following; adherence; imitation", "freq": 64},
    ("салламно", "n"): {"pos": "intj", "ru": "браво!; молодец!; прекрасно!", "en": "bravo!; well done!; splendid!", "freq": 56},
    ("хабарнигорӣ", "n"): {"ru": "журналистика; корреспонденция; репортаж", "en": "journalism; reporting; correspondence", "freq": 60},
    ("қобилак", "n"): {"ru": "паинька; послушный (о ребёнке)", "en": "good child; obedient child", "freq": 56},
    ("қобилакак", "n"): {"ru": "паинька; послушный (о ребёнке)", "en": "good child; obedient child", "freq": 50},
}

# Global cleanups for English strings (typos & broken machine translations)
EN_REPLACEMENTS = [
    (r"\bquite\b(?=\s*;|\s*$)", "quiet"),
    (r"\bgentile\b", "gentle"),
    (r"\bnucleolus\b", "kernel"),
    (r"\bquit witted\b", "quick-witted"),
    (r"\bhearse voice\b", "hoarse voice"),
    (r"\bhaving a good;\s*retentive memory", "retentive memory"),
    (r"\bbad;\s*scruffy work", "bad work; shoddy work"),
    (r"\bbeautiful;\s*picturesque place", "picturesque place"),
    (r"\b\(about (grain|horse|horses|clothes|person|people|fruit|bread|water|dog|animals|children|a child|child)\)",
     lambda m: f"(of {m.group(1)})"),
    (r"\b\(for gate\)", "(of a gate)"),
]

def clean_en(en: str) -> str:
    s = en
    for pat, repl in EN_REPLACEMENTS:
        s = re.sub(pat, repl, s, flags=re.IGNORECASE if isinstance(repl, str) else 0)
    # Remove dangling empty items or duplicate semicolons
    parts = []
    seen = set()
    for p in s.split(";"):
        p = p.strip()
        if not p:
            continue
        # Drop truncated dangling preposition-only phrases like "having a good"
        if p.lower() in ("having a good", "new (about clothes)"):
            continue
        low = p.lower()
        if low not in seen:
            seen.add(low)
            parts.append(p)
    return "; ".join(parts)

def clean_ru(ru: str) -> str:
    parts = []
    seen = set()
    for p in ru.split(";"):
        p = p.strip()
        if not p:
            continue
        # Drop stray Tajik word 'як' leaked into Russian
        if p.lower() == "як":
            continue
        low = p.lower()
        if low not in seen:
            seen.add(low)
            parts.append(p)
    return "; ".join(parts)

def recalibrate_freq(tg: str, orig_freq: int, is_core: bool, has_override: bool) -> int:
    if has_override:
        return orig_freq
    if is_core:
        return max(orig_freq, 70)
    low = tg.lower()
    reg = book_register(low)
    rscore = ru2tj_score.get(low, 0)

    # Start from calibrated base using 1985 Russian-Tajik dictionary prominence
    if rscore >= 120:
        base = 90
    elif rscore >= 50:
        base = 82
    elif rscore >= 20:
        base = 76
    elif rscore >= 8:
        base = 70
    elif rscore >= 3:
        base = 63
    elif rscore >= 1:
        base = 56
    else:
        base = min(orig_freq, 58)

    # Apply register caps from 2006 Farhangi Tojiki-Rusi
    if reg == "literary_archaic":
        base = min(base, 46)
    elif reg == "colloquial":
        base = min(base, 58)
    elif reg == "has_figurative":
        base = min(base, 62)

    # Blend mildly with curated original freq for standard words without exceeding bounds
    if reg == "standard" and rscore == 0:
        base = min(max(44, orig_freq - 10), 64)

    return max(35, min(98, base))

with open(SRC_CSV, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

cleaned = []
removed = []
corrected_count = 0
seen_keys = set()

for idx, row in enumerate(rows):
    tg = (row["tg"] or "").strip()
    pos = (row["pos"] or "").strip()
    is_core = idx < 395  # Hand-curated core entries at top of CSV

    if (tg, pos) in REMOVE_EXACT or tg in REMOVE_PERSON_NAMES:
        removed.append((tg, pos, row["ru"]))
        continue

    ru = clean_ru(row["ru"] or "")
    en = clean_en(row["en"] or "")
    freq = int((row["frequency"] or "50").strip() or 50)
    has_override = False

    if (tg, pos) in CORRECTIONS:
        c = CORRECTIONS[(tg, pos)]
        pos = c.get("pos", pos)
        ru = c.get("ru", ru)
        en = c.get("en", en)
        freq = c.get("freq", freq)
        has_override = True
        corrected_count += 1
    else:
        freq = recalibrate_freq(tg, freq, is_core, False)

    # Deduplicate (tg.lower(), pos) after POS fixes
    dedup_key = (tg.lower(), pos)
    if dedup_key in seen_keys:
        removed.append((tg, pos, f"dup-after-fix: {ru}"))
        continue
    seen_keys.add(dedup_key)

    row["pos"] = pos
    row["ru"] = ru
    row["en"] = en
    row["frequency"] = str(freq)
    cleaned.append(row)

# Sort rows: preserve exact curated core order? Better: sort by frequency DESC, preserving original order on ties
# Wait: keeping core entries sorted by frequency DESC puts highest-frequency translations FIRST in reverse_pos!
cleaned.sort(key=lambda r: (-int(r["frequency"]), r["tg"].lower()))

for out_path in (OUT_IOS, OUT_AND):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(cleaned)

print(f"Original rows: {len(rows)}")
print(f"Cleaned rows:  {len(cleaned)}")
print(f"Removed rows:  {len(removed)}")
print(f"Manual/book overrides applied: {corrected_count}")

# Distribution report
buckets = {"90-100": 0, "80-89": 0, "70-79": 0, "50-69": 0, "<50": 0}
for r in cleaned:
    fr = int(r["frequency"])
    if fr >= 90: buckets["90-100"] += 1
    elif fr >= 80: buckets["80-89"] += 1
    elif fr >= 70: buckets["70-79"] += 1
    elif fr >= 50: buckets["50-69"] += 1
    else: buckets["<50"] += 1
print("New frequency distribution:", buckets)
