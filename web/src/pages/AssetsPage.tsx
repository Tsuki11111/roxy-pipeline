import { useEffect, useMemo, useState } from "react";
import {
  App,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Radio,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { PlusOutlined, ReloadOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { api } from "../api";
import type { Asset, AssetGenerateResponse, Episode } from "../types";
import { formatDate } from "../ui";

const ASSET_TYPES = ["background", "prop", "icon", "cover"];

export default function AssetsPage() {
  const { message } = App.useApp();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>();
  const [statusFilter, setStatusFilter] = useState<string>();
  const [generateOpen, setGenerateOpen] = useState(false);
  const [mode, setMode] = useState<"text" | "episode">("episode");
  const [result, setResult] = useState<AssetGenerateResponse | null>(null);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const [assetData, episodeData] = await Promise.all([
        api.listAssets({ type: typeFilter, status: statusFilter }),
        api.listEpisodes(),
      ]);
      setAssets(assetData);
      setEpisodes(episodeData);
    } catch (error) {
      message.error(String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [typeFilter, statusFilter]);

  const approve = async (asset: Asset) => {
    try {
      await api.approveAsset(asset.id);
      message.success("已批准");
      await load();
    } catch (error) {
      message.error(String(error));
    }
  };

  const reject = async (asset: Asset) => {
    try {
      await api.rejectAsset(asset.id);
      message.success("已拒绝");
      await load();
    } catch (error) {
      message.error(String(error));
    }
  };

  const check = async (asset: Asset) => {
    try {
      const verdict = await api.checkAsset(asset.id);
      message[verdict.passed ? "success" : "warning"](
        verdict.passed ? "图片检查通过" : `发现 ${verdict.issues.length} 个问题`,
      );
      await load();
    } catch (error) {
      message.error(String(error));
    }
  };

  const generate = async () => {
    const values = await form.validateFields();
    try {
      const payload = {
        asset_type: values.asset_type,
        count: values.count,
        auto_approve: values.auto_approve,
        check: values.check,
        force: values.force,
      };
      const response =
        mode === "episode"
          ? await api.generateAssetsForEpisode(values.episode_id, payload)
          : await api.generateAssetsFromText({ ...payload, text: values.text });
      setResult(response);
      message.success(`已处理 ${response.items.length} 个素材`);
      setGenerateOpen(false);
      await load();
    } catch (error) {
      message.error(String(error));
    }
  };

  const approvedCount = useMemo(
    () => assets.filter((item) => item.status === "APPROVED").length,
    [assets],
  );

  return (
    <Space direction="vertical" size={18} className="page-stack">
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>资产库</Typography.Title>
          <Typography.Paragraph type="secondary">
            背景、道具、图标和封面；入库自动镜像到 MinIO，按 reuse_key 复用。
          </Typography.Paragraph>
        </div>
        <Space>
          <Tag color="green">已批准 {approvedCount}</Tag>
          <Select
            allowClear
            placeholder="类型"
            style={{ width: 130 }}
            value={typeFilter}
            onChange={setTypeFilter}
            options={ASSET_TYPES.map((value) => ({ value }))}
          />
          <Select
            allowClear
            placeholder="状态"
            style={{ width: 130 }}
            value={statusFilter}
            onChange={setStatusFilter}
            options={["APPROVED", "CANDIDATE", "REJECTED"].map((value) => ({ value }))}
          />
          <Button icon={<ReloadOutlined />} onClick={load}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              form.resetFields();
              form.setFieldsValue({ mode: "episode", count: 1, check: true });
              setMode("episode");
              setGenerateOpen(true);
            }}
          >
            生成素材
          </Button>
        </Space>
      </div>

      <Card>
        <Table
          loading={loading}
          rowKey="id"
          dataSource={assets}
          pagination={{ pageSize: 20 }}
          columns={[
            {
              title: "名称",
              dataIndex: "name",
              render: (name, row) => (
                <Space direction="vertical" size={0}>
                  <Typography.Text strong>{name}</Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {row.type} · {row.width}×{row.height}
                  </Typography.Text>
                </Space>
              ),
            },
            {
              title: "reuse_key",
              dataIndex: "reuse_key",
              ellipsis: true,
            },
            {
              title: "状态",
              dataIndex: "status",
              width: 110,
              render: (status) => (
                <Tag color={status === "APPROVED" ? "green" : status === "REJECTED" ? "red" : "gold"}>
                  {status}
                </Tag>
              ),
            },
            {
              title: "MinIO",
              dataIndex: "meta",
              width: 90,
              render: (meta) =>
                meta?.minio?.uri ? (
                  <Tag color="blue">已上传</Tag>
                ) : meta?.minio_error ? (
                  <Tag color="red">失败</Tag>
                ) : (
                  <Tag>未上传</Tag>
                ),
            },
            {
              title: "来源",
              dataIndex: "source",
              width: 110,
            },
            {
              title: "更新时间",
              dataIndex: "created_at",
              width: 170,
              render: (value) => formatDate(value),
            },
            {
              title: "操作",
              width: 240,
              render: (_, row) => (
                <Space wrap>
                  <Button size="small" onClick={() => check(row)}>
                    检查
                  </Button>
                  {row.status !== "APPROVED" && (
                    <Button size="small" type="primary" onClick={() => approve(row)}>
                      批准
                    </Button>
                  )}
                  {row.status !== "REJECTED" && (
                    <Button size="small" danger onClick={() => reject(row)}>
                      拒绝
                    </Button>
                  )}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="生成演示素材"
        open={generateOpen}
        onCancel={() => setGenerateOpen(false)}
        onOk={generate}
        okText="开始生成"
        width={640}
      >
        <Radio.Group
          value={mode}
          onChange={(event) => setMode(event.target.value)}
          style={{ marginBottom: 16 }}
          options={[
            { label: "按视频期文稿", value: "episode" },
            { label: "自由文本", value: "text" },
          ]}
          optionType="button"
        />
        <Form form={form} layout="vertical">
          {mode === "episode" ? (
            <Form.Item name="episode_id" label="视频期" rules={[{ required: true }]}>
              <Select
                showSearch
                optionFilterProp="label"
                options={episodes.map((item) => ({
                  value: item.id,
                  label: `${item.title}（${item.status}）`,
                }))}
              />
            </Form.Item>
          ) : (
            <Form.Item name="text" label="素材描述" rules={[{ required: true }]}>
              <Input.TextArea rows={4} placeholder="例如：解释太阳光穿过三棱镜后的色散" />
            </Form.Item>
          )}
          <Space size={16} wrap>
            <Form.Item name="asset_type" label="类型">
              <Select
                allowClear
                placeholder="自动判断"
                style={{ width: 150 }}
                options={ASSET_TYPES.map((value) => ({ value }))}
              />
            </Form.Item>
            <Form.Item name="count" label="数量" initialValue={1}>
              <InputNumber min={1} max={3} />
            </Form.Item>
            <Form.Item name="check" label="图片检查" valuePropName="checked" initialValue>
              <Checkbox>DeepSeek 检查</Checkbox>
            </Form.Item>
            <Form.Item name="auto_approve" label="自动批准" valuePropName="checked">
              <Checkbox>检查通过后直接批准</Checkbox>
            </Form.Item>
            <Form.Item name="force" label="强制重生成" valuePropName="checked">
              <Checkbox>忽略已有资产</Checkbox>
            </Form.Item>
          </Space>
        </Form>
        <AlertHint />
      </Modal>

      <Modal
        title="生成结果"
        open={!!result}
        onCancel={() => setResult(null)}
        footer={<Button onClick={() => setResult(null)}>关闭</Button>}
        width={720}
      >
        <Table
          rowKey={(row) => row.asset.id}
          pagination={false}
          dataSource={result?.items ?? []}
          columns={[
            { title: "状态", dataIndex: "status", width: 130 },
            { title: "名称", render: (_, row) => row.asset.name },
            { title: "reuse_key", render: (_, row) => row.asset.reuse_key },
            {
              title: "结果",
              render: (_, row) => (
                <Tag color={row.asset.status === "APPROVED" ? "green" : "gold"}>
                  {row.asset.status}
                </Tag>
              ),
            },
          ]}
        />
      </Modal>
    </Space>
  );
}

function AlertHint() {
  return (
    <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
      只生成无文字的背景、道具、图标或封面；角色立绘和含文字卡片不会走图片生成。
      新图默认 CANDIDATE，需要在资产库批准后才会被复用。
    </Typography.Paragraph>
  );
}
