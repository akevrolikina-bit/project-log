"use client";

import { useRef, useState } from "react";
import { PlayCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  runChecks,
  getResults,
  getUploadStatus,
  type CheckSummary,
} from "@/lib/api";

interface CheckButtonProps {
  uploadId: number;
  onCheckComplete: (summaries: CheckSummary[]) => void;
  disabled?: boolean;
}

const POLL_INTERVAL_MS = 3_000;
const POLL_TIMEOUT_MS = 5 * 60_000;

export function CheckButton({
  uploadId,
  onCheckComplete,
  disabled,
}: CheckButtonProps) {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef(false);

  const pollUntilDone = async (): Promise<void> => {
    const deadline = Date.now() + POLL_TIMEOUT_MS;

    while (Date.now() < deadline) {
      if (abortRef.current) return;
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      if (abortRef.current) return;

      const upload = await getUploadStatus(uploadId);
      if (upload.status === "checked") return;
      if (upload.status === "error") throw new Error("Проверка завершилась с ошибкой на сервере");
    }

    throw new Error("Превышено время ожидания проверки");
  };

  const handleRun = async () => {
    setError(null);
    setIsRunning(true);
    abortRef.current = false;
    try {
      await runChecks(uploadId);
      await pollUntilDone();
      const summaries = await getResults(uploadId);
      onCheckComplete(summaries);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Проверка не удалась");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <Button
        onClick={handleRun}
        disabled={disabled || isRunning}
        size="sm"
      >
        {isRunning ? (
          <Loader2 data-icon="inline-start" className="size-4 animate-spin" />
        ) : (
          <PlayCircle data-icon="inline-start" className="size-4" />
        )}
        {isRunning ? "Проверка..." : "Запустить проверку"}
      </Button>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
