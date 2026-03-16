"use client";

import { useState, useCallback, useEffect } from "react";
import { sessions, adobe, type SessionResponse, type PresignedURL, ApiError } from "@/lib/api";
import { useFeatures } from "@/lib/features-context";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { PhotoDropzone, type FileWithProgress } from "@/components/upload/dropzone";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkles, Upload, CloudDownload, FolderOpen, Check, ImageIcon } from "lucide-react";

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

      <LightroomImportPanel session={session} onSessionUpdate={onSessionUpdate} />

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

// ─── Lightroom Import Panel ──────────────────────────────────────────

interface LightroomAlbum {
  id: string;
  payload?: { name?: string };
  asset_count?: number;
}

function LightroomImportPanel({
  session,
  onSessionUpdate,
}: {
  session: SessionResponse;
  onSessionUpdate: (s: SessionResponse) => void;
}) {
  const { features, loading: featuresLoading } = useFeatures();
  const [adobeConnected, setAdobeConnected] = useState(false);
  const [statusLoading, setStatusLoading] = useState(true);
  const [albums, setAlbums] = useState<LightroomAlbum[]>([]);
  const [albumsLoading, setAlbumsLoading] = useState(false);
  const [selectedAlbumId, setSelectedAlbumId] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState("");
  const [expanded, setExpanded] = useState(false);

  const enabled = features?.adobe_lightroom ?? false;

  useEffect(() => {
    if (!enabled) {
      setStatusLoading(false);
      return;
    }
    adobe
      .status()
      .then((s) => setAdobeConnected(s.connected))
      .catch(() => {})
      .finally(() => setStatusLoading(false));
  }, [enabled]);

  const loadAlbums = useCallback(async () => {
    setAlbumsLoading(true);
    try {
      const data = await adobe.listAlbums(100);
      setAlbums(data.resources || []);
    } catch {
      setAlbums([]);
    } finally {
      setAlbumsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (expanded && adobeConnected && albums.length === 0) {
      loadAlbums();
    }
  }, [expanded, adobeConnected, albums.length, loadAlbums]);

  const handleImportAlbum = async () => {
    if (!selectedAlbumId) return;
    setImporting(true);
    setImportResult("");
    try {
      const result = await adobe.importToSession(session.id, {
        album_id: selectedAlbumId,
      });
      setImportResult(`Imported ${result.imported_count} photo(s) from Lightroom.`);
      const updated = await sessions.get(session.id);
      onSessionUpdate(updated);
    } catch (err) {
      setImportResult(err instanceof ApiError ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  if (featuresLoading || statusLoading) return null;

  const isDisabled = !enabled || !adobeConnected;

  return (
    <div
      className={cn(
        "rounded-lg border border-[var(--border)]",
        isDisabled && "opacity-50",
      )}
    >
      <button
        type="button"
        onClick={() => !isDisabled && setExpanded((e) => !e)}
        disabled={isDisabled}
        className="flex w-full items-center justify-between p-4 text-left"
      >
        <div className="flex items-center gap-3">
          <CloudDownload className="h-5 w-5 text-[var(--muted-foreground)]" />
          <div>
            <p className="text-sm font-medium">Import from Lightroom</p>
            <p className="text-xs text-[var(--muted-foreground)]">
              {!enabled
                ? "Adobe integration is not configured"
                : !adobeConnected
                  ? "Connect Adobe Lightroom in Settings"
                  : "Browse and import photos from your Lightroom catalog"}
            </p>
          </div>
        </div>
        {!isDisabled && (
          <span className="text-xs text-[var(--muted-foreground)]">
            {expanded ? "Collapse" : "Expand"}
          </span>
        )}
      </button>

      {expanded && !isDisabled && (
        <div className="border-t border-[var(--border)] p-4 space-y-4">
          {albumsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : albums.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              No albums found in your Lightroom catalog.
            </p>
          ) : (
            <>
              <p className="text-sm text-[var(--muted-foreground)]">
                Select an album to import all its photos:
              </p>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {albums.map((album) => (
                  <button
                    key={album.id}
                    type="button"
                    onClick={() =>
                      setSelectedAlbumId(
                        selectedAlbumId === album.id ? null : album.id,
                      )
                    }
                    className={cn(
                      "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                      selectedAlbumId === album.id
                        ? "bg-[var(--primary)]/10 text-[var(--primary)]"
                        : "hover:bg-[var(--muted)]",
                    )}
                  >
                    <FolderOpen className="h-4 w-4 flex-shrink-0" />
                    <span className="flex-1 text-left truncate">
                      {album.payload?.name || "Untitled Album"}
                    </span>
                    {selectedAlbumId === album.id && (
                      <Check className="h-4 w-4 flex-shrink-0" />
                    )}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-3">
                <Button
                  onClick={handleImportAlbum}
                  disabled={!selectedAlbumId || importing}
                  size="sm"
                  className="gap-2"
                >
                  <ImageIcon className="h-4 w-4" />
                  {importing ? "Importing..." : "Import Album"}
                </Button>
                {importResult && (
                  <p className="text-sm text-[var(--muted-foreground)]">
                    {importResult}
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
