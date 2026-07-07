/**
 * 类型化 API 客户端。
 *
 * - 读取 process.env.NEXT_PUBLIC_API_BASE_URL（默认 http://localhost:8000）。
 * - 封装 get/post，统一错误处理（后端错误体形如 {"error":{"code","message"}}）。
 * - 定义与后端 pydantic schema 对应的 TypeScript 类型。
 * - 对「尚未实现」的接口（返回 404/405/501）提供优雅降级判断，页面据此显示占位。
 */

// ---------------------------------------------------------------------------
// 基础配置
// ---------------------------------------------------------------------------

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

// ---------------------------------------------------------------------------
// 枚举（与 services/api/app/domain/enums.py 保持一致）
// ---------------------------------------------------------------------------

export type EmailStatus = "valid" | "catch_all" | "invalid" | "unknown";

export type EmailType = "corporate" | "personal" | "unknown";

export type DataSourceType =
  | "search_engine"
  | "customs"
  | "maps"
  | "directory"
  | "tradeshow"
  | "b2b_inquiry"
  | "social"
  | "brand";

export type LeadStage =
  | "new"
  | "contacted"
  | "replied"
  | "interested"
  | "quote"
  | "won"
  | "lost";

export type ReplyIntent =
  | "interested"
  | "meeting"
  | "objection"
  | "not_interested"
  | "referral"
  | "out_of_office"
  | "unsubscribe"
  | "wrong_person"
  | "bounce"
  | "unknown";

export type CampaignStatus = "draft" | "active" | "paused" | "completed";

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "auto_approved";

// ---------------------------------------------------------------------------
// 领域类型（对应后端 schema）
// ---------------------------------------------------------------------------

/** 来源留痕条目（Company.provenance / Contact.provenance 里的一条）。 */
export interface ProvenanceEntry {
  source?: string;
  ref?: string | null;
  at?: string;
  [key: string]: unknown;
}

/** 联系人（对应 leads.schemas.ContactOut）。 */
export interface Contact {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  title?: string | null;
  email?: string | null;
  email_status: EmailStatus;
  email_type: EmailType;
  linkedin_url?: string | null;
  phone?: string | null;
  enrichment_provider?: string | null;
  is_primary: boolean;
}

/** 公司/线索（对应 leads.schemas.CompanyOut）。 */
export interface Company {
  id: string;
  name: string;
  domain?: string | null;
  website?: string | null;
  country?: string | null;
  industry?: string | null;
  description?: string | null;
  source_type: string;
  stage: LeadStage;
  score: number;
  score_reasons: string[];
  provenance: ProvenanceEntry[];
  contacts: Contact[];
}

/** 一键找客户请求（对应 leads.schemas.DiscoverRequest）。 */
export interface DiscoverRequest {
  keywords: string[];
  hs_code?: string | null;
  countries: string[];
  industry?: string | null;
  limit: number;
  enrich: boolean;
}

/** 一键找客户返回（对应 leads.schemas.DiscoverResult）。 */
export interface DiscoverResult {
  discovered: number;
  new_companies: number;
  merged_duplicates: number;
  contacts_found: number;
  sendable_contacts: number;
  companies: Company[];
}

/** 通用分页容器（对应 core.pagination.Page[T]）。 */
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

/** 邮箱合规检查结果（对应 compliance.schemas.EmailCheckResult）。 */
export interface EmailCheckResult {
  email: string;
  email_type: EmailType;
  suppressed: boolean;
  sendable: boolean;
  reason?: string | null;
}

/** 健康检查返回（GET /health）。 */
export interface HealthStatus {
  status: string;
  env: string;
  adapter_mode: string;
  version: string;
}

// ---------------------------------------------------------------------------
// 以下模块由其它工程师并行开发。类型与其真实 schema 对齐；若某模块未挂载/宕机，
// 调用会抛 ApiError（isNotImplemented / isNetworkError），页面据此优雅降级。
// ---------------------------------------------------------------------------

/** 线索阶段占比（analytics.schemas.StageRatioOut）。 */
export interface StageRatio {
  stage: LeadStage;
  count: number;
  ratio: number;
}

/** 数据看板概览（GET /api/analytics/summary → analytics.schemas.SummaryOut）。 */
export interface AnalyticsSummary {
  total_companies: number;
  total_contacts: number;
  sendable_contacts: number;
  stages: StageRatio[];
}

/** 活动目标（campaigns.schemas.CampaignTargetOut）。 */
export interface CampaignTarget {
  id: string;
  company_id: string;
  contact_id?: string | null;
  to_email?: string | null;
  state: string;
}

/** 营销活动（GET/POST /api/campaigns → campaigns.schemas.CampaignOut）。 */
export interface Campaign {
  id: string;
  name: string;
  icp_config: Record<string, unknown>;
  sequence_def: Array<Record<string, unknown>>;
  status: CampaignStatus;
  created_by?: string | null;
  targets: CampaignTarget[];
}

/** 新建活动入参（campaigns.schemas.CampaignCreate，序列缺省由后端套 3-7-7 四步）。 */
export interface CampaignCreate {
  name: string;
  icp_config?: Record<string, unknown>;
  created_by?: string;
}

/** 人审草稿（GET /api/agent/drafts → agent.schemas.DraftOut）。 */
export interface AgentDraft {
  id: string;
  campaign_id?: string | null;
  lead_id?: string | null;
  subject: string;
  body: string;
  language: string;
  /** 个性化证据：正文引用了哪些真实信号（可解释性关键）。 */
  evidence: string[];
  spam_score: number;
  status: ApprovalStatus;
  reviewed_by?: string | null;
  reject_reason?: string | null;
}

// ---------------------------------------------------------------------------
// 错误类型
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }

  /** 网络层错误（后端不可达）。 */
  get isNetworkError(): boolean {
    return this.status === 0;
  }

  /** 接口尚未实现 / 未挂载：用于优雅降级判断。 */
  get isNotImplemented(): boolean {
    return this.status === 404 || this.status === 405 || this.status === 501;
  }
}

// ---------------------------------------------------------------------------
// 请求内核
// ---------------------------------------------------------------------------

type QueryValue = string | number | boolean | null | undefined;
type QueryParams = Record<string, QueryValue | QueryValue[]>;

interface RequestOptions {
  params?: QueryParams;
  body?: unknown;
  signal?: AbortSignal;
}

function buildUrl(path: string, params?: QueryParams): string {
  const base = path.startsWith("http")
    ? path
    : `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  if (!params) return base;

  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const v of value) {
        if (v !== undefined && v !== null) usp.append(key, String(v));
      }
    } else {
      usp.append(key, String(value));
    }
  }
  const qs = usp.toString();
  return qs ? `${base}?${qs}` : base;
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function request<T>(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const url = buildUrl(path, options.params);

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
      cache: "no-store",
    });
  } catch (err) {
    throw new ApiError(
      0,
      "network_error",
      `无法连接后端（${API_BASE_URL}）：${(err as Error).message ?? err}`,
    );
  }

  const text = await res.text();
  const data = text ? safeJsonParse(text) : null;

  if (!res.ok) {
    const errObj =
      data && typeof data === "object" && "error" in data
        ? (data as { error?: { code?: string; message?: string } }).error
        : undefined;
    throw new ApiError(
      res.status,
      errObj?.code ?? "http_error",
      errObj?.message ?? `请求失败（HTTP ${res.status}）`,
    );
  }

  return data as T;
}

// ---------------------------------------------------------------------------
// 对外 API：get / post 及各业务方法
// ---------------------------------------------------------------------------

export const http = {
  get: <T>(path: string, params?: QueryParams, signal?: AbortSignal) =>
    request<T>("GET", path, { params, signal }),
  post: <T>(path: string, body?: unknown, signal?: AbortSignal) =>
    request<T>("POST", path, { body, signal }),
};

export const api = {
  // ---- 系统 ----
  health: () => http.get<HealthStatus>("/health"),

  // ---- 线索（已实现）----
  discoverLeads: (body: DiscoverRequest) =>
    http.post<DiscoverResult>("/api/leads/discover", body),
  listLeads: (page = 1, size = 20) =>
    http.get<Page<Company>>("/api/leads", { page, size }),
  getLead: (id: string) => http.get<Company>(`/api/leads/${id}`),

  // ---- 合规（已实现）----
  checkEmail: (email: string) =>
    http.get<EmailCheckResult>("/api/compliance/check", { email }),

  // ---- 数据看板（模块 I，可降级）----
  analyticsSummary: () => http.get<AnalyticsSummary>("/api/analytics/summary"),

  // ---- 活动（模块 E/I，可降级）----
  listCampaigns: (page = 1, size = 50) =>
    http.get<Page<Campaign>>("/api/campaigns", { page, size }),
  createCampaign: (body: CampaignCreate) =>
    http.post<Campaign>("/api/campaigns", body),

  // ---- 人审草稿（模块 G4，可降级）----
  // approve/reject 需带 reviewer（后端 ApproveRequest/RejectRequest 必填）。
  listDrafts: () => http.get<AgentDraft[]>("/api/agent/drafts"),
  approveDraft: (id: string, reviewer: string) =>
    http.post<AgentDraft>(`/api/agent/drafts/${id}/approve`, { reviewer }),
  rejectDraft: (id: string, reviewer: string, reason: string) =>
    http.post<AgentDraft>(`/api/agent/drafts/${id}/reject`, { reviewer, reason }),
};
