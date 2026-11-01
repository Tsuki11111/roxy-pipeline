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

const ACTIVE_STATUSES = new Set([
  "SCRIPTING",
  "STORYBOARDING",
  "VOICING",
  "ALIGNING",
  "RENDERING",
  "QC",
]);
const WAITING_LABELS: Record<string, string> = {
  SCRIPTING: "脚本生成已完成，等待进入下一步",
  STORYBOARDING: "分镜已生成，等待确认",
  VOICING: "配音已完成，等待对齐",
  ALIGNING: "对齐已完成，等待渲染",
  RENDERING: "渲染已完成，等待质检",
  QC: "质检已完成，等待发布",
};

export function episodeStatusMeta(
  status: EpisodeStatus,
  currentNode: string | null | undefined,
): { label: string; color: string } {
  const meta = statusMeta[status];
  if (ACTIVE_STATUSES.has(status) && !currentNode) {
    return { label: WAITING_LABELS[status] ?? meta.label, color: "gold" };
  }
  return meta;
}

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
