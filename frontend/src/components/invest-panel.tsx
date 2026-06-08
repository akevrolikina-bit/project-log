"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Upload,
  ChevronDown,
  ChevronRight,
  Check,
  FileSpreadsheet,
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
} from "@/lib/api";

interface InvestPanelProps {
  uploadId: number;
}

type Step = 1 | 2 | 3;

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

  const [percentValues, setPercentValues] = useState<
    Record<string, number | null>
  >({});
  const [projectValues, setProjectValues] = useState<
    Record<string, string | null>
  >({});

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
      const pv: Record<string, number | null> = {};
      const prv: Record<string, string | null> = {};
      for (const a of data.saved_allocations) {
        const k = `${a.username}::${a.task_key}`;
        if (a.allocation_type === "manual_percent") {
          pv[k] = a.percentage;
          prv[k] = a.invest_project;
        } else {
          prv[k] = a.invest_project;
        }
      }
      for (const e of data.manual_percent_entries) {
        const k = `${e.username}::${e.task_key}`;
        if (!(k in pv)) {
          pv[k] = e.percentage;
          prv[k] = e.invest_project;
        }
      }
      for (const e of data.manual_project_entries) {
        const k = `${e.username}::${e.task_key}`;
        if (!(k in prv)) {
          prv[k] = e.invest_project;
        }
      }
      setPercentValues(pv);
      setProjectValues(prv);
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
    setIsSaving(true);
    setSaveSuccess(false);
    setError(null);

    const allocations: AllocationEntry[] = [];

    for (const e of investData.manual_percent_entries) {
      const k = `${e.username}::${e.task_key}`;
      const pct = percentValues[k];
      const proj = projectValues[k];
      if (pct != null && pct > 0 && proj) {
        allocations.push({
          username: e.username,
          task_key: e.task_key,
          invest_project: proj,
          percentage: pct,
          allocation_type: "manual_percent",
        });
      }
    }

    for (const e of investData.manual_project_entries) {
      const k = `${e.username}::${e.task_key}`;
      const proj = projectValues[k];
      if (proj) {
        allocations.push({
          username: e.username,
          task_key: e.task_key,
          invest_project: proj,
          percentage: 100,
          allocation_type: "manual_project",
        });
      }
    }

    try {
      await saveInvestAllocations(uploadId, allocations);
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
      <Card>
        <CardHeader>
          <CardTitle>Инвест-направления</CardTitle>
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
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Инвест-направления</CardTitle>
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
            percentValues={percentValues}
            setPercentValues={setPercentValues}
            projectValues={projectValues}
            setProjectValues={setProjectValues}
            onSave={handleSave}
            isSaving={isSaving}
            onBack={() => setStep(1)}
          />
        )}

        {step === 3 && (
          <StepThree
            investData={investData}
            percentValues={percentValues}
            projectValues={projectValues}
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
                ? "bg-[var(--accent)] text-white"
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
                      className="size-4 rounded border-[var(--border)] accent-[var(--accent)]"
                    />
                  </TableCell>
                  <TableCell className="font-medium">{emp.username}</TableCell>
                  <TableCell className="font-mono text-right">
                    {emp.total_hours.toFixed(2)}
                  </TableCell>
                  <TableCell className="text-center">
                    {emp.has_invest_tasks ? (
                      <span className="inline-flex h-5 items-center rounded-full bg-[var(--accent-light)] px-2 text-xs font-medium text-[var(--accent)]">
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
  percentValues: Record<string, number | null>;
  setPercentValues: React.Dispatch<
    React.SetStateAction<Record<string, number | null>>
  >;
  projectValues: Record<string, string | null>;
  setProjectValues: React.Dispatch<
    React.SetStateAction<Record<string, string | null>>
  >;
  onSave: () => void;
  isSaving: boolean;
  onBack: () => void;
}

function StepTwo({
  investData,
  isLoadingData,
  percentValues,
  setPercentValues,
  projectValues,
  setProjectValues,
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

  const usernames = new Set<string>();
  investData.auto_entries.forEach((e) => usernames.add(e.username));
  investData.buh_entries.forEach((e) => usernames.add(e.username));
  investData.manual_percent_entries.forEach((e) => usernames.add(e.username));
  investData.manual_project_entries.forEach((e) => usernames.add(e.username));

  const sortedUsers = Array.from(usernames).sort();

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
            percentValues={percentValues}
            setPercentValues={setPercentValues}
            projectValues={projectValues}
            setProjectValues={setProjectValues}
          />
        ))
      )}

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          Назад
        </Button>
        <Button onClick={onSave} disabled={isSaving}>
          {isSaving ? "Сохранение..." : "Сохранить"}
        </Button>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Employee allocation card (collapsible)
// ---------------------------------------------------------------------------

interface EmployeeAllocCardProps {
  username: string;
  investData: InvestData;
  percentValues: Record<string, number | null>;
  setPercentValues: React.Dispatch<
    React.SetStateAction<Record<string, number | null>>
  >;
  projectValues: Record<string, string | null>;
  setProjectValues: React.Dispatch<
    React.SetStateAction<Record<string, string | null>>
  >;
}

function EmployeeAllocCard({
  username,
  investData,
  percentValues,
  setPercentValues,
  projectValues,
  setProjectValues,
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
              investProjects={investData.invest_projects}
              percentValues={percentValues}
              setPercentValues={setPercentValues}
              projectValues={projectValues}
              setProjectValues={setProjectValues}
            />
          )}

          {/* Manual project entries */}
          {manualProjEntries.length > 0 && (
            <ManualProjectSection
              entries={manualProjEntries}
              investProjects={investData.invest_projects}
              projectValues={projectValues}
              setProjectValues={setProjectValues}
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
                <TableCell className="text-sm">{e.title}</TableCell>
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
                <TableCell className="text-sm">{e.title}</TableCell>
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

interface ManualPercentSectionProps {
  entries: ManualPercentEntry[];
  investProjects: string[];
  percentValues: Record<string, number | null>;
  setPercentValues: React.Dispatch<
    React.SetStateAction<Record<string, number | null>>
  >;
  projectValues: Record<string, string | null>;
  setProjectValues: React.Dispatch<
    React.SetStateAction<Record<string, string | null>>
  >;
}

function ManualPercentSection({
  entries,
  investProjects,
  percentValues,
  setPercentValues,
  projectValues,
  setProjectValues,
}: ManualPercentSectionProps) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Ручное распределение (процент)
      </h4>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ключ</TableHead>
              <TableHead>Задача</TableHead>
              <TableHead className="text-right">Часы</TableHead>
              <TableHead className="w-24">%</TableHead>
              <TableHead className="w-32">Проект</TableHead>
              <TableHead className="text-right">Инвест-часы</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((e) => {
              const k = `${e.username}::${e.task_key}`;
              const pct = percentValues[k] ?? null;
              const proj = projectValues[k] ?? investProjects[0] ?? "";
              const investHours =
                pct != null ? (e.hours * pct) / 100 : null;

              return (
                <TableRow key={k}>
                  <TableCell className="font-mono text-xs">
                    {e.task_key}
                  </TableCell>
                  <TableCell className="text-sm">{e.title}</TableCell>
                  <TableCell className="font-mono text-right">
                    {e.hours.toFixed(2)}
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      value={pct ?? ""}
                      onChange={(ev) => {
                        const val = ev.target.value
                          ? Number(ev.target.value)
                          : null;
                        setPercentValues((prev) => ({
                          ...prev,
                          [k]: val,
                        }));
                      }}
                      className="h-7 w-20 text-right font-mono text-xs"
                    />
                  </TableCell>
                  <TableCell>
                    <select
                      value={proj}
                      onChange={(ev) =>
                        setProjectValues((prev) => ({
                          ...prev,
                          [k]: ev.target.value || null,
                        }))
                      }
                      className="h-7 w-full rounded-lg border border-input bg-transparent px-2 text-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                    >
                      <option value="">—</option>
                      {investProjects.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </TableCell>
                  <TableCell className="font-mono text-right">
                    {investHours != null ? investHours.toFixed(2) : "—"}
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
// Manual project section (editable)
// ---------------------------------------------------------------------------

interface ManualProjectSectionProps {
  entries: ManualProjectEntry[];
  investProjects: string[];
  projectValues: Record<string, string | null>;
  setProjectValues: React.Dispatch<
    React.SetStateAction<Record<string, string | null>>
  >;
}

function ManualProjectSection({
  entries,
  investProjects,
  projectValues,
  setProjectValues,
}: ManualProjectSectionProps) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Ручное назначение проекта
      </h4>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ключ</TableHead>
              <TableHead>Задача</TableHead>
              <TableHead className="text-right">Часы</TableHead>
              <TableHead className="w-32">Проект</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((e) => {
              const k = `${e.username}::${e.task_key}`;
              const proj = projectValues[k] ?? "";

              return (
                <TableRow key={k}>
                  <TableCell className="font-mono text-xs">
                    {e.task_key}
                  </TableCell>
                  <TableCell className="text-sm">{e.title}</TableCell>
                  <TableCell className="font-mono text-right">
                    {e.hours.toFixed(2)}
                  </TableCell>
                  <TableCell>
                    <select
                      value={proj}
                      onChange={(ev) =>
                        setProjectValues((prev) => ({
                          ...prev,
                          [k]: ev.target.value || null,
                        }))
                      }
                      className="h-7 w-full rounded-lg border border-input bg-transparent px-2 text-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                    >
                      <option value="">—</option>
                      {investProjects.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
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
// Step 3 — Summary
// ---------------------------------------------------------------------------

interface StepThreeProps {
  investData: InvestData | null;
  percentValues: Record<string, number | null>;
  projectValues: Record<string, string | null>;
  saveSuccess: boolean;
  onBack: () => void;
}

function StepThree({
  investData,
  percentValues,
  projectValues,
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
    const pct = percentValues[k];
    const proj = projectValues[k];
    if (pct != null && proj) {
      ensure(proj);
      summary[proj].manual += (e.hours * pct) / 100;
    }
  }

  for (const e of investData.manual_project_entries) {
    const k = `${e.username}::${e.task_key}`;
    const proj = projectValues[k];
    if (proj) {
      ensure(proj);
      summary[proj].manual += e.hours;
    }
  }

  const projects = Object.keys(summary).sort();
  const totals = { auto: 0, buh: 0, manual: 0, total: 0 };
  for (const p of projects) {
    totals.auto += summary[p].auto;
    totals.buh += summary[p].buh;
    totals.manual += summary[p].manual;
    totals.total +=
      summary[p].auto + summary[p].buh + summary[p].manual;
  }

  return (
    <>
      {saveSuccess && (
        <div className="rounded-lg border border-[var(--success)] bg-[var(--success-light)] px-4 py-2 text-sm text-[var(--success)]">
          Распределение сохранено
        </div>
      )}

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
