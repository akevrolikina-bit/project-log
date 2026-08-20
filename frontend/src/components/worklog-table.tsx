"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { ChevronDown, ChevronRight, X } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import type { WorklogEntry } from "@/lib/api";

interface WorklogTableProps {
  entries: WorklogEntry[];
  isLoading?: boolean;
  defaultCollapsed?: boolean;
}

function MultiFilter({
  label,
  placeholder,
  selected,
  options,
  onAdd,
  onRemove,
}: {
  label: string;
  placeholder: string;
  selected: string[];
  options: string[];
  onAdd: (value: string) => void;
  onRemove: (value: string) => void;
}) {
  const [inputValue, setInputValue] = useState("");
  const listId = `list-${label.replace(/\s/g, "")}`;

  const filteredOptions = options.filter((o) => !selected.includes(o));

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && inputValue.trim()) {
      e.preventDefault();
      const match = options.find(
        (o) => o.toLowerCase() === inputValue.trim().toLowerCase()
      );
      onAdd(match || inputValue.trim());
      setInputValue("");
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputValue(val);
    const exactMatch = options.find(
      (o) => o.toLowerCase() === val.toLowerCase() && !selected.includes(o)
    );
    if (exactMatch) {
      onAdd(exactMatch);
      setInputValue("");
    }
  };

  return (
    <div className="space-y-1.5">
      <label className="text-xs text-muted-foreground">{label}</label>
      <Input
        placeholder={placeholder}
        value={inputValue}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        list={listId}
      />
      <datalist id={listId}>
        {filteredOptions.map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selected.map((val) => (
            <span
              key={val}
              className="inline-flex items-center gap-0.5 rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary"
            >
              {val}
              <button
                onClick={() => onRemove(val)}
                className="ml-0.5 rounded-full hover:bg-primary/20 p-0.5 cursor-pointer"
              >
                <X className="size-2.5" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function WorklogTable({
  entries,
  isLoading,
  defaultCollapsed = false,
}: WorklogTableProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const [selectedUsernames, setSelectedUsernames] = useState<string[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<string[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const usernames = useMemo(() => {
    const set = new Set(entries.map((e) => e.username));
    return Array.from(set).sort();
  }, [entries]);

  const projects = useMemo(() => {
    const set = new Set(entries.map((e) => e.project));
    return Array.from(set).sort();
  }, [entries]);

  const keys = useMemo(() => {
    const set = new Set(entries.map((e) => e.key));
    return Array.from(set).sort();
  }, [entries]);

  const toDateString = (iso: string) => {
    const d = new Date(iso);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  };

  const filteredEntries = useMemo(() => {
    return entries.filter((e) => {
      if (selectedUsernames.length > 0 && !selectedUsernames.includes(e.username))
        return false;

      if (selectedProjects.length > 0 && !selectedProjects.includes(e.project))
        return false;

      if (selectedKeys.length > 0 && !selectedKeys.includes(e.key))
        return false;

      const entryDate = toDateString(e.started);
      if (dateFrom && entryDate < dateFrom) return false;
      if (dateTo && entryDate > dateTo) return false;

      return true;
    });
  }, [entries, selectedUsernames, selectedProjects, selectedKeys, dateFrom, dateTo]);

  const hasAnyFilter =
    selectedUsernames.length > 0 ||
    selectedProjects.length > 0 ||
    selectedKeys.length > 0 ||
    dateFrom ||
    dateTo;

  const clearAllFilters = () => {
    setSelectedUsernames([]);
    setSelectedProjects([]);
    setSelectedKeys([]);
    setDateFrom("");
    setDateTo("");
  };

  useEffect(() => {
    setCollapsed(defaultCollapsed);
  }, [defaultCollapsed]);

  const addUsername = useCallback((v: string) => setSelectedUsernames((prev) => [...prev, v]), []);
  const removeUsername = useCallback((v: string) => setSelectedUsernames((prev) => prev.filter((x) => x !== v)), []);
  const addProject = useCallback((v: string) => setSelectedProjects((prev) => [...prev, v]), []);
  const removeProject = useCallback((v: string) => setSelectedProjects((prev) => prev.filter((x) => x !== v)), []);
  const addKey = useCallback((v: string) => setSelectedKeys((prev) => [...prev, v]), []);
  const removeKey = useCallback((v: string) => setSelectedKeys((prev) => prev.filter((x) => x !== v)), []);

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  };

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  }

  if (entries.length === 0) return null;

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        className="flex w-full items-center justify-between rounded-lg border bg-muted/30 px-4 py-3 text-left transition-colors hover:bg-muted/50"
      >
        <span className="flex items-center gap-2">
          {collapsed ? (
            <ChevronRight className="size-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="size-4 text-muted-foreground" />
          )}
          <span className="text-sm font-medium">Загруженные записи</span>
          <span className="text-xs text-muted-foreground">
            {entries.length} строк
          </span>
        </span>
        {collapsed && (
          <span className="text-xs text-muted-foreground">
            Нажмите, чтобы открыть
          </span>
        )}
      </button>

      {collapsed ? null : (
      <>
      {/* Filters panel */}
      <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Фильтры
          </p>
          {hasAnyFilter && (
            <Button variant="ghost" size="xs" onClick={clearAllFilters}>
              <X data-icon="inline-start" className="size-3" />
              Сбросить
            </Button>
          )}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <MultiFilter
            label="Сотрудник"
            placeholder="Введите имя и Enter..."
            selected={selectedUsernames}
            options={usernames}
            onAdd={addUsername}
            onRemove={removeUsername}
          />

          <MultiFilter
            label="Проект"
            placeholder="Введите проект и Enter..."
            selected={selectedProjects}
            options={projects}
            onAdd={addProject}
            onRemove={removeProject}
          />

          <MultiFilter
            label="Ключ задачи"
            placeholder="ADM-1234 и Enter..."
            selected={selectedKeys}
            options={keys}
            onAdd={addKey}
            onRemove={removeKey}
          />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Период с</label>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Период по</label>
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Results summary */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {hasAnyFilter && (
            <Badge variant="secondary">
              {filteredEntries.length} из {entries.length}
            </Badge>
          )}
          <span className="text-xs text-muted-foreground">
            Сумма часов:{" "}
            <span className="font-mono font-medium">
              {filteredEntries.reduce((sum, e) => sum + e.hours, 0).toFixed(2)}
            </span>
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          Всего записей: <span className="font-mono font-medium">{entries.length}</span>
        </p>
      </div>

      {/* Table */}
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Сотрудник</TableHead>
              <TableHead>Дата</TableHead>
              <TableHead>Проект</TableHead>
              <TableHead>Ключ</TableHead>
              <TableHead>Тип</TableHead>
              <TableHead>Название</TableHead>
              <TableHead className="text-right">Часы</TableHead>
              <TableHead>Комментарий</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredEntries.slice(0, 100).map((entry, idx) => (
              <TableRow key={idx}>
                <TableCell className="font-medium">{entry.username}</TableCell>
                <TableCell className="font-mono text-xs">
                  {formatDate(entry.started)}
                </TableCell>
                <TableCell>{entry.project}</TableCell>
                <TableCell className="font-mono text-xs">{entry.key}</TableCell>
                <TableCell>{entry.task_type}</TableCell>
                <TableCell
                  className="max-w-[360px] whitespace-normal break-words"
                  title={entry.title}
                >
                  {entry.title}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {entry.hours.toFixed(2)}
                </TableCell>
                <TableCell
                  className="max-w-[360px] whitespace-normal break-words text-muted-foreground"
                  title={entry.comment}
                >
                  {entry.comment}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {filteredEntries.length > 100 && (
          <div className="border-t px-4 py-2 text-center text-xs text-muted-foreground">
            Показано 100 из {filteredEntries.length} записей.
            Используйте фильтры для уточнения.
          </div>
        )}
      </div>

      {/* Employee badges */}
      {usernames.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <span className="text-xs text-muted-foreground self-center mr-1">
            Сотрудники:
          </span>
          {usernames.map((name) => (
            <button
              key={name}
              onClick={() => {
                if (selectedUsernames.includes(name)) {
                  removeUsername(name);
                } else {
                  addUsername(name);
                }
              }}
              className={`
                inline-flex h-5 items-center rounded-full px-2 text-xs transition-colors cursor-pointer
                ${
                  selectedUsernames.includes(name)
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }
              `}
            >
              {name}
            </button>
          ))}
        </div>
      )}
      </>
      )}
    </div>
  );
}
