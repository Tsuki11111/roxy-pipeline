import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  App,
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Tag,
  Typography,
  Upload,
} from "antd";
import {
  PictureOutlined,
  ReloadOutlined,
  SaveOutlined,
  ThunderboltOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { api } from "../api";
import type { Asset, Episode, ScriptRead, Shot, StoryboardRead } from "../types";

const CARD_LABELS: Record<string, string> = {
  chat_bubble: "对话气泡",
  terminal: "终端",
  browser: "浏览器",
  icon: "图标",
  pure_text: "纯文字",
};
const POSITION_OPTIONS = [
  { value: "left", label: "左侧" },
  { value: "right", label: "右侧" },
  { value: "center", label: "居中" },
];
const BG_OPTIONS = [
  { value: "paper", label: "纸纹浅色" },
  { value: "paper_dark", label: "纸纹深色" },
  { value: "desk", label: "木桌" },
];
const MOTION_OPTIONS = [
  { value: "none", label: "静止" },
  { value: "idle_breathe", label: "待机呼吸" },
  { value: "card_pop", label: "卡片弹出" },
  { value: "subtle_pan", label: "轻微平移" },
];
const MOVE_OPTIONS = [
  { value: "none", label: "无（默认方向）" },
  { value: "slide_in_left", label: "从左侧冲入" },
  { value: "slide_in_right", label: "从右侧冲入" },
  { value: "shift_left", label: "向左微移" },
  { value: "shift_right", label: "向右微移" },
];
const OVERLAY_POSITIONS = [
  { value: "left", label: "左侧" },
  { value: "center", label: "居中" },
  { value: "right", label: "右侧" },
];
const OVERLAY_BLENDS = [
  { value: "normal", label: "正常" },
  { value: "multiply", label: "白底融合" },
];
const OVERLAY_SIZES = [
  { value: "1024x1024", label: "方形 1024×1024" },
  { value: "1080x1920", label: "竖图 1080×1920" },
  { value: "1920x1080", label: "横图 1920×1080" },
];
const EDITABLE_STATUSES = ["READY", "PUBLISHED", "QC"];

interface Props {
  episode: Episode;
  refreshKey: number;
  onChanged: () => void;
}

export default function EpisodeEditorTab({ episode, refreshKey, onChanged }: Props) {
  const { message, modal } = App.useApp();
  const [form] = Form.useForm();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [storyboard, setStoryboard] = useState<StoryboardRead | null>(null);
  const [script, setScript] = useState<ScriptRead | null>(null);
  const [characterAssets, setCharacterAssets] = useState<Asset[]>([]);
  const [propAssets, setPropAssets] = useState<Asset[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [sawRendering, setSawRendering] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiDescription, setAiDescription] = useState("");
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiSize, setAiSize] = useState("1024x1024");
  const [aiCount, setAiCount] = useState(1);
  const [aiBusy, setAiBusy] = useState<"prompt" | "image" | null>(null);
  const [aiCandidates, setAiCandidates] = useState<Asset[]>([]);
  const overlayImage = Form.useWatch("overlay_image", form) as string | undefined;
  const characterImage = Form.useWatch("character_image", form) as
    | string
    | undefined;

  const canEdit = EDITABLE_STATUSES.includes(episode.status);
  const shots = storyboard?.shots ?? [];
  const selected = shots.find((shot) => shot.id === selectedId) ?? null;
  const lineByShot = useMemo(() => {
    const map = new Map<string, string>();
    (script?.lines ?? []).forEach((line) => map.set(line.id, line.text));
    return map;
  }, [script]);

  const starts = useMemo(() => {
    let cursor = 0;
    const result: Record<string, number> = {};
    shots.forEach((shot) => {
      result[shot.id] = cursor;
      cursor += shot.duration_ms;
    });
    return result;
  }, [shots]);

  const load = async () => {
    if (!episode.id) return;
    setLoading(true);
    try {
      const [nextStoryboard, nextScript, assets, props] = await Promise.all([
        api.getStoryboard(episode.id),
        api.getScript(episode.id),
        api.listAssets({ type: "character", status: "APPROVED" }),
        api.listAssets({ type: "prop", status: "APPROVED" }),
      ]);
      setStoryboard(nextStoryboard);
      setScript(nextScript);
      setCharacterAssets(assets);
      setPropAssets(props);
      setSelectedId((current) =>
        current && nextStoryboard.shots.some((shot) => shot.id === current)
          ? current
          : nextStoryboard.shots[0]?.id ?? null,
      );
    } catch (error) {
      message.error(String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [episode.id, refreshKey, episode.status === "READY" ? episode.version : 0]);

  useEffect(() => {
    if (!selected) return;
    const overlay = (selected.card_payload?.overlay ?? {}) as Record<string, any>;
    form.setFieldsValue({
      card_type: selected.card_type,
      card_text:
        selected.card_payload?.text ??
        lineByShot.get(selected.script_line_id) ??
        "",
      character_image: selected.character_image ?? undefined,
      character_position:
        selected.character_position === "none"
          ? undefined
          : selected.character_position,
      bg: selected.bg,
      motion: selected.card_payload?.motion ?? "idle_breathe",
      move: selected.card_payload?.move ?? "none",
      overlay_image: overlay.image ?? undefined,
      overlay_position: overlay.position ?? "center",
      overlay_width_px: overlay.width_px ?? 420,
      overlay_bottom: overlay.bottom ?? 120,
      overlay_opacity: overlay.opacity ?? 1,
      overlay_blend: overlay.blend ?? "normal",
    });
    setDirty(false);
  }, [selected?.id, storyboard, script]);

  useEffect(() => {
    if (!waiting) return;
    if (episode.status === "RENDERING" || episode.status === "QC") {
      setSawRendering(true);
    }
    if (sawRendering && ["READY", "PUBLISHED"].includes(episode.status)) {
      setWaiting(false);
      setSawRendering(false);
      void load();
    }
  }, [episode.status, waiting, sawRendering]);

  const characterOptions = useMemo(() => {
    const options = characterAssets.map((asset) => ({
      value: asset.path,
      label: asset.name || asset.path.split(/[\\/]/).pop() || asset.path,
    }));
    if (
      selected?.character_image &&
      !options.some((option) => option.value === selected.character_image)
    ) {
      options.unshift({
        value: selected.character_image,
        label: `${selected.character_image.split(/[\\/]/).pop() ?? selected.character_image}（当前）`,
      });
    }
    return options;
  }, [characterAssets, selected?.character_image]);

  const bgOptions = useMemo(() => {
    if (selected?.bg && !BG_OPTIONS.some((option) => option.value === selected.bg)) {
      return [...BG_OPTIONS, { value: selected.bg, label: selected.bg }];
    }
    return BG_OPTIONS;
  }, [selected?.bg]);

  const propOptions = useMemo(() => {
    const options = propAssets.map((asset) => ({
      value: asset.path,
      label: asset.name || asset.path.split(/[\\/]/).pop() || asset.path,
    }));
    if (overlayImage && !options.some((option) => option.value === overlayImage)) {
      options.unshift({
        value: overlayImage,
        label: `${overlayImage.split(/[\\/]/).pop() ?? overlayImage}（当前）`,
      });
    }
    return options;
  }, [propAssets, overlayImage]);

  const uploadOverlay = (file: File) => {
    const reader = new FileReader();
    reader.onload = async () => {
      setUploading(true);
      try {
        const data = String(reader.result ?? "").replace(
          /^data:[^;]+;base64,/,
          "",
        );
        const asset = await api.uploadAsset({
          filename: file.name,
          data_base64: data,
          asset_type: "prop",
        });
        form.setFieldValue("overlay_image", asset.path);
        setPropAssets((current) => [
          asset,
          ...current.filter((item) => item.id !== asset.id),
        ]);
        setDirty(true);
        message.success("图片已上传并应用到贴图层");
      } catch (error) {
        message.error(String(error));
      } finally {
        setUploading(false);
      }
    };
    reader.readAsDataURL(file);
  };

  const openAi = () => {
    setAiOpen(true);
    setAiDescription("");
    setAiPrompt("");
    setAiCandidates([]);
  };

  const createPrompt = async () => {
    if (!aiDescription.trim()) {
      message.warning("先写一句你想生成的画面描述");
      return;
    }
    setAiBusy("prompt");
    try {
      const result = await api.generateImagePrompt(aiDescription.trim());
      setAiPrompt(result.prompt);
    } catch (error) {
      message.error(String(error));
    } finally {
      setAiBusy(null);
    }
  };

  const createImages = async () => {
    if (!aiPrompt.trim()) {
      message.warning("先生成或填写生图提示词");
      return;
    }
    setAiBusy("image");
    try {
      const result = await api.generateSeedream({
        prompt: aiPrompt.trim(),
        size: aiSize,
        count: aiCount,
      });
      setAiCandidates(result.assets);
      message.success(`生成了 ${result.assets.length} 张候选图，点击应用`);
    } catch (error) {
      message.error(String(error));
    } finally {
      setAiBusy(null);
    }
  };

  const applyCandidate = (asset: Asset) => {
    form.setFieldValue("overlay_image", asset.path);
    if (!form.getFieldValue("overlay_position")) {
      form.setFieldValue("overlay_position", "center");
    }
    form.setFieldValue("overlay_blend", "multiply");
    setPropAssets((current) => [
      asset,
      ...current.filter((item) => item.id !== asset.id),
    ]);
    setDirty(true);
    setAiOpen(false);
    message.success("已应用到当前镜头的贴图层");
  };

  const selectShot = (shot: Shot) => {
    if (shot.id === selectedId) return;
    const apply = () => {
      setSelectedId(shot.id);
      setDirty(false);
      const video = videoRef.current;
      if (video) {
        const target = (starts[shot.id] ?? 0) / 1000 + 0.05;
        video.currentTime = Math.min(
          target,
          Math.max(0, (video.duration || target) - 0.05),
        );
      }
    };
    if (dirty) {
      modal.confirm({
        title: "放弃未保存的修改？",
        okText: "放弃并切换",
        cancelText: "继续编辑",
        onOk: apply,
      });
      return;
    }
    apply();
  };

  const save = async (): Promise<boolean> => {
    if (!selected) return false;
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.updateShot(selected.id, {
        card_type: values.card_type,
        card_text: values.card_text,
        character_image: values.character_image || null,
        character_position: values.character_image
          ? values.character_position
          : "none",
        bg: values.bg,
        motion: values.motion,
        move: values.move,
        overlay_image: values.overlay_image || null,
        overlay_position: values.overlay_position || "center",
        overlay_width_px: values.overlay_width_px ?? 420,
        overlay_bottom: values.overlay_bottom ?? 120,
        overlay_opacity: values.overlay_opacity ?? 1,
        overlay_blend: values.overlay_blend || "normal",
      });
      message.success("镜头已保存");
      setDirty(false);
      await load();
      onChanged();
      return true;
    } catch (error) {
      message.error(String(error));
      return false;
    } finally {
      setSaving(false);
    }
  };

  const applyAndRerender = async () => {
    if (!selected) return;
    if (dirty) {
      const saved = await save();
      if (!saved) return;
    }
    setWaiting(true);
    setSawRendering(false);
    try {
      await api.rerender(episode.id);
      message.success("已提交重渲染，未变化的镜头会复用缓存");
      onChanged();
    } catch (error) {
      setWaiting(false);
      message.error(String(error));
    }
  };

  if (!loading && shots.length === 0) {
    return <Empty description="这一期还没有分镜，先生成分镜再编辑" />;
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {!canEdit && (
        <Alert
          type="info"
          showIcon
          message={`当前状态 ${episode.status}，完成渲染后才能编辑和重渲染`}
        />
      )}
      {waiting && (
        <Alert
          type="info"
          showIcon
          message="重渲染中"
          description="未修改的镜头会复用缓存；完成后预览会自动刷新。"
        />
      )}

      <Card
        title="成片预览"
        extra={<Typography.Text type="secondary">基于上一次渲染</Typography.Text>}
      >
        {episode.output_path ? (
          <video
            key={`${episode.output_path}-${episode.version}`}
            ref={videoRef}
            src={api.videoUrl(episode.id, episode.version)}
            controls
            style={{ width: "100%", maxHeight: 560, background: "#111", borderRadius: 8 }}
          />
        ) : (
          <Empty description="还没有成片，完成一次渲染后才能预览" />
        )}
      </Card>

      <Card title="镜头时间线" extra={`${shots.length} 个镜头`}>
        <div className="editor-timeline">
          {shots.map((shot) => (
            <button
              type="button"
              key={shot.id}
              className={`editor-shot ${shot.id === selectedId ? "selected" : ""}`}
              style={{ width: Math.max(88, Math.round(shot.duration_ms / 25)) }}
              onClick={() => selectShot(shot)}
            >
              <span className="editor-shot-index">#{shot.seq}</span>
              <span className="editor-shot-card">
                {CARD_LABELS[shot.card_type] ?? shot.card_type}
              </span>
              <span className="editor-shot-time">
                {(shot.duration_ms / 1000).toFixed(1)}s
              </span>
            </button>
          ))}
        </div>
      </Card>

      <Card
        title="镜头属性"
        extra={
          dirty ? <Tag color="gold">有未保存修改</Tag> : <Tag color="green">已保存</Tag>
        }
      >
        {selected ? (
          <>
            <Form
              form={form}
              layout="vertical"
              disabled={!canEdit || saving || waiting}
              onValuesChange={() => setDirty(true)}
            >
              <Space size={16} style={{ width: "100%" }} align="start" wrap>
                <Form.Item name="card_type" label="卡片类型" style={{ width: 180 }}>
                  <Select
                    options={Object.entries(CARD_LABELS).map(([value, label]) => ({
                      value,
                      label,
                    }))}
                  />
                </Form.Item>
                <Form.Item name="bg" label="背景" style={{ width: 180 }}>
                  <Select options={bgOptions} />
                </Form.Item>
                <Form.Item name="motion" label="动作" style={{ width: 180 }}>
                  <Select options={MOTION_OPTIONS} />
                </Form.Item>
                <Form.Item name="move" label="入场方向" style={{ width: 180 }}>
                  <Select options={MOVE_OPTIONS} />
                </Form.Item>
                <Form.Item label="镜头时长" style={{ width: 180 }}>
                  <Input
                    value={`${(selected.duration_ms / 1000).toFixed(2)} 秒`}
                    disabled
                  />
                </Form.Item>
              </Space>

              <Form.Item
                name="card_text"
                label="卡片文案"
                extra="只影响画面中的卡片，不改旁白和配音。"
              >
                <Input.TextArea rows={2} maxLength={500} showCount />
              </Form.Item>

              <Space size={16} style={{ width: "100%" }} align="start" wrap>
                <Form.Item
                  name="character_image"
                  label="角色立绘"
                  style={{ minWidth: 360, flex: 1 }}
                >
                  <Select
                    allowClear
                    showSearch
                    optionFilterProp="label"
                    placeholder="不显示角色"
                    options={characterOptions}
                  />
                </Form.Item>
                <Form.Item name="character_position" label="角色位置" style={{ width: 160 }}>
                  <Select
                    options={POSITION_OPTIONS}
                    disabled={!characterImage}
                  />
                </Form.Item>              </Space>

              <Card size="small" title="贴图层（可选）" style={{ marginTop: 16 }}>
                <Space wrap align="start">
                  <Form.Item
                    name="overlay_image"
                    label="贴图"
                    style={{ minWidth: 320 }}
                  >
                    <Select
                      allowClear
                      showSearch
                      optionFilterProp="label"
                      placeholder="无贴图"
                      options={propOptions}
                    />
                  </Form.Item>
                  <Upload
                    accept="image/png,image/jpeg,image/webp"
                    showUploadList={false}
                    disabled={!canEdit || saving || waiting || uploading}
                    beforeUpload={(file) => {
                      uploadOverlay(file as File);
                      return false;
                    }}
                  >
                    <Button
                      icon={<UploadOutlined />}
                      loading={uploading}
                      disabled={!canEdit || saving || waiting}
                    >
                      上传图片
                    </Button>
                  </Upload>
                  <Button
                    icon={<PictureOutlined />}
                    onClick={openAi}
                    disabled={!canEdit || saving || waiting}
                  >
                    Seedream 生成
                  </Button>
                </Space>
                {overlayImage && (
                  <div className="editor-overlay-preview">
                    <img src={api.assetPathUrl(overlayImage)} alt="贴图预览" />
                  </div>
                )}
                <Space wrap>
                  <Form.Item
                    name="overlay_position"
                    label="贴图位置"
                    style={{ width: 140 }}
                  >
                    <Select
                      options={OVERLAY_POSITIONS}
                      disabled={!overlayImage}
                    />
                  </Form.Item>
                  <Form.Item
                    name="overlay_width_px"
                    label="宽度(px)"
                    style={{ width: 150 }}
                  >
                    <InputNumber
                      min={40}
                      max={1900}
                      style={{ width: "100%" }}
                      disabled={!overlayImage}
                    />
                  </Form.Item>
                  <Form.Item
                    name="overlay_bottom"
                    label="底部(px)"
                    style={{ width: 140 }}
                  >
                    <InputNumber
                      min={0}
                      max={1080}
                      style={{ width: "100%" }}
                      disabled={!overlayImage}
                    />
                  </Form.Item>
                  <Form.Item
                    name="overlay_opacity"
                    label="不透明度"
                    style={{ width: 140 }}
                  >
                    <InputNumber
                      min={0}
                      max={1}
                      step={0.1}
                      style={{ width: "100%" }}
                      disabled={!overlayImage}
                    />
                  </Form.Item>
                  <Form.Item
                    name="overlay_blend"
                    label="混合模式"
                    style={{ width: 140 }}
                  >
                    <Select
                      options={OVERLAY_BLENDS}
                      disabled={!overlayImage}
                    />
                  </Form.Item>
                </Space>
              </Card>
            </Form>

            <Space style={{ marginTop: 8 }} wrap>
              <Button
                icon={<SaveOutlined />}
                onClick={save}
                loading={saving}
                disabled={!canEdit || waiting}
              >
                保存镜头
              </Button>
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={applyAndRerender}
                loading={waiting}
                disabled={!canEdit || saving}
              >
                保存并重渲染
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={load}
                disabled={saving || waiting}
              >
                刷新数据
              </Button>
              <Typography.Text type="secondary">
                时长由配音决定；需要改时长请先在脚本里改台词并重新配音。
              </Typography.Text>
            </Space>
          </>
        ) : (
          <Empty description="选择一个镜头开始编辑" />
        )}
      </Card>

      <Modal
        title="Seedream 生成贴图"
        open={aiOpen}
        onCancel={() => setAiOpen(false)}
        footer={null}
        width={760}
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Text type="secondary">
            先写画面描述，让 DeepSeek 生成生图提示词；可以手动修改后再生成。
          </Typography.Text>
          <Input.TextArea
            rows={3}
            value={aiDescription}
            onChange={(event) => setAiDescription(event.target.value)}
            placeholder="例如：一个发光的蓝色三棱镜，透明背景，扁平插画风格"
          />
          <Button
            onClick={createPrompt}
            loading={aiBusy === "prompt"}
            disabled={aiBusy === "image"}
          >
            用 DeepSeek 生成提示词
          </Button>
          <Input.TextArea
            rows={4}
            value={aiPrompt}
            onChange={(event) => setAiPrompt(event.target.value)}
            placeholder="Seedream 提示词"
          />
          <Space wrap>
            <Select
              value={aiSize}
              onChange={setAiSize}
              options={OVERLAY_SIZES}
              style={{ width: 190 }}
            />
            <Select
              value={aiCount}
              onChange={setAiCount}
              options={[
                { value: 1, label: "1 张" },
                { value: 2, label: "2 张" },
              ]}
              style={{ width: 100 }}
            />
            <Button
              type="primary"
              onClick={createImages}
              loading={aiBusy === "image"}
              disabled={aiBusy === "prompt"}
            >
              生成图片
            </Button>
          </Space>
          {aiCandidates.length > 0 && (
            <div className="editor-ai-candidates">
              {aiCandidates.map((asset) => (
                <button
                  type="button"
                  key={asset.id}
                  className="editor-ai-candidate"
                  onClick={() => applyCandidate(asset)}
                >
                  <img src={api.assetPathUrl(asset.path)} alt={asset.name} />
                  <span>应用到镜头</span>
                </button>
              ))}
            </div>
          )}
        </Space>
      </Modal>
    </Space>
  );
}
