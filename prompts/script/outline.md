标题：$title
选题：$topic
目标时长：$target_duration_s 秒
目标总字数：约 $target_chars 字（允许 ±10%）
章节（必须按顺序全部覆盖，不增不减）：$section_labels

请为每一章分配 target_chars（各章之和约等于 $target_chars），并给出该章的 goal（1–2 句）和 key_points（2–4 条）。

输出 JSON，格式如下：
{
  "title_hook": "一句抓人的开场钩子",
  "angle": "本期讲解的切入角度",
  "sections": [
    {
      "label": "问题",
      "goal": "这一章要讲清楚什么",
      "key_points": ["要点 1", "要点 2"],
      "target_chars": 400
    }
  ]
}

只输出 JSON。
