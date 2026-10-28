大纲 JSON：
$outline_json

请为每一章写 3–5 个叙事 beat，按顺序说明这一段怎么推进；只写节奏和内容，不要写台词。

输出 JSON，格式如下：
{
  "sections": [
    {
      "label": "问题",
      "summary": "本章一句话总结",
      "beats": ["先抛出问题", "举一个反例", "留下悬念"]
    }
  ]
}

章节顺序和 label 必须与大纲完全一致。只输出 JSON。
