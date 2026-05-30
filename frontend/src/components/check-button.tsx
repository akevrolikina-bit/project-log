"use client";

import { useState } from "react";
import { PlayCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { runChecks, getResults, type CheckSummary } from "@/lib/api";

interface CheckButtonProps {
  uploadId: number;
  onCheckComplete: (summaries: CheckSummary[]) => void;
  disabled?: boolean;
}

export function CheckButton({
  uploadId,
  onCheckComplete,
  disabled,
}: CheckButtonProps) {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setError(null);
    setIsRunning(true);
    try {
      await runChecks(uploadId);
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
