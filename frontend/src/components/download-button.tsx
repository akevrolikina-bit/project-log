"use client";

import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getReportUrl } from "@/lib/api";

interface DownloadButtonProps {
  uploadId: number;
}

export function DownloadButton({ uploadId }: DownloadButtonProps) {
  const handleDownload = () => {
    window.open(getReportUrl(uploadId), "_blank");
  };

  return (
    <Button variant="outline" size="sm" onClick={handleDownload}>
      <Download data-icon="inline-start" className="size-3.5" />
      Скачать отчёт
    </Button>
  );
}
