章节：$section_label

本段台词（每句必须对应一个镜头，共 $line_count 句）：
$lines_json

可用角色资产（character_image 只能填下面第一列的路径）：
$catalog

上一段最后一个镜头：$previous

请为每一句台词选择一个镜头，输出 JSON：
{
  "shots": [
    {
      "line_seq": 1,
      "card_type": "chat_bubble",
      "card_style": "ai_reply",
      "character_image": "character_packs/roxy/roxy_calm_standing_01.png",
      "character_position": "left"
    }
  ]
}

约束：
- line_seq 必须是该段台词的序号，且每句都要出现一次。
- card_type / character_position 只能使用系统允许的值。
- 本节最后一个镜头必须是 icon 或 pure_text。
- 连续 3 个镜头不要用同一卡片类型；角色连续出现不要超过 4 个。
只输出 JSON。
