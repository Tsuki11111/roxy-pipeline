import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  App,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import {
  CheckCircleOutlined,
  EditOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  RocketOutlined,
} from "@ant-design/icons";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import type {
  Episode,
  EpisodeAudioRead,
  QcReport,
  ScriptLine,
  ScriptRead,
  Shot,
  StoryboardRead,
} from "../types";
import { formatDate, formatDuration, statusMeta } from "../ui";
import EpisodeEditorTab from "./EpisodeEditorTab";

const CARD_TYPES = ["chat_bubble", "terminal", "browser", "icon", "pure_text"];
const POSITIONS = ["left", "right", "center", "none"];
const TRANSITIONS = ["cut", "fade", "slide_in"];
const MOVES = ["none", "slide_in_left", "slide_in_right", "shift_left", "shift_right"];
const ACTIVE_STATUSES = [
  "SCRIPTING",
  "STORYBOARDING",
  "VOICING",
  "ALIGNING",
  "RENDERING",
  "QC",
];
const STAGE_PERCENT: Record<string, number> = {
  SCRIPTING: 12,
  STORYBOARDING: 40,
  VOICING: 60,
  ALIGNING: 72,
  RENDERING: 88,
  QC: 96,
};
const NODE_LABELS: Record<string, string> = {
  "script.generate": "脚本 Agent：正在拆分章节、写逐句台词",
  "storyboard.generate": "分镜 Agent：正在选择镜头和卡片",
  "voice.episode": "IndexTTS2：正在逐句合成配音",
  "align.episode": "字级对齐：正在计算每句时间",
  "render.episode": "渲染：正在逐镜头生成画面",
  "qc.episode": "质检：规则检查 + DeepSeek 抽帧审查",
};

export default function EpisodeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message, modal } = App.useApp();
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeSince, setActiveSince] = useState<number | null>(null);
  const [tick, setTick] = useState(0);

  const load = async () => {
    if (!id) return;
    try {
      setEpisode(await api.getEpisode(id));
    } catch (error) {
      message.error(String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [id]);

  useEffect(() => {
    if (!episode || !ACTIVE_STATUSES.includes(episode.status)) {
      setActiveSince(null);
      return;
    }
    setActiveSince((value) => value ?? Date.now());
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [episode?.status]);

  useEffect(() => {
    if (!id || !episode || !ACTIVE_STATUSES.includes(episode.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.getEpisode(id);
        setEpisode(next);
      } catch {
        // Keep the last known state while a polling request is in flight.
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [id, episode?.status]);

  const refresh = async () => {
    await load();
    setRefreshKey((value) => value + 1);
  };

  const run = async (name: string, label: string) => {
    if (!id) return;
    setBusy(name);
    try {
      await api.action(id, name);
      message.success(`${label}已提交`);
      await refresh();
    } catch (error) {
      message.error(String(error));
    } finally {
      setBusy(null);
    }
  };

  const runConfirm = async (kind: "script" | "storyboard") => {
    if (!id) return;
    setBusy(kind);
    try {
      if (kind === "script") await api.confirmScript(id);
      else await api.confirmStoryboard(id);
      message.success("已确认，进入下一阶段");
      await refresh();
    } catch (error) {
      message.error(String(error));
    } finally {
      setBusy(null);
    }
  };

  const actions = useMemo(() => {
    if (!episode) return [];
    const items: { label: string; name: string; primary?: boolean }[] = [];
    switch (episode.status) {
      case "SCRIPT_REVIEW":
        items.push({ label: "确认脚本", name: "confirm-script", primary: true });
        break;
      case "STORYBOARDING":
        items.push({ label: "生成分镜", name: "generate-storyboard", primary: true });
        items.push({ label: "确认分镜", name: "confirm-storyboard" });
        items.push({ label: "重生成分镜", name: "regenerate-storyboard" });
        break;
      case "VOICING":
        items.push({ label: "开始配音", name: "voice", primary: true });
        items.push({ label: "重试配音", name: "retry-voice" });
        break;
      case "ALIGNING":
        items.push({ label: "开始对齐", name: "align", primary: true });
        items.push({ label: "重试对齐", name: "retry-align" });
        break;
      case "QC":
        items.push({ label: "重新质检", name: "qc", primary: true });
        items.push({ label: "重试质检", name: "retry-qc" });
        break;
      case "READY":
        items.push({ label: "生成发布包", name: "package", primary: true });
        items.push({ label: "发布", name: "publish" });
        break;
      case "PUBLISHED":
        items.push({ label: "重新生成发布包", name: "package" });
        break;
    }
    if (episode.health === "FAILED") {
      items.push({ label: "续跑", name: "resume", primary: true });
    }
    return items;
  }, [episode]);

  const execute = async (name: string, label: string) => {    if (name === "confirm-script" || name === "confirm-storyboard") {
      await runConfirm(name === "confirm-script" ? "script" : "storyboard");
    } else if (name === "package") {
      setBusy(name);
      try {
        await api.buildPackage(id!);
        message.success("发布包已生成");
        await refresh();
      } catch (error) {
        message.error(String(error));
      } finally {
        setBusy(null);
      }
    } else if (name === "publish") {
      setBusy(name);
      try {
        await api.publish(id!);
        message.success("已发布");
        await refresh();
      } catch (error) {
        message.error(String(error));
      } finally {
        setBusy(null);
      }
    } else {
      await run(name, label);
    }
  };

  const cancelGeneration = () => {
    if (!id) return;
    modal.confirm({
      title: "取消这一期的生成？",
      content: "正在执行的任务会在当前步骤结束后停止，已生成的文件保留。",
      okText: "取消生成",
      okType: "danger",
      cancelText: "继续等待",
      onOk: async () => {
        await api.action(id, "cancel");
        message.success("已取消");
        await refresh();
      },
    });
  };

  const deleteEpisode = () => {
    if (!id) return;
    modal.confirm({
      title: "删除这个视频期？",
      content: "会删除数据库记录和关联脚本/镜头/音频，不删除 output 里已生成的文件。",
      okText: "删除",
      okType: "danger",
      cancelText: "保留",
      onOk: async () => {
        await api.deleteEpisode(id);
        message.success("视频期已删除");
        navigate("/episodes");
      },
    });
  };

  if (loading && !episode) return <Card loading />;
  if (!episode) return <Empty description="视频期不存在" />;

  const meta = statusMeta[episode.status];
  const active = ACTIVE_STATUSES.includes(episode.status);
  const percent = STAGE_PERCENT[episode.status] ?? 0;
  const nodeLabel =
    (episode.current_node && NODE_LABELS[episode.current_node]) ||
    `${meta.label}：任务执行中`;
  const elapsed = activeSince
    ? Math.max(0, Math.floor((Date.now() - activeSince) / 1000))
    : 0;

  return (
    <Space direction="vertical" size={18} className="page-stack">
      <div className="page-heading">
        <div>
          <Button type="link" className="back-link" onClick={() => navigate("/episodes")}>
            ← 返回视频期
          </Button>
          <Typography.Title level={2}>{episode.title}</Typography.Title>
          <Space wrap>
            <Tag color={meta.color}>{meta.label}</Tag>
            <Tag color={episode.health === "OK" ? "green" : episode.health === "WARNING" ? "gold" : "red"}>
              {episode.health}
            </Tag>
            <Typography.Text type="secondary">{episode.topic || "未填写选题"}</Typography.Text>
          </Space>
        </div>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={refresh}>
            刷新
          </Button>
          {actions.map((item) => (
            <Button
              key={item.name}
              type={item.primary ? "primary" : "default"}
              loading={busy === item.name}
              onClick={() => execute(item.name, item.label)}
            >
              {item.label}
            </Button>
          ))}
          {active ? (
            <Button danger onClick={cancelGeneration}>
              取消生成
            </Button>
          ) : (
            <Button danger onClick={deleteEpisode}>
              删除
            </Button>
          )}
        </Space>
      </div>

      {active && (
        <Card className="progress-card">
          <div className="progress-head">
            <Spin size="small" />
            <div>
              <Typography.Text strong>{nodeLabel}</Typography.Text>
              <Typography.Paragraph type="secondary" style={{ margin: 0 }}>
                当前状态 {meta.label}
                {episode.current_node ? ` · ${episode.current_node}` : ""}
              </Typography.Paragraph>
            </div>
            <Tag color="processing">{percent}%</Tag>
          </div>
          <Progress percent={percent} status="active" showInfo={false} />
          <Typography.Text type="secondary">
            页面每 3 秒自动刷新 · 已等待 {elapsed} 秒
          </Typography.Text>
          {episode.health === "FAILED" && (
            <Alert
              style={{ marginTop: 12 }}
              type="error"
              showIcon
              message="任务失败，可在顶部点击续跑或重试"
            />
          )}
        </Card>
      )}

      <Tabs
        className="detail-tabs"
        items={[
          {
            key: "overview",
            label: "概览",
            children: <Overview episode={episode} />,
          },
          {
            key: "script",
            label: "脚本",
            children: <ScriptTab episode={episode} refreshKey={refreshKey} onChanged={refresh} />,
          },
          {
            key: "storyboard",
            label: "分镜",
            children: (
              <StoryboardTab episode={episode} refreshKey={refreshKey} onChanged={refresh} />
            ),
          },
          {
            key: "editor",
            label: "剪辑",
            children: (
              <EpisodeEditorTab episode={episode} refreshKey={refreshKey} onChanged={refresh} />
            ),
          },
          {
            key: "audio",
            label: "配音与对齐",
            children: <AudioTab episode={episode} refreshKey={refreshKey} />,
          },
          {
            key: "qc",
            label: "质检",
            children: <QcTab episode={episode} refreshKey={refreshKey} onChanged={refresh} />,
          },
          {
            key: "package",
            label: "发布包",
            children: <PackageTab episode={episode} refreshKey={refreshKey} />,
          },
        ]}
      />
    </Space>
  );
}

function Overview({ episode }: { episode: Episode }) {
  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="状态">{statusMeta[episode.status].label}</Descriptions.Item>
          <Descriptions.Item label="健康">{episode.health}</Descriptions.Item>
          <Descriptions.Item label="当前节点">{episode.current_node ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="目标时长">{episode.target_duration_s} 秒</Descriptions.Item>
          <Descriptions.Item label="创建时间">{formatDate(episode.created_at)}</Descriptions.Item>
          <Descriptions.Item label="更新时间">{formatDate(episode.updated_at)}</Descriptions.Item>
          <Descriptions.Item label="成片路径" span={3}>
            <Typography.Text copyable={!!episode.output_path}>
              {episode.output_path ?? "—"}
            </Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="MinIO" span={3}>
            <Typography.Text copyable={!!episode.output_meta?.minio?.uri}>
              {episode.output_meta?.minio?.uri ?? "—"}
            </Typography.Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="流程">
        <Space wrap size={8}>
          {["脚本", "分镜", "配音", "对齐", "渲染", "质检", "发布"].map((step, index) => {
            const order = [
              "SCRIPT_REVIEW",
              "STORYBOARDING",
              "VOICING",
              "ALIGNING",
              "RENDERING",
              "QC",
              "READY",
            ];
            const current = order.indexOf(episode.status);
            const done = current > index || ["PUBLISHED"].includes(episode.status);
            const active = current === index;
            return (
              <Tag key={step} color={active ? "purple" : done ? "green" : "default"}>
                {done ? "✓ " : active ? "● " : ""}
                {step}
              </Tag>
            );
          })}
        </Space>
      </Card>
    </Space>
  );
}

function ScriptTab({
  episode,
  refreshKey,
  onChanged,
}: {
  episode: Episode;
  refreshKey: number;
  onChanged: () => void;
}) {
  const { message } = App.useApp();
  const [data, setData] = useState<ScriptRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<ScriptLine | null>(null);
  const [text, setText] = useState("");
  const [optimizing, setOptimizing] = useState(false);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      setData(await api.getScript(episode.id));
    } catch (error) {
      message.error(String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [episode.id, episode.status, refreshKey]);

  const edit = (line: ScriptLine) => {
    setEditing(line);
    setText(line.text);
  };

  const save = async () => {
    if (!editing) return;
    try {
      if (["READY", "QC"].includes(episode.status)) {
        await api.reviseLine(episode.id, editing.id, text);
        message.success("已提交局部重跑");
      } else {
        await api.updateScriptLine(editing.id, text);
        message.success("台词已保存");
      }
      setEditing(null);
      await load();
      onChanged();
    } catch (error) {
      message.error(String(error));
    }
  };

  const validate = async () => {
    try {
      const result = await api.validateScript(episode.id);
      message[result.valid ? "success" : "warning"](
        result.valid ? "脚本校验通过" : `发现 ${result.errors.length} 个问题`,
      );
      await load();
    } catch (error) {
      message.error(String(error));
    }
  };

  const optimize = async () => {
    setOptimizing(true);
    try {
      const result = await api.optimizeScript(episode.id);
      message.success(`文稿已润色，修改 ${result.changed_count} 句`);
      await load();
      onChanged();
    } catch (error) {
      message.error(String(error));
    } finally {
      setOptimizing(false);
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card>
        <Space wrap>
          <Button onClick={load} icon={<ReloadOutlined />}>
            刷新
          </Button>
          <Button onClick={validate}>重新校验</Button>
          {episode.status === "SCRIPT_REVIEW" && (
            <Button loading={optimizing} onClick={optimize}>
              润色文稿
            </Button>
          )}
          {data && (
            <Tag color={data.validation.valid ? "green" : "red"}>
              {data.validation.valid ? "校验通过" : `${data.validation.errors.length} 个问题`}
            </Tag>
          )}
        </Space>
        {data && !data.validation.valid && (
          <Alert
            style={{ marginTop: 16 }}
            type="error"
            showIcon
            message="脚本校验未通过"
            description={
              <ul className="compact-list">
                {data.validation.errors.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            }
          />
        )}
      </Card>
      <Card>
        <Table
          loading={loading}
          rowKey="id"
          dataSource={data?.lines ?? []}
          pagination={{ pageSize: 30 }}
          columns={[
            { title: "#", dataIndex: "seq", width: 64 },
            { title: "章节", dataIndex: "section", width: 120 },
            { title: "台词", dataIndex: "text" },
            { title: "字数", dataIndex: "char_count", width: 80 },
            {
              title: "操作",
              width: 100,
              render: (_, row) => (
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  disabled={["PUBLISHED", "CANCELLED"].includes(episode.status)}
                  onClick={() => edit(row)}
                >
                  编辑
                </Button>
              ),
            },
          ]}
        />
      </Card>
      <Modal
        title={editing ? `编辑第 ${editing.seq} 句` : "编辑台词"}
        open={!!editing}
        onCancel={() => setEditing(null)}
        onOk={save}
        okText="保存"
      >
        <Input.TextArea
          rows={5}
          value={text}
          onChange={(event) => setText(event.target.value)}
          maxLength={200}
          showCount
        />
      </Modal>
    </Space>
  );
}

function StoryboardTab({
  episode,
  refreshKey,
  onChanged,
}: {
  episode: Episode;
  refreshKey: number;
  onChanged: () => void;
}) {
  const { message } = App.useApp();
  const [data, setData] = useState<StoryboardRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<Shot | null>(null);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      setData(await api.getStoryboard(episode.id));
    } catch (error) {
      message.error(String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [episode.id, episode.status, refreshKey]);

  const edit = (shot: Shot) => {
    setEditing(shot);
    form.setFieldsValue({
      duration_ms: shot.duration_ms,
      card_type: shot.card_type,
      character_position: shot.character_position,
      transition: shot.transition,
      move: shot.card_payload?.move ?? "none",
      bg: shot.bg,
    });
  };

  const save = async () => {
    if (!editing) return;
    try {
      const values = await form.validateFields();
      await api.updateShot(editing.id, values);
      message.success("镜头已更新");
      setEditing(null);
      await load();
      onChanged();
    } catch (error) {
      message.error(String(error));
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={load}>
            刷新
          </Button>
          {data && (
            <>
              <Tag color={data.rhythm.valid ? "green" : "red"}>
                节奏 {data.rhythm.valid ? "通过" : "违规"}
              </Tag>
              <Tag>镜头 {data.rhythm.shot_count}</Tag>
              <Tag>角色占比 {(data.rhythm.character_ratio * 100).toFixed(1)}%</Tag>
              <Tag>平均时长 {(data.rhythm.avg_duration_ms / 1000).toFixed(1)}s</Tag>
            </>
          )}
        </Space>
        {data && !data.rhythm.valid && (
          <Alert
            style={{ marginTop: 16 }}
            type="error"
            showIcon
            message="分镜节奏未通过"
            description={
              <ul className="compact-list">
                {data.rhythm.errors.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            }
          />
        )}
      </Card>
      <Card>
        <Table
          loading={loading}
          rowKey="id"
          dataSource={data?.shots ?? []}
          pagination={{ pageSize: 30 }}
          columns={[
            { title: "#", dataIndex: "seq", width: 64 },
            { title: "卡片", dataIndex: "card_type", width: 140 },
            {
              title: "角色",
              dataIndex: "character_image",
              ellipsis: true,
              render: (value) => (value ? value.split("/").pop() : "—"),
            },
            { title: "位置", dataIndex: "character_position", width: 80 },
            {
              title: "时长",
              dataIndex: "duration_ms",
              width: 90,
              render: (value) => `${(value / 1000).toFixed(1)}s`,
            },
            {
              title: "动作",
              dataIndex: "card_payload",
              width: 130,
              render: (payload) => payload?.move ?? "none",
            },
            { title: "背景", dataIndex: "bg", width: 100 },
            {
              title: "操作",
              width: 90,
              render: (_, row) => (
                <Button size="small" onClick={() => edit(row)}>
                  编辑
                </Button>
              ),
            },
          ]}
        />
      </Card>
      <Modal
        title={editing ? `编辑镜头 ${editing.seq}` : "编辑镜头"}
        open={!!editing}
        onCancel={() => setEditing(null)}
        onOk={save}
        okText="保存"
      >
        <Form form={form} layout="vertical">
          <Form.Item name="duration_ms" label="时长（毫秒）">
            <InputNumber min={500} max={15000} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="card_type" label="卡片类型">
            <Select options={CARD_TYPES.map((value) => ({ value }))} />
          </Form.Item>
          <Form.Item name="character_position" label="角色位置">
            <Select options={POSITIONS.map((value) => ({ value }))} />
          </Form.Item>
          <Form.Item name="transition" label="转场">
            <Select options={TRANSITIONS.map((value) => ({ value }))} />
          </Form.Item>
          <Form.Item name="move" label="角色位移">
            <Select options={MOVES.map((value) => ({ value }))} />
          </Form.Item>
          <Form.Item name="bg" label="背景 key">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

function AudioTab({ episode, refreshKey }: { episode: Episode; refreshKey: number }) {
  const { message } = App.useApp();
  const [data, setData] = useState<EpisodeAudioRead | null>(null);

  useEffect(() => {
    api.getAudio(episode.id).then(setData).catch((error) => message.error(String(error)));
  }, [episode.id, episode.status, refreshKey]);

  const meta = data?.meta ?? {};
  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card>
        <Space size={40} wrap>
          <Statistic title="音轨总长" value={formatDuration(meta.total_ms)} />
          <Statistic title="对齐粒度" value={meta.alignment_granularity ?? "—"} />
          <Statistic title="逐句音频" value={data?.lines.length ?? 0} />
          <Statistic title="参考音" value={meta.voice_key?.slice(0, 8) ?? "—"} />
        </Space>
        <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
          {data?.audio_path ?? "尚未生成音轨"}
        </Typography.Paragraph>
      </Card>
      <Card>
        <Table
          rowKey="id"
          dataSource={data?.lines ?? []}
          pagination={{ pageSize: 30 }}
          columns={[
            { title: "#", dataIndex: "seq", width: 64 },
            {
              title: "时长",
              dataIndex: "duration_ms",
              width: 100,
              render: (value) => `${(value / 1000).toFixed(2)}s`,
            },
            { title: "采样率", dataIndex: "sample_rate", width: 100 },
            { title: "文件", dataIndex: "path", ellipsis: true },
          ]}
        />
      </Card>
    </Space>
  );
}

function QcTab({
  episode,
  refreshKey,
  onChanged,
}: {
  episode: Episode;
  refreshKey: number;
  onChanged: () => void;
}) {
  const { message } = App.useApp();
  const [data, setData] = useState<QcReport | null>(null);

  const load = () => {
    api.getQc(episode.id).then(setData).catch((error) => message.error(String(error)));
  };

  useEffect(load, [episode.id, episode.status, refreshKey]);

  const resolve = async (reviewId: string) => {
    try {
      await api.resolveReview(reviewId);
      message.success("已标记处理");
      load();
      onChanged();
    } catch (error) {
      message.error(String(error));
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card>
        <Space size={40} wrap>
          <Statistic title="质检结论" value={data?.meta?.level ?? "—"} />
          <Statistic title="错误" value={data?.meta?.errors ?? 0} />
          <Statistic title="警告" value={data?.meta?.warnings ?? 0} />
          <Statistic title="抽帧" value={data?.meta?.frame_count ?? 0} />
        </Space>
      </Card>
      <Card title="检查项">
        <Table
          rowKey="id"
          dataSource={data?.reviews ?? []}
          pagination={false}
          columns={[
            { title: "检查项", dataIndex: "check_item", width: 220 },
            {
              title: "级别",
              dataIndex: "level",
              width: 100,
              render: (level) => (
                <Tag color={level === "PASS" ? "green" : level === "ERROR" ? "red" : "gold"}>
                  {level}
                </Tag>
              ),
            },
            {
              title: "详情",
              dataIndex: "detail",
              render: (detail) => detail?.message ?? JSON.stringify(detail),
            },
            {
              title: "处理",
              width: 120,
              render: (_, row) =>
                row.level === "PASS" ? (
                  <Typography.Text type="secondary">—</Typography.Text>
                ) : row.resolved_at ? (
                  <Tag color="green">已处理</Tag>
                ) : (
                  <Button size="small" onClick={() => resolve(row.id)}>
                    标记处理
                  </Button>
                ),
            },
          ]}
        />
      </Card>
    </Space>
  );
}

function PackageTab({
  episode,
  refreshKey,
}: {
  episode: Episode;
  refreshKey: number;
}) {
  const { message } = App.useApp();
  const [manifest, setManifest] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setManifest(await api.getPackage(episode.id));
    } catch (error) {
      message.error(String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [episode.id, episode.status, refreshKey]);

  const build = async () => {
    try {
      await api.buildPackage(episode.id);
      message.success("发布包已生成");
      await load();
    } catch (error) {
      message.error(String(error));
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card loading={loading}>
        <Space wrap>
          <Button type="primary" icon={<RocketOutlined />} onClick={build}>
            {manifest ? "重新生成发布包" : "生成发布包"}
          </Button>
          <Typography.Text copyable={!!episode.output_path}>
            {episode.output_path ?? "尚未生成成片"}
          </Typography.Text>
        </Space>
        {episode.output_meta?.minio?.uri && (
          <Typography.Paragraph style={{ marginTop: 12, marginBottom: 0 }} copyable>
            MinIO：{episode.output_meta.minio.uri}
          </Typography.Paragraph>
        )}
      </Card>
      {manifest ? (
        <Card title="发布包文件">
          <Table
            rowKey="name"
            dataSource={manifest.files ?? []}
            pagination={false}
            columns={[
              { title: "文件", dataIndex: "name" },
              {
                title: "大小",
                dataIndex: "size",
                render: (value) => `${(value / 1024 / 1024).toFixed(2)} MB`,
              },
              { title: "校验", dataIndex: "checksum", ellipsis: true },
            ]}
          />
        </Card>
      ) : (
        <Empty description="发布包尚未生成" />
      )}
    </Space>
  );
}
