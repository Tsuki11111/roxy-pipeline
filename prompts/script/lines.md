正在写章节「$section_label」。

本章目标：$goal
本章 beat：
$beats
上下文：$context
本章目标字数：约 $target_chars 字（允许 ±10%）

请写这一章的口播台词，输出 JSON：
{
  "lines": [
    {"speaker": "narrator", "text": "……"},
    {"speaker": "roxy", "text": "……"}
  ]
}

规则：
- 每句不超过 25 字；洛琪希台词不超过 15 字；洛琪希台词约占本章 10%–30%。
- speaker 只能是 narrator 或 roxy。
- 按本章 beat 的顺序推进，不要重复其它章节的内容。
- 不要写章节标题、镜头说明、括号旁白或 Markdown。
只输出 JSON。
