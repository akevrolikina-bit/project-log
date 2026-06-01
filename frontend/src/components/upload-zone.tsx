"use client";

import { useCallback, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { uploadFile, type UploadResponse } from "@/lib/api";

interface UploadZoneProps {
  onUploadComplete: (upload: UploadResponse) => void;
}

export function UploadZone({ onUploadComplete }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      setIsUploading(true);
      try {
        const result = await uploadFile(file);
        onUploadComplete(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setIsUploading(false);
      }
    },
    [onUploadComplete]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      e.target.value = "";
    },
    [handleFile]
  );

  return (
    <Card>
      <CardContent>
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`
            flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8
            transition-colors cursor-pointer
            ${isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-muted-foreground/50"}
            ${isUploading ? "pointer-events-none opacity-60" : ""}
          `}
        >
          <div className="rounded-full bg-muted p-3">
            <Upload className="size-5 text-muted-foreground" />
          </div>

          <div className="text-center">
            <p className="text-sm font-medium">
              {isUploading
                ? "Загрузка..."
                : "Перетащите файл сюда"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              .xls файл из Jira (Time Sheet Report)
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            disabled={isUploading}
            onClick={() => inputRef.current?.click()}
          >
            Выбрать файл
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept=".xls,.xlsx"
            className="sr-only"
            onChange={handleInputChange}
            disabled={isUploading}
          />

          {error && (
            <p className="text-xs text-destructive">{error}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
