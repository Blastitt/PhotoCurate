"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, ImageIcon, X } from "lucide-react";
import { cn, formatFileSize } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

interface FileWithProgress {
  file: File;
  progress: number;
  status: "pending" | "uploading" | "done" | "error";
  error?: string;
}

interface DropzoneProps {
  files: FileWithProgress[];
  onFilesAdded: (files: File[]) => void;
  onRemoveFile: (index: number) => void;
  disabled?: boolean;
  maxFiles?: number;
}

export function PhotoDropzone({
  files,
  onFilesAdded,
  onRemoveFile,
  disabled,
  maxFiles = 100,
}: DropzoneProps) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      onFilesAdded(accepted);
    },
    [onFilesAdded],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp", ".tiff", ".raw", ".cr2", ".nef", ".arw"] },
    maxFiles,
    disabled,
    multiple: true,
  });

  const totalSize = files.reduce((acc, f) => acc + f.file.size, 0);
  const uploadedCount = files.filter((f) => f.status === "done").length;
  const uploadingCount = files.filter((f) => f.status === "uploading").length;

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={cn(
          "relative flex min-h-[240px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed transition-all duration-200",
          isDragActive
            ? "border-[var(--primary)] bg-[var(--primary)]/5 scale-[1.01]"
            : "border-[var(--border)] hover:border-[var(--muted-foreground)] hover:bg-[var(--muted)]/50",
          disabled && "pointer-events-none opacity-50",
        )}
      >
        <input {...getInputProps()} />
        <motion.div
          animate={{
            scale: isDragActive ? 1.05 : 1,
            y: isDragActive ? -4 : 0,
          }}
          className="flex flex-col items-center gap-3 px-4 text-center"
        >
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--muted)]">
            <Upload
              className={cn(
                "h-6 w-6 transition-colors",
                isDragActive
                  ? "text-[var(--primary)]"
                  : "text-[var(--muted-foreground)]",
              )}
            />
          </div>
          <div>
            <p className="text-sm font-medium">
              {isDragActive ? "Drop photos here" : "Drag & drop photos"}
            </p>
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
              or click to browse · JPG, PNG, WebP, TIFF, RAW
            </p>
          </div>
        </motion.div>
      </div>

      {/* File summary */}
      {files.length > 0 && (
        <div className="flex items-center justify-between rounded-lg bg-[var(--muted)] px-4 py-2 text-sm">
          <span>
            <strong>{files.length}</strong> photos · {formatFileSize(totalSize)}
          </span>
          {uploadingCount > 0 && (
            <span className="text-[var(--primary)]">
              Uploading {uploadedCount + uploadingCount} of {files.length}...
            </span>
          )}
          {uploadedCount === files.length && files.length > 0 && (
            <span className="text-[var(--success)]">All uploaded ✓</span>
          )}
        </div>
      )}

      {/* File list */}
      <AnimatePresence mode="popLayout">
        {files.length > 0 && (
          <div className="max-h-64 space-y-1 overflow-y-auto rounded-lg">
            {files.map((f, i) => (
              <motion.div
                key={`${f.file.name}-${i}`}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="flex items-center gap-3 rounded-lg bg-[var(--card)] px-3 py-2"
              >
                <ImageIcon className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" />
                <span className="flex-1 truncate text-sm">{f.file.name}</span>
                <span className="shrink-0 text-xs text-[var(--muted-foreground)]">
                  {formatFileSize(f.file.size)}
                </span>
                {f.status === "uploading" && (
                  <Progress value={f.progress} className="w-20 h-1.5" />
                )}
                {f.status === "done" && (
                  <span className="text-xs text-[var(--success)]">✓</span>
                )}
                {f.status === "error" && (
                  <span className="text-xs text-[var(--destructive)]">✗</span>
                )}
                {f.status === "pending" && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemoveFile(i);
                    }}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

export type { FileWithProgress };
