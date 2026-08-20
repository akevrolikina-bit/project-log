"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { CheckResult, CheckSummary } from "@/lib/api";

interface CheckResultsProps {
  summaries: CheckSummary[];
  isLoading?: boolean;
}

const STATUS_CONFIG = {
  ok: {
    label: "OK",
    badgeClass: "bg-[var(--success-light)] text-[var(--success)]",
    rowClass: "border-l-[3px] border-l-[var(--success)]",
  },
  warning: {
    label: "Внимание",
    badgeClass: "bg-[var(--warning-light)] text-[var(--warning)]",
    rowClass: "border-l-[3px] border-l-[var(--warning)]",
  },
  error: {
    label: "Ошибка",
    badgeClass: "bg-[var(--error-light)] text-[var(--error)]",
    rowClass: "border-l-[3px] border-l-[var(--error)]",
  },
} as const;

function checkTypeLabel(type: string): string {
  if (type === "permitted_task") return "Неразрешённая задача";
  if (type === "hours_mismatch") return "Расхождение часов";
  if (type === "comment_quality") return "Качество комментария";
  if (type === "comment_relevance") return "Соответствие комментария задаче";
  if (type === "time_limit") return "Превышение лимита времени";
  if (type === "general_rules") return "Общие правила списания";
  return type;
}

function severityLabel(severity: string): string {
  if (severity === "error") return "Ошибка";
  if (severity === "warning") return "Внимание";
  return severity;
}

function StatusBadge({ status }: { status: CheckSummary["status"] }) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-full px-2 text-xs font-medium",
        config.badgeClass
      )}
    >
      {config.label}
    </span>
  );
}

interface CommentDetail {
  key: string;
  hours: number;
  comment?: string;
  title?: string;
  severity?: string;
  reason?: string;
  verdict?: string;
  explanation?: string;
}

function IssueDetails({ issue }: { issue: CheckResult }) {
  if (
    issue.check_type !== "comment_quality" &&
    issue.check_type !== "comment_relevance" &&
    issue.check_type !== "general_rules"
  ) {
    return null;
  }

  let items: CommentDetail[];
  try {
    items = JSON.parse(issue.details);
  } catch {
    return null;
  }

  if (!Array.isArray(items) || items.length === 0) return null;

  return (
    <ul className="mt-2 space-y-1.5 border-t pt-2">
      {items.map((item, idx) => {
        const description =
          item.reason || item.explanation || "Нет описания";
        const verdictColor =
          (item.severity === "error" || item.verdict === "red")
            ? "text-[var(--error)]"
            : "text-[var(--warning)]";

        return (
          <li key={idx} className="flex flex-col gap-0.5 text-xs">
            <div className="flex items-baseline gap-2">
              <span className="font-mono font-medium">{item.key}</span>
              <span className="text-muted-foreground">
                {item.hours.toFixed(1)} ч
              </span>
              <span className={cn("font-medium", verdictColor)}>
                {description}
              </span>
            </div>
            {(item.comment || item.title) && (
              <span className="ml-4 text-muted-foreground italic">
                «{item.comment || item.title}»
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function EmployeeRow({ summary }: { summary: CheckSummary }) {
  const [expanded, setExpanded] = useState(false);
  const config = STATUS_CONFIG[summary.status];
  const diff =
    summary.expected_hours !== null
      ? summary.total_hours - summary.expected_hours
      : null;

  return (
    <>
      <TableRow
        className={cn("cursor-pointer hover:bg-muted/50", config.rowClass)}
        onClick={() => setExpanded((v) => !v)}
      >
        <TableCell className="w-8">
          {summary.issues.length > 0 ? (
            expanded ? (
              <ChevronDown className="size-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="size-4 text-muted-foreground" />
            )
          ) : null}
        </TableCell>
        <TableCell className="font-medium">{summary.username}</TableCell>
        <TableCell className="font-mono text-right">
          {summary.total_hours.toFixed(2)}
        </TableCell>
        <TableCell className="font-mono text-right">
          {summary.expected_hours !== null
            ? summary.expected_hours.toFixed(2)
            : "—"}
        </TableCell>
        <TableCell className="font-mono text-right">
          {diff !== null ? (
            <span
              className={cn(
                diff === 0 && "text-[var(--success)]",
                diff !== 0 && diff > 0 && "text-[var(--warning)]",
                diff !== 0 && diff < 0 && "text-[var(--error)]"
              )}
            >
              {diff > 0 ? "+" : ""}
              {diff.toFixed(2)}
            </span>
          ) : (
            "—"
          )}
        </TableCell>
        <TableCell>
          <StatusBadge status={summary.status} />
        </TableCell>
        <TableCell className="text-right text-xs text-muted-foreground">
          {summary.issues.length > 0
            ? `${summary.issues.length} замеч.`
            : "—"}
        </TableCell>
      </TableRow>

      {expanded && summary.issues.length > 0 && (
        <TableRow className="bg-muted/30 hover:bg-muted/30">
          <TableCell colSpan={7} className="p-0">
            <ul className="space-y-2 px-6 py-3">
              {summary.issues.map((issue) => (
                <li
                  key={issue.id}
                  className="rounded-md border bg-background px-3 py-2 text-sm"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={cn(
                        "inline-flex h-5 items-center rounded-full px-2 text-xs font-medium",
                        issue.severity === "error"
                          ? STATUS_CONFIG.error.badgeClass
                          : STATUS_CONFIG.warning.badgeClass
                      )}
                    >
                      {severityLabel(issue.severity)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {checkTypeLabel(issue.check_type)}
                    </span>
                  </div>
                  <p className="mt-1">{issue.message}</p>
                  <IssueDetails issue={issue} />
                </li>
              ))}
            </ul>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

export function CheckResults({ summaries, isLoading }: CheckResultsProps) {
  if (isLoading) {
    return (
      <Card className="border-l-4 border-l-[var(--brand)]">
        <CardHeader className="-mt-4 bg-[var(--brand-light)] pt-4">
          <CardTitle>Результаты проверки</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (summaries.length === 0) return null;

  const okCount = summaries.filter((s) => s.status === "ok").length;
  const warningCount = summaries.filter((s) => s.status === "warning").length;
  const errorCount = summaries.filter((s) => s.status === "error").length;

  return (
    <Card className="border-l-4 border-l-[var(--brand)]">
      <CardHeader className="-mt-4 bg-[var(--brand-light)] pt-4">
        <CardTitle>Результаты проверки</CardTitle>
        <CardDescription>
          Сотрудников: {summaries.length} ·{" "}
          <span className="text-[var(--success)]">{okCount} OK</span>
          {warningCount > 0 && (
            <>
              {" "}
              ·{" "}
              <span className="text-[var(--warning)]">
                {warningCount} с замечаниями
              </span>
            </>
          )}
          {errorCount > 0 && (
            <>
              {" "}
              ·{" "}
              <span className="text-[var(--error)]">
                {errorCount} с ошибками
              </span>
            </>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8" />
                <TableHead>Сотрудник</TableHead>
                <TableHead className="text-right">Факт, ч</TableHead>
                <TableHead className="text-right">Норма, ч</TableHead>
                <TableHead className="text-right">Разница</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead className="text-right">Замечания</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {summaries.map((summary) => (
                <EmployeeRow key={summary.username} summary={summary} />
              ))}
            </TableBody>
          </Table>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Нажмите на строку сотрудника, чтобы развернуть список замечаний.
        </p>
      </CardContent>
    </Card>
  );
}
