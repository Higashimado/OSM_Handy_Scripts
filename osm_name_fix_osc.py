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
    "新区","开发区","商贸区","度假区","核心区","商务区","管理区","经开区","起步区",
    "保税区","合作区","中心区","经济区","集中区","产业园区","工业园区","旅游区","试验区",
    "实验区","投资区","工业园小区","名胜区","风景区","示范区","直管区","产业小镇","科教园区"
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

FOREIGN_LANG_TAGS = [
    "name:af","name:ca","name:ceb","name:da","name:de","name:es","name:et",
    "name:eu","name:fr","name:gl","name:id","name:it","name:ki","name:mg",
    "name:nl","name:nn","name:no","name:pl","name:sv","name:tl","name:tr"
    ]

SINITIC_LANG_TAGS = ["name:lzh","name:gan","name:yue"]

# ------------------ 工具函数 ------------------

def ends_with_admin(name):
    return any(name.endswith(s) for s in ADMIN_SUFFIXES.keys()) and not any(name.endswith(s) for s in NON_ADMIN_SUFFIXES)


def remove_suffix(name):
    for s in ADMIN_SUFFIXES.keys():
        if name.endswith(s):
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
    return "".join(result)


def zh_to_en(name_zh):
    base, suffix = split_admin(name_zh)
    base = base.replace("陂面", "坡面")
    base = base.replace("通什", "通杂")
    base = base.replace("乐成", "月成")
    base = base.replace("天台", "天胎")
    base = base.replace("朝晖", "召晖")
    base = base.replace("都", "督")
    base = base.replace("长", "常")
    base = base.replace("戛", "嘎")
    base = base.replace("圩", "墟")
    base = base.replace("卜", "捕")
    base = base.replace("泊", "伯")
    base = base.replace("朝", "潮")
    base = base.replace("什", "十")
    base = base.replace("佛", "仏")
    base = base.replace("重", "崇")
    base = base.replace("厦", "夏")
    base = base.replace("咀", "嘴")
    base = base.replace("尾", "苇")
#   base = base.replace("涌", "冲")
    base_py = char_pinyin(base, style=Style.NORMAL).capitalize().replace("v", "ü")
    suffix_py = ""
    if len(base) == 1:
        if suffix in ("村", "镇", "乡", "县", "市"):
            suffix_py = " " + char_pinyin(suffix, style=Style.NORMAL).capitalize()

    return base_py + suffix_py


def zh_to_pinyin(name_zh):
    base, suffix = split_admin(name_zh)
    base = base.replace("羊场", "羊肠")
    base = base.replace("马号", "马嚎")
    base = base.replace("陂面", "坡面")
    base = base.replace("通什", "通杂")
    base = base.replace("乐成", "月成")
    base = base.replace("天台", "天胎")
    base = base.replace("朝晖", "召晖")
    base = base.replace("都", "督")
    base = base.replace("长", "常")
    base = base.replace("干", "甘")
    base = base.replace("处", "楚")
    base = base.replace("戛", "嘎")
    base = base.replace("圩", "墟")
    base = base.replace("泊", "伯")
    base = base.replace("朝", "潮")
    base = base.replace("什", "十")
    base = base.replace("佛", "仏")
    base = base.replace("重", "崇")
    base = base.replace("曲", "屈")
    base = base.replace("更", "庚")
    base = base.replace("厦", "夏")
    base = base.replace("咀", "嘴")
    base = base.replace("尾", "苇")
#   base = base.replace("涌", "冲")
    base_py = char_pinyin(base, style=Style.TONE).capitalize()
    suffix_py = char_pinyin(suffix, style=Style.TONE).capitalize()
    if suffix_py:
        return base_py + " " + suffix_py
    return base_py


def process_ethnic(name, tags):
    for e in ETHNIC_NAMES.keys():
        if e in name:
            tags["official_name"] = name
            tags["official_name:zh"] = name
            name = name.replace(e,"")
    return name


def process_alt_name(tags):

    alt = tags.get("alt_name") or ""
    alt_zh = tags.get("alt_name:zh") or ""
    alt_en = tags.get("alt_name:en") or ""
    if not alt and not alt_zh and not alt_en:
        return None

    combined = ";".join((alt, alt_zh, alt_en))
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

    alt_zh = []
    short_zh = None

    for z in zh:
        if z == name_zh:
            continue
        if z == tags.get("name:zh-Hant"):
            continue
        if z == tags.get("official_name"):
            continue
        if z == base_zh:
            if len(z) > 1:
                 short_zh = z
            continue
        alt_zh.append(z)

    # ---------- 英文处理 ----------

    name_en = tags["name:en"]
    alt_en = []
    official_en = None

    for e in en:
        if e == name_en:
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

    if short_zh and not "short_name" in tags:
        tags["short_name"] = short_zh

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

    combined = ";".join((old, old_zh, old_en))
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
        if z == base_zh:
            if len(z) > 1:
                 short_zh = z
            if not (z.endswith("县") and name_zh.endswith("县区")):
                continue
        old_zh.append(z)

    old_en = en

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

    suffix_en = ADMIN_SUFFIXES[suffix]
    if suffix not in ["自治县","族镇","族乡"]:
        return f"{name_en} {suffix_en}"


#    ethnic_names = []
#    for zh, en in ETHNIC_NAMES.items():
#        if zh in name_zh:
#            if en:
#                ethnic_names.append(en)
#    ethnic_names = list(dict.fromkeys(ethnic_names))
#    ethnic_text = join_ethnic_names(ethnic_names)
#    if ethnic_text:
#        return f"{name_en} {ethnic_text} {suffix_en}"

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
        return f"{name_en} {ethnic_text} {suffix_en}"


    return f"{name_en} {suffix_en}"


def remove_non_place_tags(tags,obj_id):
    for k in ["building","office","amenity","shop","ele","natural"]:
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
            else:
                logging.warning(f"Tag '{k}' is None for node {node.id}, skipped")

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
        if "name:zh-Hant" in tags and tags["name:zh-Hant"] != new_ht:
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

        
        official_en = build_official_name_en(official_zh, new_en)
        if "official_name:en" in tags or tags.get("place:CN") in ("autonomous_county", "ethnic_town", "ethnic_township"):
            tags["official_name"] = official_zh 
            tags["official_name:zh"] = official_zh
            old_official_en = tags.get("official_name:en") or ""
            if official_en != old_official_en:
                if old_official_en:
                    logging.info(f"official_name:en override {name} {old_official_en} -> {official_en}")
                tags["official_name:en"] = official_en
                

        for lang in FOREIGN_LANG_TAGS:
            if lang in tags and tags[lang]!=new_en:
                logging.info(f"{lang} override {n.id}: {tags[lang]} -> {new_en}")
                tags[lang] = new_en

        for lang in SINITIC_LANG_TAGS:
            if lang in tags:
                new_val = tags["name:zh-Hant"]
                if tags[lang] != new_val:
                    logging.info(f"{lang} override {n.id}: {tags[lang]} -> {new_val}")
                tags[lang] = new_val


        if "capital" in tags and not tags.get("place:CN") in ("village", "neighbourhood"):
            wiki_name = tags.get("official_name", tags["name:zh"])
            if "wikipedia" not in tags or not tags["wikipedia"].startswith("zh:"):
                tags["wikipedia"] = "zh:" + wiki_name

        # 写入修改过的节点
        if tags != dict(n.tags):
            self.writer.add_modified_node(n,tags)


# ------------------ 主程序 ------------------

writer = OSCWriter(OUTPUT_FILE)
handler = NameFixer(writer)
handler.apply_file(INPUT_FILE)
writer.close()

print(f"OSC file generated: {OUTPUT_FILE}")
