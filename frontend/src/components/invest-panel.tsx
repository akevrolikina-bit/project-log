"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Upload,
  ChevronDown,
  ChevronRight,
  Check,
  FileSpreadsheet,
  Plus,
  X,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  getInvestEmployees,
  saveInvestEmployees,
  uploadBuhCsv,
  getInvestData,
  saveInvestAllocations,
  type InvestEmployee,
  type InvestData,
  type AllocationEntry,
  type BuhCsvResult,
  type AutoEntry,
  type ManualPercentEntry,
  type ManualProjectEntry,
  type BuhEntry,
  type KeywordEntry,
  type PlanFteEntry,
  type FtePlanItem,
  type PlanVsFactEntry,
} from "@/lib/api";

interface InvestPanelProps {
  uploadId: number;
}

type Step = 1 | 2 | 3;

type AllocSplit = {
  id: string;
  project: string;
  percentage: number | null;
};

function newSplitId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function emptySplit(): AllocSplit {
  return { id: newSplitId(), project: "", percentage: null };
}

function sortInvestProjects(projects: string[]): string[] {
  const unique = [...new Set(projects.filter(Boolean))];
  const rest = unique
    .filter((p) => p !== "MENA")
    .sort((a, b) => a.localeCompare(b, "en"));
  return unique.includes("MENA") ? ["MENA", ...rest] : rest;
}

function splitsToAllocations(
  username: string,
  taskKey: string,
  splits: AllocSplit[],
  allocationType: string
): AllocationEntry[] {
  const active = splits.filter((s) => s.project);
  if (active.length === 1 && active[0].percentage == null) {
    return [
      {
        username,
        task_key: taskKey,
        invest_project: active[0].project,
        percentage: 100,
        allocation_type: allocationType,
      },
    ];
  }
  return active
    .filter((s) => s.percentage != null && s.percentage > 0)
    .map((s) => ({
      username,
      task_key: taskKey,
      invest_project: s.project,
      percentage: s.percentage as number,
      allocation_type: allocationType,
    }));
}

function splitHours(
  hours: number,
  splits: AllocSplit[]
): { project: string; hours: number }[] {
  const active = splits.filter((s) => s.project);
  if (active.length === 1 && active[0].percentage == null) {
    return [{ project: active[0].project, hours }];
  }
  return active
    .filter((s) => s.percentage != null && s.percentage > 0)
    .map((s) => ({
      project: s.project,
      hours: (hours * (s.percentage as number)) / 100,
    }));
}

function splitsPercentSum(splits: AllocSplit[]): number {
  return splits.reduce((sum, s) => sum + (s.percentage ?? 0), 0);
}

function fmtMetric(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toFixed(2);
}

function sumKnown(values: Array<number | null | undefined>): number | null {
  const nums = values.filter((v): v is number => v != null);
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0);
}

type ProjectPlanGroup = {
  project: string;
  people: PlanVsFactEntry[];
  planFte: number | null;
  planHours: number | null;
  factHours: number;
  factFte: number | null;
  deltaFte: number | null;
  deltaHours: number | null;
};

function groupPlanVsFactByProject(
  rows: PlanVsFactEntry[]
): ProjectPlanGroup[] {
  const byProject: Record<string, PlanVsFactEntry[]> = {};
  for (const row of rows) {
    (byProject[row.invest_project] ??= []).push(row);
  }
  return sortInvestProjects(Object.keys(byProject)).map((project) => {
    const people = [...byProject[project]].sort((a, b) =>
      a.username.localeCompare(b.username, "ru")
    );
    const planFte = sumKnown(people.map((p) => p.plan_fte));
    const planHours = sumKnown(people.map((p) => p.plan_hours));
    const factHours = people.reduce((sum, p) => sum + p.fact_hours, 0);
    const factFte = sumKnown(people.map((p) => p.fact_fte));
    return {
      project,
      people,
      planFte,
      planHours,
      factHours,
      factFte,
      deltaFte:
        factFte != null && planFte != null ? factFte - planFte : null,
      deltaHours: planHours != null ? factHours - planHours : null,
    };
  });
}

export function InvestPanel({ uploadId }: InvestPanelProps) {
  const [step, setStep] = useState<Step>(1);
  const [employees, setEmployees] = useState<InvestEmployee[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [csvResult, setCsvResult] = useState<BuhCsvResult | null>(null);
  const [isUploadingCsv, setIsUploadingCsv] = useState(false);
  const [csvDragging, setCsvDragging] = useState(false);
  const [investData, setInvestData] = useState<InvestData | null>(null);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [splitsMap, setSplitsMap] = useState<Record<string, AllocSplit[]>>(
    {}
  );
  const [fteValues, setFteValues] = useState<Record<string, number | null>>({});

  const csvInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setIsLoading(true);
    getInvestEmployees(uploadId)
      .then((emps) => {
        setEmployees(emps);
        const prev = new Set(
          emps.filter((e) => e.selected).map((e) => e.username)
        );
        setSelected(prev);
        if (prev.size > 0) {
          setStep(2);
          loadInvestData();
        }
      })
      .catch(() => setError("Не удалось загрузить список сотрудников"))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploadId]);

  const loadInvestData = useCallback(async () => {
    setIsLoadingData(true);
    try {
      const data = await getInvestData(uploadId);
      setInvestData(data);
      const nextSplits: Record<string, AllocSplit[]> = {};
      const addSplit = (
        key: string,
        project: string | null,
        percentage: number | null
      ) => {
        if (!nextSplits[key]) nextSplits[key] = [];
        nextSplits[key].push({
          id: newSplitId(),
          project: project ?? "",
          percentage,
        });
      };
      for (const a of data.saved_allocations) {
        const k = `${a.username}::${a.task_key}`;
        addSplit(k, a.invest_project, a.percentage);
      }
      for (const e of data.manual_percent_entries) {
        const k = `${e.username}::${e.task_key}`;
        if (!nextSplits[k]) {
          nextSplits[k] = [
            {
              id: newSplitId(),
              project: e.invest_project ?? data.invest_projects[0] ?? "",
              percentage: e.percentage,
            },
          ];
        }
      }
      for (const e of data.manual_project_entries) {
        const k = `${e.username}::${e.task_key}`;
        if (!nextSplits[k]) {
          nextSplits[k] = [
            {
              id: newSplitId(),
              project: e.invest_project ?? "",
              percentage: e.invest_project ? 100 : null,
            },
          ];
        }
      }
      for (const e of data.keyword_entries) {
        const k = `${e.username}::${e.task_key}`;
        if (!nextSplits[k] && !e.matched_project) {
          nextSplits[k] = [emptySplit()];
        }
      }
      const fv: Record<string, number | null> = {};
      for (const fp of data.fte_plans) {
        fv[`${fp.username}::${fp.invest_project}`] = fp.fte_value;
      }
      setSplitsMap(nextSplits);
      setFteValues(fv);
    } catch {
      setError("Не удалось загрузить данные инвест-распределения");
    } finally {
      setIsLoadingData(false);
    }
  }, [uploadId]);

  const toggleEmployee = (username: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(username)) next.delete(username);
      else next.add(username);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === employees.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(employees.map((e) => e.username)));
    }
  };

  const handleCsvFiles = async (fileList: FileList) => {
    setIsUploadingCsv(true);
    setError(null);
    try {
      const files = Array.from(fileList);
      const result = await uploadBuhCsv(uploadId, files);
      setCsvResult(result);
    } catch {
      setError("Ошибка загрузки CSV файлов");
    } finally {
      setIsUploadingCsv(false);
    }
  };

  const handleCsvDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setCsvDragging(false);
    if (e.dataTransfer.files.length > 0) handleCsvFiles(e.dataTransfer.files);
  };

  const handleCsvInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleCsvFiles(e.target.files);
      e.target.value = "";
    }
  };

  const handleNextStep = async () => {
    setError(null);
    try {
      await saveInvestEmployees(uploadId, Array.from(selected));
      await loadInvestData();
      setStep(2);
    } catch {
      setError("Не удалось сохранить выбор сотрудников");
    }
  };

  const handleSave = async () => {
    if (!investData) return;
    const overLimit = Object.values(splitsMap).some(
      (splits) => splitsPercentSum(splits) > 100.001
    );
    if (overLimit) {
      setError("Сумма процентов по одной задаче не может быть больше 100");
      return;
    }
    setIsSaving(true);
    setSaveSuccess(false);
    setError(null);

    const allocations: AllocationEntry[] = [];

    for (const e of investData.manual_percent_entries) {
      const k = `${e.username}::${e.task_key}`;
      allocations.push(
        ...splitsToAllocations(
          e.username,
          e.task_key,
          splitsMap[k] ?? [],
          "manual_percent"
        )
      );
    }

    for (const e of investData.manual_project_entries) {
      const k = `${e.username}::${e.task_key}`;
      allocations.push(
        ...splitsToAllocations(
          e.username,
          e.task_key,
          splitsMap[k] ?? [],
          "manual_project"
        )
      );
    }

    for (const e of investData.keyword_entries) {
      if (e.matched_project) continue;
      const k = `${e.username}::${e.task_key}`;
      allocations.push(
        ...splitsToAllocations(
          e.username,
          e.task_key,
          splitsMap[k] ?? [],
          "keyword"
        )
      );
    }

    const ftePlans: FtePlanItem[] = [];
    for (const [key, value] of Object.entries(fteValues)) {
      if (value != null && value > 0) {
        const sep = key.indexOf("::");
        if (sep === -1) continue;
        const username = key.slice(0, sep);
        const project = key.slice(sep + 2);
        ftePlans.push({
          username,
          invest_project: project,
          fte_value: value,
        });
      }
    }

    try {
      await saveInvestAllocations(uploadId, allocations, ftePlans);
      setSaveSuccess(true);
      setStep(3);
      await loadInvestData();
    } catch {
      setError("Не удалось сохранить распределение");
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <Card className="border-l-4 border-l-[var(--invest)]">
        <CardHeader className="-mt-4 bg-[var(--invest-light)] pt-4">
          <CardTitle>Распределение по проектам</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-l-4 border-l-[var(--invest)]">
      <CardHeader className="-mt-4 bg-[var(--invest-light)] pt-4">
        <div className="flex items-center justify-between">
          <CardTitle>Распределение по проектам</CardTitle>
          <div className="flex items-center gap-2">
            <StepIndicator current={step} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {error && (
          <div className="rounded-lg border border-[var(--error)] bg-[var(--error-light)] px-4 py-2 text-sm text-[var(--error)]">
            {error}
          </div>
        )}

        {step === 1 && (
          <StepOne
            employees={employees}
            selected={selected}
            toggleEmployee={toggleEmployee}
            toggleAll={toggleAll}
            csvResult={csvResult}
            isUploadingCsv={isUploadingCsv}
            csvDragging={csvDragging}
            setCsvDragging={setCsvDragging}
            handleCsvDrop={handleCsvDrop}
            handleCsvInputChange={handleCsvInputChange}
            csvInputRef={csvInputRef}
            onNext={handleNextStep}
          />
        )}

        {step === 2 && (
          <StepTwo
            investData={investData}
            isLoadingData={isLoadingData}
            splitsMap={splitsMap}
            setSplitsMap={setSplitsMap}
            fteValues={fteValues}
            setFteValues={setFteValues}
            onSave={handleSave}
            isSaving={isSaving}
            onBack={() => setStep(1)}
          />
        )}

        {step === 3 && (
          <StepThree
            investData={investData}
            splitsMap={splitsMap}
            fteValues={fteValues}
            saveSuccess={saveSuccess}
            onBack={() => setStep(2)}
          />
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Step indicator
// ---------------------------------------------------------------------------

function StepIndicator({ current }: { current: Step }) {
  const steps = [
    { n: 1 as Step, label: "Выбор" },
    { n: 2 as Step, label: "Распределение" },
    { n: 3 as Step, label: "Итоги" },
  ];

  return (
    <div className="flex items-center gap-1">
      {steps.map((s, idx) => (
        <div key={s.n} className="flex items-center gap-1">
          <span
            className={cn(
              "flex size-6 items-center justify-center rounded-full text-xs font-medium",
              s.n === current
                ? "bg-[var(--brand)] text-white"
                : s.n < current
                  ? "bg-[var(--success-light)] text-[var(--success)]"
                  : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
            )}
          >
            {s.n < current ? <Check className="size-3" /> : s.n}
          </span>
          <span
            className={cn(
              "text-xs",
              s.n === current
                ? "font-medium text-[var(--text-primary)]"
                : "text-[var(--text-muted)]"
            )}
          >
            {s.label}
          </span>
          {idx < steps.length - 1 && (
            <span className="mx-1 text-[var(--text-muted)]">·</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 1 — Employee selection & CSV upload
// ---------------------------------------------------------------------------

interface StepOneProps {
  employees: InvestEmployee[];
  selected: Set<string>;
  toggleEmployee: (u: string) => void;
  toggleAll: () => void;
  csvResult: BuhCsvResult | null;
  isUploadingCsv: boolean;
  csvDragging: boolean;
  setCsvDragging: (v: boolean) => void;
  handleCsvDrop: (e: React.DragEvent) => void;
  handleCsvInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  csvInputRef: React.RefObject<HTMLInputElement | null>;
  onNext: () => void;
}

function StepOne({
  employees,
  selected,
  toggleEmployee,
  toggleAll,
  csvResult,
  isUploadingCsv,
  csvDragging,
  setCsvDragging,
  handleCsvDrop,
  handleCsvInputChange,
  csvInputRef,
  onNext,
}: StepOneProps) {
  return (
    <>
      {/* CSV upload zone */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium">
          Загрузка CSV файлов BUH Company
        </h3>
        <p className="text-xs text-muted-foreground">
          Загрузите CSV-выгрузки из GBS JIRA для автоматического определения
          инвест-проекта по BUH Company.
        </p>

        <div
          onDrop={handleCsvDrop}
          onDragOver={(e) => {
            e.preventDefault();
            setCsvDragging(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            setCsvDragging(false);
          }}
          className={cn(
            "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 transition-colors cursor-pointer",
            csvDragging
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-muted-foreground/50",
            isUploadingCsv && "pointer-events-none opacity-60"
          )}
          onClick={() => csvInputRef.current?.click()}
        >
          <div className="rounded-full bg-muted p-2">
            <FileSpreadsheet className="size-4 text-muted-foreground" />
          </div>
          <p className="text-xs font-medium">
            {isUploadingCsv
              ? "Загрузка..."
              : "Перетащите CSV файлы сюда или нажмите"}
          </p>
          <input
            ref={csvInputRef}
            type="file"
            accept=".csv"
            multiple
            className="sr-only"
            onChange={handleCsvInputChange}
            disabled={isUploadingCsv}
          />
        </div>

        {csvResult && (
          <div className="rounded-lg border bg-[var(--success-light)] px-4 py-2 text-sm text-[var(--success)]">
            Загружено ключей: {csvResult.total_keys} · Определено:{" "}
            {csvResult.matched_keys} · Не определено: {csvResult.unmatched_keys}
          </div>
        )}
      </div>

      {/* Employee list */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Выбор сотрудников</h3>
          <Button variant="ghost" size="xs" onClick={toggleAll}>
            {selected.size === employees.length
              ? "Снять все"
              : "Выбрать всех"}
          </Button>
        </div>
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>Сотрудник</TableHead>
                <TableHead className="text-right">Часы</TableHead>
                <TableHead className="text-center">Инвест-задачи</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {employees.map((emp) => (
                <TableRow
                  key={emp.username}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => toggleEmployee(emp.username)}
                >
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selected.has(emp.username)}
                      onChange={() => toggleEmployee(emp.username)}
                      className="size-4 rounded border-[var(--border)] accent-[var(--brand)]"
                    />
                  </TableCell>
                  <TableCell className="font-medium">{emp.username}</TableCell>
                  <TableCell className="font-mono text-right">
                    {emp.total_hours.toFixed(2)}
                  </TableCell>
                  <TableCell className="text-center">
                    {emp.has_invest_tasks ? (
                      <span className="inline-flex h-5 items-center rounded-full bg-[var(--brand-light)] px-2 text-xs font-medium text-[var(--brand)]">
                        Да
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      <div className="flex justify-end">
        <Button
          onClick={onNext}
          disabled={selected.size === 0}
        >
          Далее
        </Button>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Step 2 — Manual allocations
// ---------------------------------------------------------------------------

interface StepTwoProps {
  investData: InvestData | null;
  isLoadingData: boolean;
  splitsMap: Record<string, AllocSplit[]>;
  setSplitsMap: React.Dispatch<
    React.SetStateAction<Record<string, AllocSplit[]>>
  >;
  fteValues: Record<string, number | null>;
  setFteValues: React.Dispatch<
    React.SetStateAction<Record<string, number | null>>
  >;
  onSave: () => void;
  isSaving: boolean;
  onBack: () => void;
}

function StepTwo({
  investData,
  isLoadingData,
  splitsMap,
  setSplitsMap,
  fteValues,
  setFteValues,
  onSave,
  isSaving,
  onBack,
}: StepTwoProps) {
  if (isLoadingData || !investData) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  const usernames = new Set<string>(investData.selected_employees);
  investData.auto_entries.forEach((e) => usernames.add(e.username));
  investData.buh_entries.forEach((e) => usernames.add(e.username));
  investData.manual_percent_entries.forEach((e) => usernames.add(e.username));
  investData.manual_project_entries.forEach((e) => usernames.add(e.username));
  investData.keyword_entries.forEach((e) => usernames.add(e.username));
  investData.plan_fte_entries.forEach((e) => usernames.add(e.username));

  const sortedUsers = Array.from(usernames).sort();

  const overLimit = Object.values(splitsMap).some(
    (splits) => splitsPercentSum(splits) > 100.001
  );

  return (
    <>
      {sortedUsers.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Для выбранных сотрудников нет инвест-задач.
        </p>
      ) : (
        sortedUsers.map((username) => (
          <EmployeeAllocCard
            key={username}
            username={username}
            investData={investData}
            splitsMap={splitsMap}
            setSplitsMap={setSplitsMap}
            fteValues={fteValues}
            setFteValues={setFteValues}
          />
        ))
      )}

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          Назад
        </Button>
        <Button onClick={onSave} disabled={isSaving || overLimit}>
          {isSaving ? "Сохранение..." : "Сохранить"}
        </Button>
      </div>
      {overLimit && (
        <p className="text-right text-xs text-[var(--error)]">
          Сумма процентов по одной задаче не может быть больше 100
        </p>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Employee allocation card (collapsible)
// ---------------------------------------------------------------------------

interface EmployeeAllocCardProps {
  username: string;
  investData: InvestData;
  splitsMap: Record<string, AllocSplit[]>;
  setSplitsMap: React.Dispatch<
    React.SetStateAction<Record<string, AllocSplit[]>>
  >;
  fteValues: Record<string, number | null>;
  setFteValues: React.Dispatch<
    React.SetStateAction<Record<string, number | null>>
  >;
}

function EmployeeAllocCard({
  username,
  investData,
  splitsMap,
  setSplitsMap,
  fteValues,
  setFteValues,
}: EmployeeAllocCardProps) {
  const [expanded, setExpanded] = useState(true);

  const autoEntries = investData.auto_entries.filter(
    (e) => e.username === username
  );
  const buhEntries = investData.buh_entries.filter(
    (e) => e.username === username
  );
  const manualPctEntries = investData.manual_percent_entries.filter(
    (e) => e.username === username
  );
  const manualProjEntries = investData.manual_project_entries.filter(
    (e) => e.username === username
  );
  const keywordEntries = investData.keyword_entries.filter(
    (e) => e.username === username
  );
  const planFteEntries = investData.plan_fte_entries.filter(
    (e) => e.username === username
  );

  const autoHours = autoEntries.reduce((s, e) => s + e.hours, 0);
  const buhHours = buhEntries.reduce((s, e) => s + e.hours, 0);

  return (
    <div className="rounded-lg border">
      <button
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-muted/50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground" />
          )}
          <span className="font-medium">{username}</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {autoHours > 0 && (
            <span>
              Авто:{" "}
              <span className="font-mono">{autoHours.toFixed(2)} ч</span>
            </span>
          )}
          {buhHours > 0 && (
            <span>
              BUH:{" "}
              <span className="font-mono">{buhHours.toFixed(2)} ч</span>
            </span>
          )}
        </div>
      </button>

      {expanded && (
        <div className="space-y-4 border-t px-4 py-4">
          {/* FTE plan for every selected employee */}
          <EmployeeFtePlanSection
            username={username}
            investProjects={sortInvestProjects(investData.invest_projects)}
            fteValues={fteValues}
            setFteValues={setFteValues}
          />

          {/* Auto entries summary */}
          {autoEntries.length > 0 && (
            <AutoSection entries={autoEntries} />
          )}

          {/* BUH company entries summary */}
          {buhEntries.length > 0 && (
            <BuhSection entries={buhEntries} />
          )}

          {/* Manual percent entries */}
          {manualPctEntries.length > 0 && (
            <ManualPercentSection
              entries={manualPctEntries}
              investProjects={sortInvestProjects(investData.invest_projects)}
              splitsMap={splitsMap}
              setSplitsMap={setSplitsMap}
            />
          )}

          {/* Manual project entries */}
          {manualProjEntries.length > 0 && (
            <ManualProjectSection
              entries={manualProjEntries}
              investProjects={sortInvestProjects(investData.invest_projects)}
              splitsMap={splitsMap}
              setSplitsMap={setSplitsMap}
            />
          )}

          {/* Keyword-based entries */}
          {keywordEntries.length > 0 && (
            <KeywordSection
              entries={keywordEntries}
              investProjects={sortInvestProjects(investData.invest_projects)}
              splitsMap={splitsMap}
              setSplitsMap={setSplitsMap}
            />
          )}

          {/* Plan FTE task preview (GENERAL / GBTUTORIAL only) */}
          {planFteEntries.length > 0 && (
            <PlanFteSection
              username={username}
              entries={planFteEntries}
              investProjects={sortInvestProjects(investData.invest_projects)}
              fteValues={fteValues}
            />
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Auto section (read-only)
// ---------------------------------------------------------------------------

function AutoSection({ entries }: { entries: AutoEntry[] }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Автоматическое распределение (100%)
      </h4>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ключ</TableHead>
              <TableHead>Задача</TableHead>
              <TableHead className="text-right">Часы</TableHead>
              <TableHead>Проект</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((e) => (
              <TableRow key={e.task_key}>
                <TableCell className="font-mono text-xs">
                  {e.task_key}
                </TableCell>
                <TableCell className="max-w-[28rem] whitespace-normal break-words text-sm">
                  {e.title}
                </TableCell>
                <TableCell className="font-mono text-right">
                  {e.hours.toFixed(2)}
                </TableCell>
                <TableCell>
                  <span className="inline-flex h-5 items-center rounded-full bg-[var(--success-light)] px-2 text-xs font-medium text-[var(--success)]">
                    {e.invest_project}
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// BUH company section (read-only)
// ---------------------------------------------------------------------------

function BuhSection({ entries }: { entries: BuhEntry[] }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        По BUH Company (из CSV)
      </h4>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ключ</TableHead>
              <TableHead>Задача</TableHead>
              <TableHead className="text-right">Часы</TableHead>
              <TableHead>BUH Company</TableHead>
              <TableHead>Проект</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((e) => (
              <TableRow key={e.task_key}>
                <TableCell className="font-mono text-xs">
                  {e.task_key}
                </TableCell>
                <TableCell className="max-w-[28rem] whitespace-normal break-words text-sm">
                  {e.title}
                </TableCell>
                <TableCell className="font-mono text-right">
                  {e.hours.toFixed(2)}
                </TableCell>
                <TableCell className="text-xs">
                  {e.buh_company || "—"}
                </TableCell>
                <TableCell>
                  {e.invest_project ? (
                    <span className="inline-flex h-5 items-center rounded-full bg-[var(--success-light)] px-2 text-xs font-medium text-[var(--success)]">
                      {e.invest_project}
                    </span>
                  ) : (
                    <span className="inline-flex h-5 items-center rounded-full bg-[var(--warning-light)] px-2 text-xs font-medium text-[var(--warning)]">
                      Не определено
                    </span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Manual percent section (editable)
// ---------------------------------------------------------------------------

interface SplitsEditorProps {
  splits: AllocSplit[];
  hours: number;
  investProjects: string[];
  onChange: (next: AllocSplit[]) => void;
}

function SplitsEditor({
  splits,
  hours,
  investProjects,
  onChange,
}: SplitsEditorProps) {
  const rows = splits.length > 0 ? splits : [emptySplit()];
  const used = new Set(rows.map((s) => s.project).filter(Boolean));
  const sum = splitsPercentSum(rows);
  const over = sum > 100.001;
  const canAdd = investProjects.some((p) => !used.has(p));

  const updateRow = (id: string, patch: Partial<AllocSplit>) => {
    onChange(rows.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  };

  return (
    <div className="space-y-1.5">
      {rows.map((split) => {
        const investHours =
          split.percentage != null ? (hours * split.percentage) / 100 : null;
        const options = investProjects.filter(
          (p) => p === split.project || !used.has(p)
        );
        return (
          <div key={split.id} className="flex items-center gap-1.5">
            <select
              value={split.project}
              onChange={(ev) =>
                updateRow(split.id, { project: ev.target.value })
              }
              className="h-7 min-w-[7rem] flex-1 rounded-lg border border-input bg-transparent px-2 text-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <option value="">—</option>
              {options.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <Input
              type="number"
              min={0}
              max={100}
              value={split.percentage ?? ""}
              onChange={(ev) => {
                const val = ev.target.value ? Number(ev.target.value) : null;
                updateRow(split.id, { percentage: val });
              }}
              className="h-7 w-16 text-right font-mono text-xs"
            />
            <span className="w-4 text-xs text-muted-foreground">%</span>
            <span className="w-16 text-right font-mono text-xs text-muted-foreground">
              {investHours != null ? `${investHours.toFixed(2)} ч` : "—"}
            </span>
            {rows.length > 1 && (
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                onClick={() =>
                  onChange(rows.filter((s) => s.id !== split.id))
                }
                aria-label="Удалить проект"
              >
                <X />
              </Button>
            )}
          </div>
        );
      })}
      {canAdd && (
        <Button
          type="button"
          variant="ghost"
          size="xs"
          onClick={() => onChange([...rows, emptySplit()])}
        >
          <Plus />
          Добавить проект
        </Button>
      )}
      {(rows.length > 1 || over) && (
        <p
          className={cn(
            "text-xs",
            over ? "text-[var(--error)]" : "text-muted-foreground"
          )}
        >
          Сумма: {sum}%
          {over ? " — нельзя больше 100%" : ""}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Manual percent section (editable)
// ---------------------------------------------------------------------------

interface ManualPercentSectionProps {
  entries: ManualPercentEntry[];
  investProjects: string[];
  splitsMap: Record<string, AllocSplit[]>;
  setSplitsMap: React.Dispatch<
    React.SetStateAction<Record<string, AllocSplit[]>>
  >;
}

function ManualPercentSection({
  entries,
  investProjects,
  splitsMap,
  setSplitsMap,
}: ManualPercentSectionProps) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Ручное распределение (процент)
      </h4>
      <p className="mb-2 text-xs text-muted-foreground">
        Можно указать несколько инвест-проектов. Сумма процентов не больше
        100.
      </p>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ключ</TableHead>
              <TableHead>Задача</TableHead>
              <TableHead className="text-right">Часы</TableHead>
              <TableHead>Распределение</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((e) => {
              const k = `${e.username}::${e.task_key}`;
              const splits = splitsMap[k] ?? [emptySplit()];

              return (
                <TableRow key={k}>
                  <TableCell className="align-top font-mono text-xs">
                    {e.task_key}
                  </TableCell>
                  <TableCell className="align-top max-w-[22rem] whitespace-normal break-words text-sm">
                    {e.title}
                  </TableCell>
                  <TableCell className="align-top font-mono text-right">
                    {e.hours.toFixed(2)}
                  </TableCell>
                  <TableCell className="align-top">
                    <SplitsEditor
                      splits={splits}
                      hours={e.hours}
                      investProjects={investProjects}
                      onChange={(next) =>
                        setSplitsMap((prev) => ({ ...prev, [k]: next }))
                      }
                    />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-employee FTE plan (editable)
// ---------------------------------------------------------------------------

interface EmployeeFtePlanSectionProps {
  username: string;
  investProjects: string[];
  fteValues: Record<string, number | null>;
  setFteValues: React.Dispatch<
    React.SetStateAction<Record<string, number | null>>
  >;
}

function EmployeeFtePlanSection({
  username,
  investProjects,
  fteValues,
  setFteValues,
}: EmployeeFtePlanSectionProps) {
  const totalFte = investProjects.reduce((sum, p) => {
    const v = fteValues[`${username}::${p}`];
    return sum + (v != null && v > 0 ? v : 0);
  }, 0);

  return (
    <div className="rounded-lg border bg-muted/20 p-3">
      <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        План FTE — {username}
      </h4>
      <p className="mb-2 text-xs text-muted-foreground">
        Целевая загрузка по инвест-проектам. 0,2 FTE означает, что 20% часов
        GENERAL / GBTUTORIAL относятся на этот проект. Также используется для
        сравнения плана с фактом в отчёте.
      </p>
      <div className="flex flex-wrap gap-4">
        {investProjects.map((p) => {
          const key = `${username}::${p}`;
          return (
            <div key={key} className="flex items-center gap-2">
              <label className="text-xs text-muted-foreground">{p}</label>
              <Input
                type="number"
                min={0}
                step={0.01}
                value={fteValues[key] ?? ""}
                onChange={(ev) => {
                  const val = ev.target.value ? Number(ev.target.value) : null;
                  setFteValues((prev) => ({ ...prev, [key]: val }));
                }}
                className="h-7 w-24 text-right font-mono text-xs"
              />
            </div>
          );
        })}
      </div>
      {totalFte > 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          Сумма FTE:{" "}
          <span className="font-mono">{totalFte.toFixed(2)}</span>
        </p>
      )}
    </div>
  );
}

function getFteByProject(
  username: string,
  investProjects: string[],
  fteValues: Record<string, number | null>
): Record<string, number> {
  const result: Record<string, number> = {};
  for (const project of investProjects) {
    const value = fteValues[`${username}::${project}`];
    if (value != null && value > 0) {
      result[project] = value;
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Manual project section (editable)
// ---------------------------------------------------------------------------

interface ManualProjectSectionProps {
  entries: ManualProjectEntry[];
  investProjects: string[];
  splitsMap: Record<string, AllocSplit[]>;
  setSplitsMap: React.Dispatch<
    React.SetStateAction<Record<string, AllocSplit[]>>
  >;
}

function ManualProjectSection({
  entries,
  investProjects,
  splitsMap,
  setSplitsMap,
}: ManualProjectSectionProps) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Ручное назначение проекта
      </h4>
      <p className="mb-2 text-xs text-muted-foreground">
        Можно разделить часы на несколько инвест-проектов. Если проект один
        и процент не указан — все часы идут туда.
      </p>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ключ</TableHead>
              <TableHead>Задача</TableHead>
              <TableHead className="text-right">Часы</TableHead>
              <TableHead>Распределение</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((e) => {
              const k = `${e.username}::${e.task_key}`;
              const splits = splitsMap[k] ?? [emptySplit()];

              return (
                <TableRow key={k}>
                  <TableCell className="align-top font-mono text-xs">
                    {e.task_key}
                  </TableCell>
                  <TableCell className="align-top max-w-[22rem] whitespace-normal break-words text-sm">
                    {e.title}
                  </TableCell>
                  <TableCell className="align-top font-mono text-right">
                    {e.hours.toFixed(2)}
                  </TableCell>
                  <TableCell className="align-top">
                    <SplitsEditor
                      splits={splits}
                      hours={e.hours}
                      investProjects={investProjects}
                      onChange={(next) =>
                        setSplitsMap((prev) => ({ ...prev, [k]: next }))
                      }
                    />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Keyword section (auto-match + manual override)
// ---------------------------------------------------------------------------

interface KeywordSectionProps {
  entries: KeywordEntry[];
  investProjects: string[];
  splitsMap: Record<string, AllocSplit[]>;
  setSplitsMap: React.Dispatch<
    React.SetStateAction<Record<string, AllocSplit[]>>
  >;
}

function KeywordSection({
  entries,
  investProjects,
  splitsMap,
  setSplitsMap,
}: KeywordSectionProps) {
  const sortedEntries = [...entries].sort((a, b) => {
    const aMatched = Boolean(a.matched_project);
    const bMatched = Boolean(b.matched_project);
    if (aMatched === bMatched) return 0;
    return aMatched ? -1 : 1;
  });

  return (
    <div>
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        По ключевым словам в названии задачи
      </h4>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ключ</TableHead>
              <TableHead>Задача</TableHead>
              <TableHead className="text-right">Часы</TableHead>
              <TableHead>Распределение</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedEntries.map((e) => {
              const k = `${e.username}::${e.task_key}`;
              const autoMatched = e.matched_project;
              const splits = splitsMap[k] ?? [emptySplit()];

              return (
                <TableRow
                  key={k}
                  className={autoMatched ? "bg-emerald-50/50 dark:bg-emerald-950/20" : undefined}
                >
                  <TableCell className="align-top font-mono text-xs">
                    {e.task_key}
                  </TableCell>
                  <TableCell className="align-top max-w-[22rem] whitespace-normal break-words text-sm">
                    {e.title}
                  </TableCell>
                  <TableCell className="align-top font-mono text-right">
                    {e.hours.toFixed(2)}
                  </TableCell>
                  <TableCell className="align-top">
                    {autoMatched ? (
                      <span className="text-xs font-medium">{autoMatched}</span>
                    ) : (
                      <SplitsEditor
                        splits={splits}
                        hours={e.hours}
                        investProjects={investProjects}
                        onChange={(next) =>
                          setSplitsMap((prev) => ({ ...prev, [k]: next }))
                        }
                      />
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Plan FTE section (read-only preview)
// ---------------------------------------------------------------------------

interface PlanFteSectionProps {
  username: string;
  entries: PlanFteEntry[];
  investProjects: string[];
  fteValues: Record<string, number | null>;
}

function PlanFteSection({
  username,
  entries,
  investProjects,
  fteValues,
}: PlanFteSectionProps) {
  const fteByProject = getFteByProject(username, investProjects, fteValues);
  const hasFte = Object.keys(fteByProject).length > 0;

  return (
    <div>
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Распределение по плану FTE
      </h4>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ключ</TableHead>
              <TableHead>Задача</TableHead>
              <TableHead className="text-right">Часы</TableHead>
              <TableHead className="text-right">Инвест-часы</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((e) => (
                <TableRow key={`${e.username}::${e.task_key}`}>
                  <TableCell className="font-mono text-xs">
                    {e.task_key}
                  </TableCell>
                  <TableCell className="max-w-[28rem] whitespace-normal break-words text-sm">
                  {e.title}
                </TableCell>
                  <TableCell className="font-mono text-right">
                    {e.hours.toFixed(2)}
                  </TableCell>
                  <TableCell className="font-mono text-right text-xs">
                    {hasFte ? (
                      <div className="space-y-0.5">
                        {Object.entries(fteByProject).map(([proj, fte]) => (
                          <div key={proj}>
                            {proj}: {(e.hours * fte).toFixed(2)} ч
                          </div>
                        ))}
                      </div>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {!hasFte && (
        <p className="mt-1 text-xs text-muted-foreground">
          Введите плановые FTE для этого сотрудника, чтобы увидеть распределение.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 3 — Summary
// ---------------------------------------------------------------------------

interface StepThreeProps {
  investData: InvestData | null;
  splitsMap: Record<string, AllocSplit[]>;
  fteValues: Record<string, number | null>;
  saveSuccess: boolean;
  onBack: () => void;
}

function StepThree({
  investData,
  splitsMap,
  fteValues,
  saveSuccess,
  onBack,
}: StepThreeProps) {
  if (!investData) return null;

  const summary: Record<string, { auto: number; buh: number; manual: number }> =
    {};

  const ensure = (p: string) => {
    if (!summary[p]) summary[p] = { auto: 0, buh: 0, manual: 0 };
  };

  for (const e of investData.auto_entries) {
    ensure(e.invest_project);
    summary[e.invest_project].auto += e.hours;
  }

  for (const e of investData.buh_entries) {
    if (e.invest_project) {
      ensure(e.invest_project);
      summary[e.invest_project].buh += e.hours;
    }
  }

  for (const e of investData.manual_percent_entries) {
    const k = `${e.username}::${e.task_key}`;
    for (const part of splitHours(e.hours, splitsMap[k] ?? [])) {
      ensure(part.project);
      summary[part.project].manual += part.hours;
    }
  }

  for (const e of investData.manual_project_entries) {
    const k = `${e.username}::${e.task_key}`;
    for (const part of splitHours(e.hours, splitsMap[k] ?? [])) {
      ensure(part.project);
      summary[part.project].manual += part.hours;
    }
  }

  for (const e of investData.keyword_entries) {
    if (e.matched_project) {
      ensure(e.matched_project);
      summary[e.matched_project].manual += e.hours;
    } else {
      const k = `${e.username}::${e.task_key}`;
      for (const part of splitHours(e.hours, splitsMap[k] ?? [])) {
        ensure(part.project);
        summary[part.project].manual += part.hours;
      }
    }
  }

  for (const e of investData.plan_fte_entries) {
    const fteByProject = getFteByProject(
      e.username,
      investData.invest_projects,
      fteValues
    );
    for (const [proj, fte] of Object.entries(fteByProject)) {
      ensure(proj);
      summary[proj].manual += e.hours * fte;
    }
  }

  const projects = sortInvestProjects(Object.keys(summary));
  const totals = { auto: 0, buh: 0, manual: 0, total: 0 };
  for (const p of projects) {
    totals.auto += summary[p].auto;
    totals.buh += summary[p].buh;
    totals.manual += summary[p].manual;
    totals.total +=
      summary[p].auto + summary[p].buh + summary[p].manual;
  }

  const projectGroups = groupPlanVsFactByProject(investData.plan_vs_fact);

  return (
    <>
      {saveSuccess && (
        <div className="rounded-lg border border-[var(--success)] bg-[var(--success-light)] px-4 py-2 text-sm text-[var(--success)]">
          Распределение сохранено
        </div>
      )}

      <div>
        <h3 className="mb-3 text-sm font-medium">Итоги по проектам</h3>
        {projectGroups.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Нет распределённых инвест-часов. Введите план FTE и сохраните
            распределение, чтобы увидеть сравнение.
          </p>
        ) : (
          <div className="space-y-6">
            {projectGroups.map((group) => {
              const highlightTotal =
                group.deltaFte != null && Math.abs(group.deltaFte) > 0.05;
              return (
                <div key={group.project} className="rounded-lg border">
                  <div className="border-b bg-muted/30 px-4 py-3">
                    <p className="text-sm font-medium">{group.project}</p>
                  </div>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Сотрудник</TableHead>
                        <TableHead className="text-right">План, ч</TableHead>
                        <TableHead className="text-right">План FTE</TableHead>
                        <TableHead className="text-right">Факт, ч</TableHead>
                        <TableHead className="text-right">Факт FTE</TableHead>
                        <TableHead className="text-right">
                          Разница, ч
                        </TableHead>
                        <TableHead className="text-right">
                          Разница FTE
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {group.people.map((r) => (
                        <TableRow
                          key={`${r.username}::${r.invest_project}`}
                          className={
                            r.delta_fte != null && Math.abs(r.delta_fte) > 0.05
                              ? "bg-amber-50/50 dark:bg-amber-950/20"
                              : undefined
                          }
                        >
                          <TableCell className="font-medium">
                            {r.username}
                          </TableCell>
                          <TableCell className="font-mono text-right">
                            {fmtMetric(r.plan_hours)}
                          </TableCell>
                          <TableCell className="font-mono text-right">
                            {fmtMetric(r.plan_fte)}
                          </TableCell>
                          <TableCell className="font-mono text-right">
                            {fmtMetric(r.fact_hours)}
                          </TableCell>
                          <TableCell className="font-mono text-right">
                            {fmtMetric(r.fact_fte)}
                          </TableCell>
                          <TableCell className="font-mono text-right">
                            {fmtMetric(r.delta_hours)}
                          </TableCell>
                          <TableCell className="font-mono text-right">
                            {fmtMetric(r.delta_fte)}
                          </TableCell>
                        </TableRow>
                      ))}
                      <TableRow
                        className={cn(
                          "font-semibold",
                          highlightTotal
                            ? "bg-amber-50/70 dark:bg-amber-950/20"
                            : "bg-muted/30"
                        )}
                      >
                        <TableCell>Итого</TableCell>
                        <TableCell className="font-mono text-right">
                          {fmtMetric(group.planHours)}
                        </TableCell>
                        <TableCell className="font-mono text-right">
                          {fmtMetric(group.planFte)}
                        </TableCell>
                        <TableCell className="font-mono text-right">
                          {fmtMetric(group.factHours)}
                        </TableCell>
                        <TableCell className="font-mono text-right">
                          {fmtMetric(group.factFte)}
                        </TableCell>
                        <TableCell className="font-mono text-right">
                          {fmtMetric(group.deltaHours)}
                        </TableCell>
                        <TableCell className="font-mono text-right">
                          {fmtMetric(group.deltaFte)}
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div>
        <h3 className="mb-3 text-sm font-medium">
          Сводка инвест-часов
        </h3>
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Инвест-проект</TableHead>
                <TableHead className="text-right">Авто, ч</TableHead>
                <TableHead className="text-right">BUH Company, ч</TableHead>
                <TableHead className="text-right">Ручное, ч</TableHead>
                <TableHead className="text-right font-semibold">
                  Итого, ч
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {projects.map((p) => {
                const s = summary[p];
                const t = s.auto + s.buh + s.manual;
                return (
                  <TableRow key={p}>
                    <TableCell className="font-medium">{p}</TableCell>
                    <TableCell className="font-mono text-right">
                      {s.auto.toFixed(2)}
                    </TableCell>
                    <TableCell className="font-mono text-right">
                      {s.buh.toFixed(2)}
                    </TableCell>
                    <TableCell className="font-mono text-right">
                      {s.manual.toFixed(2)}
                    </TableCell>
                    <TableCell className="font-mono text-right font-semibold">
                      {t.toFixed(2)}
                    </TableCell>
                  </TableRow>
                );
              })}
              {projects.length > 0 && (
                <TableRow className="bg-muted/30 font-semibold">
                  <TableCell>Всего</TableCell>
                  <TableCell className="font-mono text-right">
                    {totals.auto.toFixed(2)}
                  </TableCell>
                  <TableCell className="font-mono text-right">
                    {totals.buh.toFixed(2)}
                  </TableCell>
                  <TableCell className="font-mono text-right">
                    {totals.manual.toFixed(2)}
                  </TableCell>
                  <TableCell className="font-mono text-right">
                    {totals.total.toFixed(2)}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      <div className="flex justify-start">
        <Button variant="outline" onClick={onBack}>
          Вернуться к распределению
        </Button>
      </div>
    </>
  );
}
