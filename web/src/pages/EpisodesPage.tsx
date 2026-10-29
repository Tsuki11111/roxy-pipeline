import { useEffect, useState } from "react";
import {
  App,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
} from "antd";
import {
  FileTextOutlined,
  ReloadOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Episode, Series } from "../types";
import { formatDate, statusMeta } from "../ui";

const RUNNING_STATUSES = [
  "SCRIPTING",
  "STORYBOARDING",
  "VOICING",
  "ALIGNING",
  "RENDERING",
  "QC",
];

export default function EpisodesPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [series, setSeries] = useState<Series[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>();
  const [seriesOpen, setSeriesOpen] = useState(false);
  const [articleOpen, setArticleOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [seriesForm] = Form.useForm();
  const [articleForm] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const [episodeData, seriesData] = await Promise.all([
        api.listEpisodes(statusFilter),
        api.listSeries(),
      ]);
      setEpisodes(episodeData);
      setSeries(seriesData);
    } catch (error) {
      message.error(String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [statusFilter]);

  const createSeries = async () => {
    const values = await seriesForm.validateFields();
    const labels = String(values.section_labels ?? "")
      .split(/[,，]/)
      .map((item: string) => item.trim())
      .filter(Boolean);
    await api.createSeries({
      name: values.name,
      section_labels: labels,
      character_pack_id: values.character_pack_id || "roxy",
      watermark: values.watermark || "",
    });
    message.success("系列已创建");
    setSeriesOpen(false);
    seriesForm.resetFields();
    await load();
  };

  const importArticle = async () => {
    const values = await articleForm.validateFields();
    setImporting(true);
    let createdId: string | null = null;
    try {
      const created = await api.createEpisode({
        series_id: values.series_id,
        title: values.title,
        topic: values.topic || values.title,
        target_duration_s: values.target_duration_s,
      });
      createdId = created.id;
      const result = await api.importArticle(created.id, {
        article: values.article,
        optimize: values.optimize,
        instructions: values.instructions || "",
      });
      message.success(
        `文稿已导入：${result.lines.length} 句，校验${result.validation.valid ? "通过" : "未通过"}`,
      );
      setArticleOpen(false);
      articleForm.resetFields();
      navigate(`/episodes/${created.id}`);
    } catch (error) {
      message.error(String(error));
      if (createdId) navigate(`/episodes/${createdId}`);
    } finally {
      setImporting(false);
    }
  };

  return (
    <Space direction="vertical" size={18} className="page-stack">
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>视频期</Typography.Title>
          <Typography.Paragraph type="secondary">
            管理每一期的脚本、分镜、配音、渲染和发布状态。
          </Typography.Paragraph>
        </div>
        <Space>
          <Select
            allowClear
            placeholder="按状态筛选"
            style={{ width: 160 }}
            value={statusFilter}
            onChange={setStatusFilter}
            options={Object.entries(statusMeta).map(([value, meta]) => ({
              value,
              label: meta.label,
            }))}
          />
          <Button icon={<ReloadOutlined />} onClick={load}>
            刷新
          </Button>
          <Button onClick={() => setSeriesOpen(true)}>新建系列</Button>
          <Button
            icon={<FileTextOutlined />}
            onClick={() => {
              articleForm.resetFields();
              articleForm.setFieldsValue({ target_duration_s: 600, optimize: true });
              setArticleOpen(true);
            }}
            disabled={series.length === 0}
          >
            导入文稿
          </Button>
        </Space>
      </div>

      <Card>
        <Table
          loading={loading}
          rowKey="id"
          dataSource={episodes}
          columns={[
            {
              title: "标题",
              dataIndex: "title",
              render: (title, row) => (
                <a onClick={() => navigate(`/episodes/${row.id}`)}>{title}</a>
              ),
            },
            {
              title: "选题",
              dataIndex: "topic",
              ellipsis: true,
            },
            {
              title: "状态",
              dataIndex: "status",
              render: (status) => (
                <Tag color={statusMeta[status as keyof typeof statusMeta].color}>
                  {statusMeta[status as keyof typeof statusMeta].label}
                </Tag>
              ),
            },
            {
              title: "健康",
              dataIndex: "health",
              render: (health) => (
                <Tag color={health === "OK" ? "green" : health === "WARNING" ? "gold" : "red"}>
                  {health}
                </Tag>
              ),
            },
            {
              title: "目标时长",
              dataIndex: "target_duration_s",
              render: (value) => `${value}s`,
            },
            {
              title: "更新时间",
              dataIndex: "updated_at",
              render: (value) => formatDate(value),
            },
            {
              title: "操作",
              render: (_, row) => (
                <Space>
                  <Button size="small" onClick={() => navigate(`/episodes/${row.id}`)}>
                    打开
                  </Button>
                  {RUNNING_STATUSES.includes(row.status) ? (
                    <Popconfirm
                      title="取消生成？"
                      description="当前步骤结束后停止，已生成文件保留。"
                      okText="取消生成"
                      okButtonProps={{ danger: true }}
                      onConfirm={async () => {
                        try {
                          await api.action(row.id, "cancel");
                          message.success("已取消");
                          await load();
                        } catch (error) {
                          message.error(String(error));
                        }
                      }}
                    >
                      <Button size="small" danger>
                        取消
                      </Button>
                    </Popconfirm>
                  ) : (
                    <Popconfirm
                      title="删除这个视频期？"
                      description="删除数据库记录，不删除 output 文件。"
                      okText="删除"
                      okButtonProps={{ danger: true }}
                      onConfirm={async () => {
                        try {
                          await api.deleteEpisode(row.id);
                          message.success("已删除");
                          await load();
                        } catch (error) {
                          message.error(String(error));
                        }
                      }}
                    >
                      <Button size="small" danger>
                        删除
                      </Button>
                    </Popconfirm>
                  )}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="新建系列"
        open={seriesOpen}
        onCancel={() => setSeriesOpen(false)}
        onOk={createSeries}
        okText="创建"
      >
        <Form form={seriesForm} layout="vertical">
          <Form.Item name="name" label="系列名" rules={[{ required: true }]}>
            <Input placeholder="例如：洛琪希的 AI 科普" />
          </Form.Item>
          <Form.Item
            name="section_labels"
            label="章节（逗号分隔）"
            rules={[{ required: true }]}
          >
            <Input placeholder="问题, 概念, 解决, 结尾" />
          </Form.Item>
          <Form.Item name="character_pack_id" label="角色包" initialValue="roxy">
            <Input />
          </Form.Item>
          <Form.Item name="watermark" label="水印">
            <Input placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="导入文稿生成视频期"
        open={articleOpen}
        onCancel={() => setArticleOpen(false)}
        onOk={importArticle}
        okText={importing ? "AI 理解中..." : "导入并生成脚本"}
        confirmLoading={importing}
        width={820}
        maskClosable={!importing}
      >
        <Form form={articleForm} layout="vertical">
          <Space size={16} style={{ width: "100%" }} align="start">
            <Form.Item
              name="series_id"
              label="系列"
              rules={[{ required: true }]}
              style={{ minWidth: 240 }}
            >
              <Select
                options={series.map((item) => ({ value: item.id, label: item.name }))}
              />
            </Form.Item>
            <Form.Item name="title" label="视频标题" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Input placeholder="例如：为什么天空是蓝色的" />
            </Form.Item>
          </Space>
          <Form.Item name="topic" label="主题/副标题">
            <Input />
          </Form.Item>
          <Form.Item name="target_duration_s" label="目标时长（秒）" initialValue={600}>
            <InputNumber min={30} max={3600} style={{ width: 180 }} />
          </Form.Item>
          <Form.Item
            name="article"
            label="文章正文"
            rules={[{ required: true, message: "请粘贴或上传文章" }]}
            extra="支持最多 30000 字；粘贴或上传 .txt/.md。"
          >
            <Input.TextArea rows={12} maxLength={30000} showCount placeholder="粘贴完整文章..." />
          </Form.Item>
          <Space wrap>
            <Upload
              accept=".txt,.md,text/plain,text/markdown"
              showUploadList={false}
              beforeUpload={(file) => {
                const reader = new FileReader();
                reader.onload = () => {
                  articleForm.setFieldValue("article", String(reader.result ?? ""));
                };
                reader.readAsText(file);
                return false;
              }}
            >
              <Button icon={<UploadOutlined />}>上传 .txt / .md</Button>
            </Upload>
            <Form.Item name="optimize" valuePropName="checked" initialValue style={{ marginBottom: 0 }}>
              <Checkbox>导入后自动润色</Checkbox>
            </Form.Item>
          </Space>
          <Form.Item name="instructions" label="额外要求" style={{ marginTop: 16 }}>
            <Input placeholder="例如：多举生活例子，语气轻松一点" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
