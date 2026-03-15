import logging
import os
import osmium
import re
import sys
import xml.etree.ElementTree as ET

from opencc import OpenCC
from pypinyin import pinyin, Style


if len(sys.argv) != 2:
    print("Usage: %s [.osm]" % (os.path.basename(__file__)))
    exit(0)

INPUT_FILE = sys.argv[1]
OUTPUT_FILE = "changes.osc"
LOG_FILE = "process.log"


cc = OpenCC('s2t')

logging.basicConfig(
    filename=LOG_FILE,
    filemode='w',
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)


ADMIN_SUFFIXES = {
    "村":"Village",
    "社区":"Community",
    "市":"City",
    "林区":"Forestry District",
    "区":"District",
    "自治县":"Autonomous County",
    "县":"County",
    "族镇":"Ethnic Town",
    "镇":"Town",
    "族乡":"Ethnic Township",
    "乡":"Township",
    "街道":"Subdistrict"
}


NON_ADMIN_SUFFIXES = [
    "新区","开发区","商贸区","度假区","核心区","商务区","工业区","管理区","经开区","起步区",
    "保税区","合作区","中心区","经济区","旅游区","试验区","实验区","投资区","集中区",
    "产业园区","工业园区","科学园区","科教园区","盐化园区","教育园区","农业园区","示范园区"
    "工业园小区","名胜区","风景区","示范区","直管区","产业小镇","生态区","资源区", "聚集区", "加工区",
    "保护特区"
]


ETHNIC_NAMES = {
    "白族":"Bai",
    "布朗族":"Bulang",
    "布依族":"Buyei",
    "侗族":"Dong",
    "仡佬族":"Gelao",
    "哈尼族":"Hani",
    "回族":"Hui",
    "哈萨克族":"Kazakh",
    "朝鲜族":"Korean",
    "拉祜族":"Lahu",
    "傈僳族":"Lisu",
    "黎族":"Li",
    "满族":"Manchu",
    "毛南族":"Maonan",
    "苗族":"Miao",
    "蒙古族":"Mongol",
    "仫佬族":"Mulao",
    "畲族":"She",
    "水族":"Sui",
    "塔塔尔族":"Tatar",
    "藏族":"Tibetan",
    "土家族":"Tujia",
    "维吾尔族":"Uyghur",
    "乌孜别克族":"Uzbek",
    "佤族":"Wa",
    "锡伯族":"Xibe",
    "瑶族":"Yao",
    "彝族":"Yi",
    "壮族":"Zhuang",
    "各族":"Various Nationalities",
    "民族":""
}

SPECIAL_PRONUNCIATION = {
    "羊场":"羊肠",  # 黔
    "马号":"马嚎",  # 黔
    "陂面":"坡面",
    "通什":"通杂",  # 琼
    "乐成":"悦成",
#   "天台":"天胎",  # 浙
    "朝晖":"召晖",
    "单集":"善集",
    "行香":"形香",
    "石湫":"石秋",
    "乐桥":"悦桥",
    "焦陂":"焦坡",
    "六郎":"遛郎",
    "单桥":"丹桥",  # 皖
    "洩湖":"野湖",  # 陕
    "拓石":"踏石",  # 陕
    "解家":"谢家",  # 陕
    "长官":"掌官",
    "华阴":"化阴",  # 陕
    "召公":"绍公",  # 陕
    "都":"督",
    "长":"常",
    "干":"甘",
    "处":"楚",
    "戛":"嘎",
#   "圩":"墟",      # 粤/湘
    "圩":"围",      # 苏/皖
    "泊":"伯",
    "朝":"潮",
    "什":"十",
    "佛":"仏",
    "重":"崇",
    "曲":"屈",
    "更":"庚",
    "厦":"夏",
    "咀":"嘴",
    "尾":"苇",
#   "涌":"冲",      # 粤
    "曾":"增",
    "柏":"百",
    "行":"杭",      # 粤
#   "六":"陆",      # 苏/皖
    "任":"仁",
    "堨":"鄂",      # 皖
    "单":"善",
#   "涡":"郭",      # 皖
    "姥":"母",      # 皖
    "阚":"看",      # 皖
    "蚌":"迸",      # 皖
    "堡":"补",      # 晋/陕/冀/蒙
}

SPECIAL_PUNCTUATION = [
    "新村", "一路", "二路", "一桥", "二桥", "花园", 
    "东路", "西路", "北路", "南路", "中路", "新路", 
]

FOREIGN_LANG_TAGS = [
    "name:af","name:ca","name:ceb","name:da","name:de","name:es","name:et",
    "name:eu","name:fr","name:gl","name:id","name:it","name:ki","name:mg",
    "name:nl","name:nn","name:no","name:pl","name:sv","name:tl","name:tr"
    ]

SINITIC_LANG_TAGS = ["name:lzh","name:gan","name:yue","name:wuu"]

CITIES_WITH_HISTORICAL_NAME = ["北京市", "上海市", "广州市", "南京市", "青岛市"]

# ------------------ 工具函数 ------------------

def ends_with_admin(name):
    return any(name.endswith(s) for s in ADMIN_SUFFIXES.keys()) and not any(name.endswith(s) for s in NON_ADMIN_SUFFIXES)


def remove_suffix(name):
    for s in ADMIN_SUFFIXES.keys():
        if name.endswith(s):
            # 按照汉语的发音习惯，通名的字数一般不会少于专名
            if len(s) >= 2 and len(name[:-len(s)]) < 2 and s != "街道":
                    continue
            return name[:-len(s)], s
    return name, ""


def split_admin(name):
    base, suffix = remove_suffix(name)
    return base, suffix


def zh_to_hant(text):
    result = cc.convert(text)
    result = result.replace("遊", "游")
    result = result.replace("峯", "峰")
    result = result.replace("幹", "干")
    result = result.replace("裏", "里")
    return result


def char_pinyin(chars, style=Style.NORMAL):
    pys = pinyin(chars, style=style)
    result = [pys[0][0]]
    for p in pys[1:]:
        s = p[0]
        if s.startswith(("a","ā","á","à","o","ō","e","é","è")):
            s = "'" + s
        result.append(s)
    return "".join(result).replace(" '", " ")


def zh_to_en(name_zh):
    base, suffix = split_admin(name_zh)
    if not base:
        print("***ERROR: Invalid name_zh: " + name_zh)
        exit(0)
    for k, v in SPECIAL_PRONUNCIATION.items():
        base = base.replace(k, v)
    for k in SPECIAL_PUNCTUATION:
        if len(base) >= 4 and k in base[2:]:
            base = base.replace(k, " " + k)
    base_py = char_pinyin(base, style=Style.NORMAL).replace("v", "ü")
    suffix_py = ""
    if len(base) == 1:
        if suffix in ("村", "镇", "乡", "县", "市"):
            suffix_py = " " + char_pinyin(suffix, style=Style.NORMAL)
    strs = (base_py + " " + suffix_py).split()
    strs = [s.capitalize() for s in strs]
    return " ".join(strs)


def zh_to_pinyin(name_zh):
    base, suffix = split_admin(name_zh)
    if not base:
        print("***ERROR: Invalid name_zh: " + name_zh)
        exit(0)
    for k, v in SPECIAL_PRONUNCIATION.items():
        base = base.replace(k, v)
    for k in SPECIAL_PUNCTUATION:
        if len(base) >= 4 and k in base[2:]:
            base = base.replace(k, " " + k)
    base_py = char_pinyin(base, style=Style.TONE)
    suffix_py = char_pinyin(suffix, style=Style.TONE)
    strs = (base_py + " " + suffix_py).split()
    strs = [s.capitalize() for s in strs]
    return " ".join(strs)


def process_ethnic(name, tags):
    for e in ETHNIC_NAMES.keys():
        if e in name and name != "民族街道":
            tags["official_name"] = name
            tags["official_name:zh"] = name
            name = name.replace(e,"")
    return name


def check_admin_level(name_1, name_2):

    admin_level_1 = 0
    admin_level_2 = 0

    # No check for admin_level = 10
    for s in ("村", "社区"):
        if name_1.endswith(s) or name_2.endswith(s):
            return True

    norm_1 = re.sub(r'[（\(].*?[\)）]', '', name_1)
    norm_2 = re.sub(r'[（\(].*?[\)）]', '', name_2)

    norm_1 = norm_1.replace("-", "").replace(" ", "").lower()
    norm_2 = norm_2.replace("-", "").replace(" ", "").lower()

    for s in ("镇", "乡", "街道", "zhen", "xiang", "jiedao", "town", "township", "subdistrict"):
        if norm_1.endswith(s) and admin_level_1 == 0:
            admin_level_1 = 8
        if norm_2.endswith(s) and admin_level_2 == 0:
            admin_level_2 = 8

    for s in ("市", "县", "区", "shi", "xian", "qu", "city", "county", "district"):
        if norm_1.endswith(s) and admin_level_1 == 0:
            admin_level_1 = 6
        if norm_2.endswith(s) and admin_level_2 == 0:
            admin_level_2 = 6

    return admin_level_1 == admin_level_2 or admin_level_1 * admin_level_2 == 0


def process_alt_name(tags):

    # ---------- 分割 alt_name ----------

    alt = tags.get("alt_name") or ""
    alt_zh = tags.get("alt_name:zh") or ""
    alt_en = tags.get("alt_name:en") or ""
    if not alt and not alt_zh and not alt_en:
        return None

    combined = ";".join((alt, alt_zh, alt_en)).replace(":", ";")
    parts = [p.strip() for p in combined.split(";") if p.strip()]

    seen = set()
    unique_parts = []
    for p in parts:
        if p not in seen:
            unique_parts.append(p)
            seen.add(p)
    parts = unique_parts

    zh = []
    en = []
    for p in parts:
        if re.search("[\u4e00-\u9fff]", p):
            zh.append(p)
        else:
            en.append(p)

    # ---------- 分割 short_name ----------

    short_name = tags.get("short_name") or ""
    short_name_zh = tags.get("short_name:zh") or ""
    combined = ";".join((short_name, short_name_zh)).replace(":", ";")
    parts = [p.strip() for p in combined.split(";") if p.strip()]
    seen = set()
    unique_parts = []
    for p in parts:
        if p not in seen:
            unique_parts.append(p)
            seen.add(p)
    parts = unique_parts
    short_zh = parts

    # ---------- 中文处理 ----------

    name_zh = tags["name"]
    name_zht = tags["name:zh-Hant"]

    base_zh, _ = remove_suffix(name_zh)
    base_zht, _ = remove_suffix(name_zht)

    alt_zh = []
    for z in zh:
        if z == name_zh:
            continue
        if z == name_zht:
            continue
        if z == tags.get("official_name"):
            continue
        if z == base_zh:
            if not z in short_zh:
                short_zh.append(z)
            continue
        if "办事处" in z:
            continue
        if not check_admin_level(name_zh, z):
            continue
        skip = False
        for v_zh in ADMIN_SUFFIXES.keys():
            if z == base_zh + v_zh:
                skip = True
                break
        if skip:
            continue
        alt_zh.append(z)

    # ---------- 英文处理 ----------

    name_en = tags["name:en"]
    official_en = None

    alt_en = []
    for e in en:
        if e == name_en:
            continue
        if e == tags.get("official_name:en"):
            continue
        if not check_admin_level(name_en, e):
            continue
        skip = False
        for v_zh in ADMIN_SUFFIXES.keys():
            v_en = char_pinyin(v_zh)
            e_norm = e.replace("-", "").replace(" ", "").lower()
            n_norm = name_en.replace("-", "").replace(" ", "").lower()
            if e_norm == n_norm + v_en:
                skip = True
                break
        if skip:
            continue
        matched = False
        for suf in ADMIN_SUFFIXES.values():
            if e == name_en + " " + suf:
                official_en = e
                matched = True
                break
        if not matched:
            alt_en.append(e)

    # ---------- 写回 tags ----------

    if short_zh:
        tags["short_name"] = ";".join(short_zh)
        if "short_name:zh" in tags:
            tags["short_name:zh"] = tags.get("short_name")

    if official_en:
        if not "official_name:en" in tags:
            tags["official_name:en"] = official_en
        else:
            if official_en != tags["official_name:en"]:
                alt_en.append(official_en)

    new_alt_zh = ";".join(alt_zh) if alt_zh else None
    new_alt_en = ";".join(alt_en) if alt_en else None

    return new_alt_zh, new_alt_en


def process_old_name(tags):

    old = tags.get("old_name") or ""
    old_zh = tags.get("old_name:zh") or ""
    old_en = tags.get("old_name:en") or ""
    if not old and not old_zh and not old_en:
        return None

    combined = ";".join((old, old_zh, old_en)).replace(":", ";")
    parts = [p.strip() for p in combined.split(";") if p.strip()]

    seen = set()
    unique_parts = []
    for p in parts:
        if p not in seen:
            unique_parts.append(p)
            seen.add(p)
    parts = unique_parts

    zh = []
    en = []
    for p in parts:
        if re.search("[\u4e00-\u9fff]", p):
            zh.append(p)
        else:
            en.append(p)

    # ---------- 中文处理 ----------

    name_zh = tags["name"]
    base_zh, _ = remove_suffix(name_zh)

    old_zh = []
    short_zh = None

    for z in zh:
        if z == name_zh:
            continue
        if not check_admin_level(name_zh, z):
            continue
        if z == base_zh:
            if len(z) > 1:
                 short_zh = z
            if not (z.endswith("县") and name_zh.endswith("县区")):
                continue
        old_zh.append(z)

    # ---------- 英文处理 ----------

    name_en = tags.get("name:en")
    old_en = []

    for e in en:
        if e == name_en:
            continue
        if e == tags.get("official_name:en"):
            continue
        if not check_admin_level(name_en, e):
            continue
        old_en.append(e)

    # ---------- 写回 tags ----------

    if short_zh and not "short_name" in tags:
        tags["short_name"] = short_zh

    new_old_zh = ";".join(old_zh) if old_zh else None
    new_old_en = ";".join(old_en) if old_en else None

    return new_old_zh, new_old_en


def ensure_place_cn(tags, name):
    if name.endswith("自治县"):
        place = "autonomous_county"
    elif name.endswith("县"):
        place = "county"
    elif name.endswith("族镇"):
        place = "ethnic_town"
    elif name.endswith("镇"):
        place = "town"
    elif name.endswith("族乡"):
        place = "ethnic_township"
    elif name.endswith("乡"):
        place = "township"
    elif name.endswith("街道"):
        place = "subdistrict"
    elif name.endswith("村"):
        place = "village"
    elif name.endswith("社区"):
        place = "neighbourhood"
    else:
        return
    tags["place:CN"] = place
    if place in ("autonomous_county", "county"):
        tags["capital"] = "6"
    if place in ("ethnic_town", "town", "ethnic_township", "township", "subdistrict"):
        tags["capital"] = "8"


def join_ethnic_names(names):
    if len(names) == 0:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return names[0] + " and " + names[1]
    return ", ".join(names[:-1]) + " and " + names[-1]


def build_official_name_en(name_zh, name_en):

    suffix = None
    for s in ADMIN_SUFFIXES.keys():
        if name_zh.endswith(s):
            suffix = s
            break
    if not suffix:
        return None

    norm_en = name_en
    for en in ("Cun", "Shi", "Xian", "Xiang", "Zhen"):
        norm_en = norm_en.replace(" " + en, "")

    suffix_en = ADMIN_SUFFIXES[suffix]
    if suffix not in ["自治县","族镇","族乡"]:
        return f"{norm_en} {suffix_en}"

    ethnic_names = []
    
    base = name_zh
    for s in reversed(ADMIN_SUFFIXES):
        if base.endswith(s):
            base = base[:-len(s)]
            break
    
    first_pos = None
    for k in ETHNIC_NAMES.keys():
        pos = base.find(k)
        if pos != -1:
            if first_pos is None or pos < first_pos:
                first_pos = pos
    
    if first_pos is not None:
        ethnic_part = base[first_pos:]
        parts = ethnic_part.split("族")
        for p in parts:
            if not p:
                continue
            zh = p + "族"
            en = ETHNIC_NAMES.get(zh)
            if en:
                ethnic_names.append(en)
    
    ethnic_text = join_ethnic_names(ethnic_names)
    if ethnic_text:
        return f"{norm_en} {ethnic_text} {suffix_en}"

    return f"{norm_en} {suffix_en}"


def remove_non_place_tags(tags,obj_id):
    for k in ["amenity","building","ele","fee","natural","office","shop"]:
        if k in tags:
            logging.info(f"remove {k} tag {obj_id}")
            tags.pop(k)


# ------------------ OSC Writer ------------------

class OSCWriter:

    def __init__(self, filename):
        self.root = ET.Element("osmChange", version="0.6", generator="osm-name-script")
        self.modify = ET.SubElement(self.root,"modify")
        self.filename = filename

    def add_modified_node(self,node,tags):
        node_elem = ET.SubElement(
            self.modify,
            "node",
            id=str(node.id),
            version=str(node.version),
            lat=str(node.location.lat),
            lon=str(node.location.lon)
        )
        for k, v in tags.items():
            if v is not None:
                ET.SubElement(node_elem, "tag", k=k, v=v)
#           else:
#               logging.warning(f"Tag '{k}' is None for node {node.id}, skipped")

    def close(self):
        tree = ET.ElementTree(self.root)
        tree.write(self.filename,encoding="utf-8",xml_declaration=True)


# ------------------ Handler ------------------

class NameFixer(osmium.SimpleHandler):

    def __init__(self, writer):
        super().__init__()
        self.writer = writer

    def node(self,n):

        tags = dict(n.tags)
        if "name" not in tags or "place" not in tags:
            return
        name = tags["name"]
        if not ends_with_admin(name):
            logging.info(f"skip {n.id}: {name}")
            return

        remove_non_place_tags(tags,n. id)

        name = process_ethnic(tags["name"], tags)

        for tag in ("name", "name:zh", "name:zh-Hans"):
            if tag in tags and tags[tag] != name:
                logging.info(f"{tag} override {name} {tags[tag]} -> {name}")
            tags[tag] = name

        official_zh = tags.get("official_name", tags["name:zh"])
        name_1 = remove_suffix(official_zh)[0]
        name_2 = remove_suffix(name)[0]
        if official_zh != name and name_1 == name_2:
            logging.info(f"official_name override {name} {official_zh} -> {name}")
            official_zh = name
            tags["official_name"] = name

        ensure_place_cn(tags, official_zh)

        new_ht = zh_to_hant(tags["name:zh-Hans"])
        old_ht = tags.get("name:zh-Hant") or ""
        if old_ht != new_ht and len(old_ht) == len(new_ht):
            logging.info(f"name:zh-Hant mismatch {name} {tags['name:zh-Hant']} <> {new_ht}, skip")
        else:
            tags["name:zh-Hant"] = new_ht

        new_en = zh_to_en(name)
        if "name:en" in tags and tags["name:en"] != new_en:
            logging.info(f"name:en oveeride {name} {tags['name:en']} -> {new_en}")
        tags["name:en"] = new_en

        new_py = zh_to_pinyin(tags["name:zh"])
        if "name:zh-Latn-pinyin" in tags and tags["name:zh-Latn-pinyin"] != new_py:
            logging.info(f"name:zh-Latn-pinyin override {name} {tags['name:zh-Latn-pinyin']} -> {new_py}")
        tags["name:zh-Latn-pinyin"] = new_py

 
        official_en = build_official_name_en(official_zh, new_en)
        if (tags.get("place:CN") in ("autonomous_county", "ethnic_town", "ethnic_township")
            or (len(name) == 2 and tags.get("place:CN") in ("county", "town", "township"))):
            tags["official_name"] = official_zh 
            tags["official_name:zh"] = official_zh
            old_official_en = tags.get("official_name:en") or ""
            if official_en != old_official_en:
                if old_official_en:
                    logging.info(f"official_name:en override {name} {old_official_en} -> {official_en}")
                tags["official_name:en"] = official_en


        alt = process_alt_name(tags)
        if alt:
            alt_zh, alt_en = alt
            if alt_zh:
                tags["alt_name"] = alt_zh
                tags["alt_name:zh"] = alt_zh
            else:
                tags.pop("alt_name", None)
                tags.pop("alt_name:zh", None)
            if alt_en:
                tags["alt_name:en"] = alt_en
            else:
                tags.pop("alt_name:en", None)

        old = process_old_name(tags)
        if old:
            old_zh, old_en = old
            if old_en:
                tags["old_name:en"] = old_en
            else:
                tags.pop("old_name:en", None)
            if old_zh:
                tags["old_name"] = old_zh
                if "old_name:zh" in tags or "old_name:en" in tags:
                    tags["old_name:zh"] = old_zh
            else:
                tags.pop("old_name", None)
                tags.pop("old_name:zh", None)


        if "official_name:en" in tags:
            tags["official_name"] = official_zh 
            tags["official_name:zh"] = official_zh

                
        if not name in CITIES_WITH_HISTORICAL_NAME:
            for lang in FOREIGN_LANG_TAGS:
                if lang in tags and tags[lang]!=new_en:
                    logging.info(f"{lang} override {name}: {tags[lang]} -> {new_en}")
                    tags[lang] = new_en

        for lang in SINITIC_LANG_TAGS:
            if lang in tags:
                new_val = tags["name:zh-Hant"]
                if tags[lang] != new_val:
                    logging.info(f"{lang} override {name}: {tags[lang]} -> {new_val}")
                tags[lang] = new_val


        if "capital" in tags and not tags.get("place:CN") in ("village", "neighbourhood"):
            old_wiki = tags.get("wikipedia") or ""
            new_wiki = "zh:" + (tags.get("official_name") or tags.get("name:zh"))
            if not old_wiki.startswith("zh:") or not check_admin_level(new_wiki, old_wiki):
                if old_wiki:
                    logging.info(f"wikipedia override {name}: {old_wiki} -> {new_wiki}")
                tags["wikipedia"] = new_wiki


        # 写入修改过的节点
        if tags != dict(n.tags):
            self.writer.add_modified_node(n,tags)


# ------------------ 主程序 ------------------

writer = OSCWriter(OUTPUT_FILE)
handler = NameFixer(writer)
handler.apply_file(INPUT_FILE)
writer.close()

print(f"OSC file generated: {OUTPUT_FILE}")
