// Dev UI (localhost:3000) talks to the npm backend on 8002 so it does not
// collide with a long-running packaged TimeAudit on 8001.
const API_BASE =
  process.env.NODE_ENV === "development" ? "http://127.0.0.1:8002" : "";

const NETWORK_ERROR_MESSAGE =
  "Не получилось связаться с сервером. Подождите пару секунд и нажмите проверку ещё раз.";

export function isNetworkError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const msg = err.message.toLowerCase();
  return (
    err.message === NETWORK_ERROR_MESSAGE ||
    msg === "failed to fetch" ||
    msg.includes("networkerror") ||
    msg.includes("load failed")
  );
}

async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (err) {
    if (err instanceof TypeError || isNetworkError(err)) {
      throw new Error(NETWORK_ERROR_MESSAGE);
    }
    throw err;
  }
}

export interface UploadResponse {
  id: number;
  filename: string;
  uploaded_at: string;
  row_count: number;
  status: string;
  error_message?: string | null;
}

export interface WorklogEntry {
  project: string;
  task_type: string;
  key: string;
  title: string;
  started: string;
  username: string;
  hours: number;
  comment: string;
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/uploads`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

export async function getUploads(): Promise<UploadResponse[]> {
  const res = await fetch(`${API_BASE}/api/uploads`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getWorklogs(
  uploadId: number,
  username?: string
): Promise<WorklogEntry[]> {
  const params = username
    ? `?username=${encodeURIComponent(username)}`
    : "";
  const res = await fetch(`${API_BASE}/api/uploads/${uploadId}/worklogs${params}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface CheckResult {
  id: number;
  upload_id: number;
  username: string;
  check_type: string;
  severity: string;
  message: string;
  details: string;
}

export interface CheckSummary {
  username: string;
  total_hours: number;
  expected_hours: number | null;
  status: "ok" | "warning" | "error";
  issues: CheckResult[];
}

export async function runChecks(uploadId: number): Promise<void> {
  const url = `${API_BASE}/api/uploads/${uploadId}/check`;
  let lastError: unknown;

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await apiFetch(url, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Check failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return;
    } catch (err) {
      lastError = err;
      if (!isNetworkError(err) || attempt === 2) throw err;
      await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
    }
  }

  throw lastError;
}

export async function getUploadStatus(
  uploadId: number
): Promise<UploadResponse> {
  const res = await apiFetch(`${API_BASE}/api/uploads/${uploadId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getResults(
  uploadId: number,
  username?: string
): Promise<CheckSummary[]> {
  const params = username
    ? `?username=${encodeURIComponent(username)}`
    : "";
  const res = await apiFetch(
    `${API_BASE}/api/uploads/${uploadId}/results${params}`
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function getReportUrl(uploadId: number): string {
  return `${API_BASE}/api/uploads/${uploadId}/report`;
}

// ---------------------------------------------------------------------------
// Invest allocation types
// ---------------------------------------------------------------------------

export interface InvestEmployee {
  username: string;
  total_hours: number;
  has_invest_tasks: boolean;
  selected: boolean;
}

export interface AutoEntry {
  username: string;
  task_key: string;
  title: string;
  hours: number;
  invest_project: string;
}

export interface BuhEntry {
  username: string;
  task_key: string;
  title: string;
  hours: number;
  buh_company: string | null;
  invest_project: string | null;
}

export interface ManualPercentEntry {
  username: string;
  task_key: string;
  title: string;
  hours: number;
  invest_project: string | null;
  percentage: number | null;
}

export interface ManualProjectEntry {
  username: string;
  task_key: string;
  title: string;
  hours: number;
  invest_project: string | null;
}

export interface KeywordEntry {
  username: string;
  task_key: string;
  title: string;
  hours: number;
  matched_project: string | null;
}

export interface PlanFteEntry {
  username: string;
  task_key: string;
  title: string;
  hours: number;
}

export interface FtePlanItem {
  username: string;
  invest_project: string;
  fte_value: number;
}

export interface PlanVsFactEntry {
  username: string;
  invest_project: string;
  plan_fte: number | null;
  plan_hours: number | null;
  fact_hours: number;
  fact_fte: number | null;
  delta_fte: number | null;
  delta_hours: number | null;
}

export interface ExpectedHoursEntry {
  username: string;
  expected_hours: number;
}

export interface SavedAllocation {
  username: string;
  task_key: string;
  invest_project: string;
  percentage: number;
  allocation_type: string;
}

export interface InvestData {
  auto_entries: AutoEntry[];
  buh_entries: BuhEntry[];
  manual_percent_entries: ManualPercentEntry[];
  manual_project_entries: ManualProjectEntry[];
  keyword_entries: KeywordEntry[];
  plan_fte_entries: PlanFteEntry[];
  fte_plans: FtePlanItem[];
  plan_vs_fact: PlanVsFactEntry[];
  expected_hours: ExpectedHoursEntry[];
  selected_employees: string[];
  saved_allocations: SavedAllocation[];
  invest_projects: string[];
}

export interface BuhCsvResult {
  total_keys: number;
  matched_keys: number;
  unmatched_keys: number;
}

export interface AllocationEntry {
  username: string;
  task_key: string;
  invest_project: string;
  percentage: number;
  allocation_type: string;
}

// ---------------------------------------------------------------------------
// Invest allocation API
// ---------------------------------------------------------------------------

export async function getInvestEmployees(
  uploadId: number
): Promise<InvestEmployee[]> {
  const res = await fetch(`${API_BASE}/api/uploads/${uploadId}/invest/employees`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function saveInvestEmployees(
  uploadId: number,
  usernames: string[]
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/uploads/${uploadId}/invest/employees`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usernames }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function uploadBuhCsv(
  uploadId: number,
  files: File[]
): Promise<BuhCsvResult> {
  const formData = new FormData();
  for (const f of files) {
    formData.append("files", f);
  }
  const res = await fetch(`${API_BASE}/api/uploads/${uploadId}/invest/buh-csv`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getInvestData(uploadId: number): Promise<InvestData> {
  const res = await fetch(`${API_BASE}/api/uploads/${uploadId}/invest`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function saveInvestAllocations(
  uploadId: number,
  allocations: AllocationEntry[],
  ftePlans: FtePlanItem[] = []
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/uploads/${uploadId}/invest`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ allocations, fte_plans: ftePlans }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}
