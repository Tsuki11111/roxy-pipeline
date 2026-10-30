请根据下面的剧集上下文和镜头数据，生成 Remotion 镜头组件。

$skill

## 剧集上下文

标题：$title
主题：$topic
文章摘要：$summary
大纲：
$outline

## 镜头

$shot_json

## 可用资产

$assets_json

## 上一镜头结尾（用于衔接，可为空）

$previous_tail

## 校验错误（首次为空）

$error_feedback

请只输出 JSON：{"schema_version":"1","component_name":"$component_name","code":"完整 TSX 文件内容","summary":"一句话说明"}。
