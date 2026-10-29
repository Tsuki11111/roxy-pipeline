import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Col,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  ArrowRightOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  SoundOutlined,
} from "@ant-design/icons";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Asset, Episode } from "../types";
import { formatDate, statusMeta } from "../ui";

export default function DashboardPage() {
  const [health, setHealth] = useState<{
    status: string;
    env: string;
    database: string;
  } | null>(null);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([api.health(), api.listEpisodes(), api.listAssets()])
      .then(([healthData, episodeData, assetData]) => {
        setHealth(healthData);
        setEpisodes(episodeData);
        setAssets(assetData);
      })
      .finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => {
    const ready = episodes.filter((item) =>
      ["READY", "PUBLISHED"].includes(item.status),
    ).length;
    const active = episodes.filter((item) =>
      ["SCRIPTING", "STORYBOARDING", "VOICING", "ALIGNING", "RENDERING", "QC"].includes(
        item.status,
      ),
    ).length;
    return {
      ready,
      active,
      total: episodes.length,
      assets: assets.filter((item) => item.status === "APPROVED").length,
    };
  }, [episodes, assets]);

  return (
    <Space direction="vertical" size={20} className="page-stack">
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>总览</Typography.Title>
          <Typography.Paragraph type="secondary">
            从选题到成片的本地 AI 视频流水线。
          </Typography.Paragraph>
        </div>
        <Space>
          <Tag color={health?.database === "ok" ? "green" : "red"}>
            数据库 {health?.database ?? "..."}
          </Tag>
          <Tag color="blue">环境 {health?.env ?? "..."}</Tag>
        </Space>
      </div>

      <Row gutter={16}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stat-card stat-violet">
            <Statistic
              title="全部视频期"
              value={stats.total}
              prefix={<PlayCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stat-card stat-amber">
            <Statistic
              title="制作中"
              value={stats.active}
              prefix={<SoundOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stat-card stat-green">
            <Statistic
              title="可发布 / 已发布"
              value={stats.ready}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stat-card stat-blue">
            <Statistic title="已批准资产" value={stats.assets} />
          </Card>
        </Col>
      </Row>

      <Card
        title="最近视频期"
        extra={
          <Link to="/episodes">
            查看全部 <ArrowRightOutlined />
          </Link>
        }
      >
        <Table
          loading={loading}
          rowKey="id"
          pagination={false}
          dataSource={episodes.slice(0, 6)}
          columns={[
            {
              title: "标题",
              dataIndex: "title",
              render: (title, row) => (
                <Link to={`/episodes/${row.id}`}>{title}</Link>
              ),
            },
            {
              title: "状态",
              dataIndex: "status",
              render: (status) => {
                const meta = statusMeta[status as keyof typeof statusMeta];
                return <Tag color={meta.color}>{meta.label}</Tag>;
              },
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
              title: "更新时间",
              dataIndex: "updated_at",
              render: (value) => formatDate(value),
            },
            {
              title: "",
              render: (_, row) => (
                <Button size="small" onClick={() => navigate(`/episodes/${row.id}`)}>
                  打开
                </Button>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
}
