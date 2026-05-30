"use client";

import { useCallback, useState } from "react";
import { UploadZone } from "@/components/upload-zone";
import { WorklogTable } from "@/components/worklog-table";
import { Badge } from "@/components/ui/badge";
import { getWorklogs, type UploadResponse, type WorklogEntry } from "@/lib/api";

export default function Home() {
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [entries, setEntries] = useState<WorklogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const handleUploadComplete = useCallback(async (result: UploadResponse) => {
    setUpload(result);
    setIsLoading(true);
    try {
      const worklogs = await getWorklogs(result.id);
      setEntries(worklogs);
    } catch {
      setEntries([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  return (
    <div className="mx-auto w-full max-w-[1100px] px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">TimeAudit</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Загрузите файл из Jira для проверки рабочего времени
        </p>
      </header>

      <section className="mb-8">
        <UploadZone onUploadComplete={handleUploadComplete} />
      </section>

      {upload && (
        <section className="mb-6 flex items-center gap-3">
          <Badge variant="secondary">{upload.filename}</Badge>
          <span className="text-xs text-muted-foreground">
            {upload.row_count} записей
          </span>
          <Badge variant="outline">{upload.status}</Badge>
        </section>
      )}

      <section>
        <WorklogTable entries={entries} isLoading={isLoading} />
      </section>
    </div>
  );
}
