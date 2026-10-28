当前脚本 JSON：
$lines_json

确定性校验错误：
$errors

目标总字数：$target_chars
章节顺序：$section_labels

请修正脚本并输出完整 JSON：
{"lines": [{"speaker": "narrator", "section": "问题", "text": "……"}]}

要求：
- 保留已经合格的句子，只改必要部分。
- 每句不超过 25 字；洛琪希台词不超过 15 字。
- 章节顺序不变，每个章节都必须有内容。
- 全文字数接近目标总字数（允许 ±10%）。
只输出 JSON。
