# OSM Handy Scripts

本项目旨在提供用于帮助在 OSM 中进行数据检查、补充和修正的简易半自动脚本。由于 OSM 中的数据类型复杂，编者标注风格各异，用简单的编码规则应对复杂的现实情况是很难做到的。所以，**半自动**的含义即，请使用者在执行这些脚本后仔细进行人工核查，检查输出日志，并手动修复因各种特殊情况导致的疏漏等。

## osm_name_fix_osc.py

该脚本用于对中国大陆境内省、市、县、乡四级法定行政区驻地的 `place` 节点的标签进行检查、补充和修正，主要涉及 `name:*` `alt_name:*` `short_name` `official_name:*` 和 `wikipedia` 标签。具体规则如下：

### 主名类

1. 对于名称类标签 `<tag>`，强制 `<tag>:zh` 和 `<tag>:zh-Hans` 与 `<tag>` 的值相同（暂未考虑双语地区的情况），并在 `<tag>:en` 存在的情况下强制补充 `<tag>:zh` 标签
2. 使用 pypinyin 生成 `name:zh-Latn-pinyin` 标签，覆盖原有标签的值
3. 使用 opencc 生成 `name:zh-Hant` 标签，但不覆盖原有标签的值
4. 使用不含通名、无声调的的汉语拼音拉丁化方案生成 `name:en` 标签，覆盖原有标签的值

### 别名类

1. 对于 `alt_name` 中的非中文部分，将其转移至 `alt_name:en` 中，并强制生成和剩余中文部分相同的 `alt_name:zh` 标签
2. 对于 `alt_name` 中不含通名的中文变体（如“杭州”之于“杭州市”），将其转移至 `short_name`
3. 对于 `alt_name` 中含通名，且遵循 [OSM 中国社区的通名翻译规范](https://wiki.openstreetmap.org/wiki/Multilingual_names#China)的英文变体（如 *Hangzhou City* 之于 *Hangzhou*），将其转移至 `official_name:en`，并强制生成相应的中文 `official_name` 和 `official_name:zh` 标签
4. 对于 `alt_name` 中含通名，且对应汉语拼音拉丁化的英文变体（如 *Hangzhou Shi* 之于 *Hangzhou*），删除之，理由是 Nominatim 可正确将 `name:zh-Latn-pinyin` 中的带声调字符正规化为无声调字符，该英文变体并不提供额外信息
4. 对于自治县、民族乡、民族镇等，强制将带民族名称（包括“XX 民族乡”“XX 各族乡”等）的长名称转移至 `official_name` 和 `official_name:zh` 中，主名称 `name` 按照 OSM 中国社区的约定规范化为“XX 县”“XX 乡”等，同时强制补充带民族名称翻译的 `official_name:en`

### 其他规则

1. 跳过所有不含通名的地点，以及所有以非法定行政区类型作为通名的地点（如“XX 新区”“XX 示范区”等，参见 `NON_ADMIN_SUFFIXES`）
2. **县镇分离：** 检查 `alt_name:*` `old_name:*` `wikipedia` 中的值和 `name:*` 中的值是否在行政等级上一致，若不一致，则删除之
2. 使用 `official_name` 或 `name` 标签生成相应的 `wikipedia` 标签，但不覆盖原有标签的值
3. 强制使用不含通名、无声调的的汉语拼音拉丁化方案（即 `name:en`）作为各使用拉丁字母的欧洲语言对应标签（参见 `FOREIGN_LANG_TAGS`）的值，但拥有已被广泛使用的历史名称的城市除外（参见 `CITIES_WITH_HISTORICAL_NAME`）
4. 强制使用繁体中文（即 `name:zh-Hant`）作为国内各方言对应标签（参见 `SINITIC_LANG_TAGS`）的值
5. 单字地名处理规则按照 OSM 中国社区的约定，不使用单字名作为 `alt_name` 或 `short_name`，了，拉丁化时通名大写（如“杨镇”拉丁化成 *Yang Zhen*）
6. **分词翻译：** 多字地名在拉丁化时按汉语拼音习惯进行分词（如“长江二桥街道”拉丁化成 *Changjiang Erqiao*，参见 `SPECIAL_PUNCTUATION`）
7. 删除不适合在 `place` 节点上使用的标签（如 `building` 等，参见 `remove_non_place_tags(tags,obj_id)`

### 使用方式

在 JOSM 中使用 overpass 下载 *place* 节点，将图层保存为 .osm 文件，并将该文件作为参数，在命令行中输入 `python3 ./osm_name_fix_osc.py [.osm]` 。正常运行结束后会生成 `process.log` 文件和 `changes.osc` 文件。使用 JOSM 打开 `changes.osc`，在 `process.log` 的辅助下核对无误后，上传更改即可。
