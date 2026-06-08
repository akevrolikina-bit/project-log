"use client";

import { useCallback, useState } from "react";
import { UploadZone } from "@/components/upload-zone";
import { WorklogTable } from "@/components/worklog-table";
import { CheckButton } from "@/components/check-button";
import { CheckResults } from "@/components/check-results";
import { Badge } from "@/components/ui/badge";
import { DownloadButton } from "@/components/download-button";
import {
  getWorklogs,
  getResults,
  type UploadResponse,
  type WorklogEntry,
  type CheckSummary,
} from "@/lib/api";

export default function Home() {
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [entries, setEntries] = useState<WorklogEntry[]>([]);
  const [summaries, setSummaries] = useState<CheckSummary[]>([]);
  const [isLoadingWorklogs, setIsLoadingWorklogs] = useState(false);
  const [isLoadingResults, setIsLoadingResults] = useState(false);

  const loadResults = useCallback(async (uploadId: number) => {
    setIsLoadingResults(true);
    try {
      const results = await getResults(uploadId);
      setSummaries(results);
    } catch {
      setSummaries([]);
    } finally {
      setIsLoadingResults(false);
    }
  }, []);

  const handleUploadComplete = useCallback(
    async (result: UploadResponse) => {
      setUpload(result);
      setSummaries([]);
      setIsLoadingWorklogs(true);
      try {
        const worklogs = await getWorklogs(result.id);
        setEntries(worklogs);
      } catch {
        setEntries([]);
      } finally {
        setIsLoadingWorklogs(false);
      }

      if (result.status === "checked") {
        await loadResults(result.id);
      }
    },
    [loadResults]
  );

  const handleCheckComplete = useCallback(
    (results: CheckSummary[]) => {
      setSummaries(results);
      if (upload) {
        setUpload({ ...upload, status: "checked" });
      }
    },
    [upload]
  );

  const showResults = summaries.length > 0 || isLoadingResults;

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
        <section className="mb-6 flex flex-wrap items-center gap-3">
          <Badge variant="secondary">{upload.filename}</Badge>
          <span className="text-xs text-muted-foreground">
            {upload.row_count} записей
          </span>
          <Badge variant="outline">
            {upload.status === "checked" ? "проверено" : "загружено"}
          </Badge>
          <CheckButton
            uploadId={upload.id}
            onCheckComplete={handleCheckComplete}
            disabled={entries.length === 0}
          />
          {upload.status === "checked" && (
            <DownloadButton uploadId={upload.id} />
          )}
        </section>
      )}

      <section className="mb-8">
        <WorklogTable entries={entries} isLoading={isLoadingWorklogs} />
      </section>

      {showResults && (
        <section>
          <CheckResults summaries={summaries} isLoading={isLoadingResults} />
        </section>
      )}
    </div>
  );
}
