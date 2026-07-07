/** 枚举值 → 中文标签，以及 antd 标签配色。集中一处，页面复用。 */
import type {
  ApprovalStatus,
  CampaignStatus,
  DataSourceType,
  EmailStatus,
  EmailType,
  LeadStage,
  ReplyIntent,
} from "./api";

export const leadStageLabels: Record<LeadStage, string> = {
  new: "新线索",
  contacted: "已触达",
  replied: "已回复",
  interested: "意向",
  quote: "询盘",
  won: "成交",
  lost: "流失",
};

export const leadStageColors: Record<LeadStage, string> = {
  new: "default",
  contacted: "blue",
  replied: "cyan",
  interested: "gold",
  quote: "orange",
  won: "green",
  lost: "red",
};

export const emailStatusLabels: Record<EmailStatus, string> = {
  valid: "有效",
  catch_all: "全收（降权）",
  invalid: "无效",
  unknown: "未知",
};

export const emailStatusColors: Record<EmailStatus, string> = {
  valid: "green",
  catch_all: "gold",
  invalid: "red",
  unknown: "default",
};

export const emailTypeLabels: Record<EmailType, string> = {
  corporate: "企业",
  personal: "个人",
  unknown: "未知",
};

export const dataSourceLabels: Record<DataSourceType, string> = {
  search_engine: "搜索引擎",
  customs: "海关数据",
  maps: "谷歌地图",
  directory: "企业名录",
  tradeshow: "展会名录",
  b2b_inquiry: "B2B 询盘",
  social: "社媒主页",
  brand: "品牌反查",
};

export const campaignStatusLabels: Record<CampaignStatus, string> = {
  draft: "草稿",
  active: "进行中",
  paused: "已暂停",
  completed: "已完成",
};

export const campaignStatusColors: Record<CampaignStatus, string> = {
  draft: "default",
  active: "green",
  paused: "gold",
  completed: "blue",
};

export const approvalStatusLabels: Record<ApprovalStatus, string> = {
  pending: "待审",
  approved: "已通过",
  rejected: "已驳回",
  auto_approved: "自动通过",
};

export const replyIntentLabels: Record<ReplyIntent, string> = {
  interested: "感兴趣",
  meeting: "约会议",
  objection: "有异议",
  not_interested: "不感兴趣",
  referral: "转介绍",
  out_of_office: "自动回复",
  unsubscribe: "退订",
  wrong_person: "找错人",
  bounce: "退信",
  unknown: "未知",
};

/** 安全取标签：未知值原样返回，避免 undefined。 */
export function labelOf<T extends string>(
  map: Record<string, string>,
  value: T | string | null | undefined,
  fallback = "未知",
): string {
  if (!value) return fallback;
  return map[value] ?? value;
}

/** 显示联系人姓名。 */
export function contactName(
  first?: string | null,
  last?: string | null,
): string {
  const name = [first, last].filter(Boolean).join(" ").trim();
  return name || "—";
}
