章节：$section_label

本段台词（共 $line_count 句，每句必须被且只被一个镜头覆盖）：
$lines_json

可用角色资产（character_image 只能填下面第一列的路径）：
$catalog

上一段最后一个镜头：$previous

请把这些台词编排成少量连贯的镜头，输出 JSON：
{
  "shots": [
    {
      "line_seqs": [1, 2, 3],
      "card_type": "chat_bubble",
      "card_style": "ai_reply",
      "character_image": "character_packs/roxy/roxy_calm_standing_01.png",
      "character_position": "left",
      "continuity_group": "solution-1",
      "scene": {
        "setting": "暖纸舞台，右侧有一块演示白板",
        "entities": [
          {"id": "diagram", "name": "流程图", "appearance": "三个圆角节点，陶土色连线"}
        ]
      }
    }
  ]
}

约束：
- `line_seqs` 必须是连续序号，1–4 句一组；所有台词按顺序恰好覆盖一次。
- 详细讲解一个方案/例子时，把相关句子合并成一个镜头；不要为每句生成独立动画。
- 概览“有哪几种方案”可以单独成一个镜头；随后详细讲某个方案时用新的 continuity_group。
- 同一 continuity_group 的多个镜头共享相同的 setting 和 entity 定义。
- 单镜头 3–20 秒，由系统按时长估算，不需要你填写。
- card_type / character_position 只能使用系统允许的值。
- pose=standing 适合常规讲解；pose=bust 是半身反应图，适合强调、吐槽、惊讶等情绪镜头。
- 本节最后一个镜头必须是 icon 或 pure_text。
- 连续 3 个镜头不要用同一卡片类型；角色连续出现不要超过 4 个。
只输出 JSON。
