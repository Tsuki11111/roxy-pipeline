输入文本：
$text

生成数量：$count
$forced

已有资产（可按语义复用 reuse_key）：
$assets

输出 JSON：
{"assets":[{"type":"prop","name":"简洁中文名","reuse_key":"prop:stable-semantic-key","prompt":"视觉描述，必须包含 no text, no letters, no watermark","size":"1024x1024","reason":"为什么需要这个素材/为什么复用"}]}

要求：
- reuse_key 使用小写英文/数字/连字符，并以类型前缀开头，例如 prop:blue-light-prism。
- 如果复用已有资产，reuse_key 必须与列表中的完全一致。
- size：background 用 1920x1088，prop/icon 用 1024x1024，cover 用 1080x1920。
- 不要输出任何角色、人物、动漫或版权形象。
- prompt 里写清与本期主题匹配的风格（色调、材质、线条、视角），同组素材保持一致，不要混用写实照片、扁平插画、赛博霓虹等冲突风格。