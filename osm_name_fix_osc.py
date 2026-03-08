import osmium
import logging
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

ADMIN_SUFFIX = ["村","社区","市","区","自治县","县","族镇","镇","族乡","乡","街道"]
NON_ADMIN_SUFFIX = ["新区","开发区","商贸区","度假区","核心区","商务区","管理区","经开区","起步区","保税区","合作区","中心区"]

ETHNIC_GROUPS = [
    "回族","满族","蒙古族","畲族","土家族","壮族","苗族","瑶族","侗族",
    "朝鲜族","仫佬族","毛南族","锡伯族","藏族","乌孜别克族","哈萨克族",
    "塔塔尔族","傈僳族","拉祜族","白族","布朗族","佤族","哈尼族","水族",
    "维吾尔族",
]

FOREIGN_LANG_TAGS = [
    "name:af","name:ca","name:ceb","name:da","name:de","name:es","name:et",
    "name:eu","name:fr","name:gl","name:id","name:it","name:ki","name:mg",
    "name:nl","name:nn","name:no","name:pl","name:sv","name:tl","name:tr"
]

SINITIC_LANG_TAGS = ["name:lzh","name:gan","name:yue"]


# ------------------ 工具函数 ------------------

def ends_with_admin(name):
    return any(name.endswith(s) for s in ADMIN_SUFFIX) and not any(name.endswith(s) for s in NON_ADMIN_SUFFIX)


def remove_suffix(name):
    for s in ADMIN_SUFFIX:
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
    return result


def char_pinyin(chars, style=Style.NORMAL):
    pys = pinyin(chars, style=style)
    result = [pys[0][0]]
    for p in pys[1:]:
        s = p[0]
        if s.startswith(("a","ā","á","à","o","e","é","è")):
            s = "'" + s
        result.append(s)
    return "".join(result)


def zh_to_en(name_zh):
    base, suffix = split_admin(name_zh)
    base = base.replace("都", "督")
    base = base.replace("长", "常")
    base = base.replace("戛", "嘎")
    base = base.replace("圩", "墟")
    base = base.replace("卜", "捕")
    base = base.replace("泊", "薄")
    base = base.replace("朝", "潮")
    base = base.replace("什", "十")
    base = base.replace("佛", "仏")
    base = base.replace("重", "崇")
    base = base.replace("厦", "夏")
    base_py = char_pinyin(base, style=Style.NORMAL).capitalize().replace("v", "ü")
    suffix_py = ""
    if len(base) == 1:
        if suffix in ("村", "镇", "乡", "县", "市"):
            suffix_py = " " + char_pinyin(suffix, style=Style.NORMAL).capitalize()

    return base_py + suffix_py

def zh_to_pinyin(name_zh):
    base, suffix = split_admin(name_zh)
    base = base.replace("都", "督")
    base = base.replace("长", "常")
    base = base.replace("干", "甘")
    base = base.replace("处", "楚")
    base = base.replace("戛", "嘎")
    base = base.replace("圩", "墟")
    base = base.replace("泊", "薄")
    base = base.replace("朝", "潮")
    base = base.replace("什", "十")
    base = base.replace("佛", "仏")
    base = base.replace("重", "崇")
    base = base.replace("曲", "屈")
    base = base.replace("更", "庚")
    base = base.replace("厦", "夏")
    base_py = char_pinyin(base, style=Style.TONE).capitalize()
    suffix_py = char_pinyin(suffix, style=Style.TONE).capitalize()
    if suffix_py:
        return base_py + " " + suffix_py
    return base_py

def process_ethnic(name, tags):
    for e in ETHNIC_GROUPS:
        if e in name:
            tags["official_name"] = name
            tags["official_name:zh"] = name
            name = name.replace(e,"")
    return name


def process_alt_name(tags, name_zh, name_en):

    alt = tags.get("alt_name")
    if not alt:
        return None

    parts = [p.strip() for p in alt.split(";")]
    zh = []
    en = []
    for p in parts:
        if re.search("[\u4e00-\u9fff]", p):
            zh.append(p)
        else:
            en.append(p)

    # ---------- 中文处理 ----------

    base_zh, _ = remove_suffix(name_zh)

    alt_zh = []
    short_zh = None
    for z in zh:
        if z == name_zh:
            continue
        if z == base_zh:
            short_zh = z
            continue
        alt_zh.append(z)

    # ---------- 英文处理 ----------

    alt_en = []
    official_en = None

    suffix_list = ["Town", "Township", "Subdistrict", "City", "County", "District"]

    if not en and "alt_name:en" in tags:
        alt = tags.get("alt_name:en")
        en = [p.strip() for p in alt.split(";")]

    for e in en:
        if e == name_en:
            continue
        matched = False
        for suf in suffix_list:
            if e == name_en + " " + suf:
                official_en = e
                matched = True
                break
        if not matched:
            alt_en.append(e)

    # ---------- 写回 tags ----------

    if short_zh:
        tags["short_name"] = short_zh

    if official_en:
        tags["official_name:en"] = official_en

    new_alt_zh = ";".join(alt_zh) if alt_zh else None
    new_alt_en = ";".join(alt_en) if alt_en else None

    return new_alt_zh, new_alt_en


def ensure_place_cn(tags, name):
    if name.endswith("族镇"):
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
    if place in ("ethnic_town", "town", "ethnic_township", "township", "subdistrict"):
        tags["capital"] = "8"


def remove_building_office_tags(tags,obj_id):
    for k in ["building","office"]:
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
        for k,v in tags.items():
            ET.SubElement(node_elem,"tag",k=k,v=v)

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

        remove_building_office_tags(tags,n. id)

        name = process_ethnic(tags["name"], tags)

        for tag in ("name", "name:zh", "name:zh-Hans"):
            if tag in tags and tags[tag] != name:
                logging.info(f"{tag} override {name} {tags[tag]} -> {name}")
            tags[tag] = name

        official_name = tags.get("official_name", tags["name:zh"])
        name_1 = remove_suffix(official_name)[0]
        name_2 = remove_suffix(name)[0]
        if official_name != name and name_1 == name_2:
            logging.info(f"official_name override {name} {official_name} -> {name}")
            official_name = name
            tags["official_name"] = name

        ensure_place_cn(tags, official_name)

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

        alt = process_alt_name(tags, tags["name:zh"], tags["name:en"])
        
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
        
        if "official_name:en" in tags:
            candidate = tags.get("official_name") or tags.get("name")
            if candidate:
                tags["official_name"] = candidate
                tags["official_name:zh"] = candidate

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

        if "capital" in tags and not name.endswith("村") and not name.endswith("社区"):
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
