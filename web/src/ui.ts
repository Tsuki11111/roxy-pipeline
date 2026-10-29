import type { EpisodeStatus } from "./types";

export const statusMeta: Record<
  EpisodeStatus,
  { label: string; color: string }
> = {
  DRAFT: { label: "草稿", color: "default" },
  TOPIC_CONFIRMED: { label: "选题确认", color: "blue" },
  SCRIPTING: { label: "脚本生成中", color: "processing" },
  SCRIPT_REVIEW: { label: "脚本待确认", color: "gold" },
  STORYBOARDING: { label: "分镜中", color: "processing" },
  VOICING: { label: "配音中", color: "processing" },
  ALIGNING: { label: "对齐中", color: "processing" },
  RENDERING: { label: "渲染中", color: "processing" },
  QC: { label: "质检中", color: "orange" },
  READY: { label: "待发布", color: "success" },
  PUBLISHED: { label: "已发布", color: "purple" },
  CANCELLED: { label: "已取消", color: "default" },
};

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

export function formatDuration(ms?: number | null): string {
  if (!ms) return "—";
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}分${seconds}秒` : `${seconds}秒`;
}
