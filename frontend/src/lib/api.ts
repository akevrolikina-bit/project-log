export interface UploadResponse {
  id: number;
  filename: string;
  uploaded_at: string;
  row_count: number;
  status: string;
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

  const res = await fetch("/api/uploads", {
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
  const res = await fetch("/api/uploads");
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
  const res = await fetch(`/api/uploads/${uploadId}/worklogs${params}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
