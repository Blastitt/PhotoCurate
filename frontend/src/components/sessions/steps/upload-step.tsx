"use client";

import { useState, useCallback } from "react";
import { sessions, type SessionResponse, type PresignedURL, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { PhotoDropzone, type FileWithProgress } from "@/components/upload/dropzone";
import { Sparkles } from "lucide-react";

interface UploadStepProps {
  session: SessionResponse;
  onSessionUpdate: (s: SessionResponse) => void;
}

export function UploadStep({ session, onSessionUpdate }: UploadStepProps) {
  const [files, setFiles] = useState<FileWithProgress[]>([]);
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState("");

  const handleFilesAdded = useCallback((newFiles: File[]) => {
    setFiles((prev) => [
      ...prev,
      ...newFiles.map(
        (f): FileWithProgress => ({
          file: f,
          progress: 0,
          status: "pending",
        }),
      ),
    ]);
  }, []);

  const handleRemoveFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const uploadAndFinalize = async () => {
    setError("");
    const pendingFiles = files.filter((f) => f.status === "pending");

    if (pendingFiles.length > 0) {
      try {
        const { urls } = await sessions.getUploadUrls(
          session.id,
          pendingFiles.map((f) => f.file.name),
        );

        const batchSize = 4;
        for (let i = 0; i < urls.length; i += batchSize) {
          const batch = urls.slice(i, i + batchSize);
          await Promise.all(
            batch.map(async (urlInfo: PresignedURL, batchIdx: number) => {
              const fileIdx = i + batchIdx;
              const globalIdx = files.findIndex(
                (f) =>
                  f.file.name === urlInfo.filename && f.status === "pending",
              );
              if (globalIdx === -1) return;

              setFiles((prev) =>
                prev.map((f, idx) =>
                  idx === globalIdx
                    ? { ...f, status: "uploading", progress: 50 }
                    : f,
                ),
              );

              try {
                await fetch(urlInfo.upload_url, {
                  method: "PUT",
                  body: pendingFiles[fileIdx].file,
                  headers: {
                    "Content-Type":
                      pendingFiles[fileIdx].file.type ||
                      "application/octet-stream",
                  },
                });
                setFiles((prev) =>
                  prev.map((f, idx) =>
                    idx === globalIdx
                      ? { ...f, status: "done", progress: 100 }
                      : f,
                  ),
                );
              } catch {
                setFiles((prev) =>
                  prev.map((f, idx) =>
                    idx === globalIdx
                      ? { ...f, status: "error", error: "Upload failed" }
                      : f,
                  ),
                );
              }
            }),
          );
        }
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Failed to get upload URLs",
        );
        return;
      }
    }

    // Finalize
    setFinalizing(true);
    try {
      await sessions.finalize(session.id);
      const updated = await sessions.get(session.id);
      onSessionUpdate(updated);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to start processing",
      );
    } finally {
      setFinalizing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Upload Photos</h3>
        <p className="text-sm text-[var(--muted-foreground)]">
          Add photos from your shoot session. You can upload more later.
        </p>
      </div>

      <PhotoDropzone
        files={files}
        onFilesAdded={handleFilesAdded}
        onRemoveFile={handleRemoveFile}
      />

      {error && (
        <p className="text-sm text-[var(--destructive)]">{error}</p>
      )}

      <div className="flex justify-end">
        <Button
          onClick={uploadAndFinalize}
          disabled={files.length === 0 || finalizing}
          className="gap-2"
        >
          <Sparkles className="h-4 w-4" />
          {finalizing ? "Processing..." : "Upload & Start AI Processing"}
        </Button>
      </div>
    </div>
  );
}
