"use client";

import { useCallback, useState } from "react";
import { UploadZone } from "@/components/upload-zone";
import { WorklogTable } from "@/components/worklog-table";
import { CheckButton } from "@/components/check-button";
import { CheckResults } from "@/components/check-results";
import { InvestPanel } from "@/components/invest-panel";
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
    <div className="mx-auto w-full max-w-[1600px] px-6 py-10 lg:px-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">TimeAudit</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Загрузите файл из Jira. Можно проверить время или сразу распределить
          часы по инвест-проектам.
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
          <DownloadButton uploadId={upload.id} />
        </section>
      )}

      <section className="mb-10">
        <WorklogTable
          entries={entries}
          isLoading={isLoadingWorklogs}
          defaultCollapsed={Boolean(upload)}
        />
      </section>

      {showResults && (
        <section className="mb-10">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            1 · Проверка времени
          </p>
          <CheckResults summaries={summaries} isLoading={isLoadingResults} />
        </section>
      )}

      {upload && (
        <section className="mb-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            {showResults
              ? "2 · Распределение по проектам"
              : "Распределение по проектам"}
          </p>
          <InvestPanel uploadId={upload.id} />
        </section>
      )}
    </div>
  );
}
