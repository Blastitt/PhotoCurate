"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, ArrowRight, SkipForward, Sparkles } from "lucide-react";
import { sessions, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Card, CardContent } from "@/components/ui/card";
import { WizardStepIndicator } from "@/components/sessions/wizard-step-indicator";
import { ClientPicker } from "@/components/sessions/client-picker";
import { PhotoDropzone, type FileWithProgress } from "@/components/upload/dropzone";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const STEPS = [
  { label: "Details" },
  { label: "Client" },
  { label: "Upload" },
  { label: "Configure" },
];

const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 80 : -80,
    opacity: 0,
  }),
  center: { x: 0, opacity: 1 },
  exit: (direction: number) => ({
    x: direction < 0 ? 80 : -80,
    opacity: 0,
  }),
};

export default function NewSessionPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState(1);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Step 1 - Details
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [shootDate, setShootDate] = useState("");
  const [autoPickCount, setAutoPickCount] = useState(50);

  // Step 2 - Client
  const [clientId, setClientId] = useState<string | null>(null);

  // Step 3 - Upload
  const [files, setFiles] = useState<FileWithProgress[]>([]);

  // Step 4 - Configure
  const [wbMode, setWbMode] = useState("auto");
  const [wbTempShift, setWbTempShift] = useState(0);
  const [wbTintShift, setWbTintShift] = useState(0);
  const [wbStrength, setWbStrength] = useState(0.7);

  const canNext = () => {
    if (step === 0) return title.trim().length > 0;
    return true;
  };

  const goNext = () => {
    if (step < STEPS.length - 1) {
      setDirection(1);
      setStep((s) => s + 1);
    }
  };

  const goBack = () => {
    if (step > 0) {
      setDirection(-1);
      setStep((s) => s - 1);
    }
  };

  // Create session (happens when leaving step 1)
  const createSession = useCallback(async () => {
    if (sessionId) return sessionId;
    setError("");
    setLoading(true);
    try {
      const created = await sessions.create({
        title: title.trim(),
        description: description.trim() || undefined,
        shoot_date: shootDate || undefined,
        client_id: clientId ?? undefined,
        auto_pick_count: autoPickCount,
      });
      setSessionId(created.id);
      return created.id;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create session");
      return null;
    } finally {
      setLoading(false);
    }
  }, [sessionId, title, description, shootDate, clientId, autoPickCount]);

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

  // Upload files to presigned URLs
  const uploadFiles = useCallback(async (sid: string) => {
    const pendingFiles = files.filter((f) => f.status === "pending");
    if (pendingFiles.length === 0) return;

    const filenames = pendingFiles.map((f) => f.file.name);
    const { urls } = await sessions.getUploadUrls(sid, filenames);

    // Upload in parallel batches of 4
    const batchSize = 4;
    for (let i = 0; i < urls.length; i += batchSize) {
      const batch = urls.slice(i, i + batchSize);
      await Promise.all(
        batch.map(async (urlInfo, batchIdx) => {
          const fileIdx = i + batchIdx;
          const globalIdx = files.findIndex(
            (f) => f.file.name === urlInfo.filename && f.status === "pending",
          );
          if (globalIdx === -1) return;

          setFiles((prev) =>
            prev.map((f, idx) =>
              idx === globalIdx ? { ...f, status: "uploading", progress: 0 } : f,
            ),
          );

          try {
            await fetch(urlInfo.upload_url, {
              method: "PUT",
              body: pendingFiles[fileIdx].file,
              headers: { "Content-Type": pendingFiles[fileIdx].file.type || "application/octet-stream" },
            });
            setFiles((prev) =>
              prev.map((f, idx) =>
                idx === globalIdx ? { ...f, status: "done", progress: 100 } : f,
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
  }, [files]);

  const handleStepAction = async () => {
    if (step === 1) {
      // After client step, create session
      const sid = await createSession();
      if (!sid) return;
      goNext();
    } else if (step === 2) {
      // After upload step, upload files
      const sid = sessionId ?? (await createSession());
      if (!sid) return;
      if (files.some((f) => f.status === "pending")) {
        await uploadFiles(sid);
      }
      goNext();
    } else if (step === 3) {
      // Final: update processing config & finalize
      const sid = sessionId ?? (await createSession());
      if (!sid) return;
      setLoading(true);
      try {
        if (wbMode !== "auto" || wbTempShift !== 0 || wbTintShift !== 0 || wbStrength !== 0.7) {
          await sessions.updateProcessingConfig(sid, {
            wb_mode: wbMode,
            wb_temp_shift: wbTempShift,
            wb_tint_shift: wbTintShift,
            wb_strength: wbStrength,
          });
        }
        await sessions.finalize(sid);
        router.push(`/dashboard/sessions/${sid}`);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to start processing");
      } finally {
        setLoading(false);
      }
    } else {
      goNext();
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => router.push("/dashboard/sessions")}
          className="mb-4 flex items-center gap-1 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Sessions
        </button>
        <h1 className="text-2xl font-bold tracking-tight">New Session</h1>
      </div>

      {/* Step indicator */}
      <div className="mb-8">
        <WizardStepIndicator steps={STEPS} currentStep={step} />
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-lg bg-[var(--destructive)]/10 p-3 text-sm text-[var(--destructive)]">
          {error}
        </div>
      )}

      {/* Step content */}
      <Card>
        <CardContent className="p-6">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={step}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.25, ease: "easeInOut" }}
            >
              {step === 0 && (
                <div className="space-y-5">
                  <div className="space-y-1.5">
                    <Label>Session title *</Label>
                    <Input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="Smith Wedding 2026"
                      autoFocus
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Description</Label>
                    <Textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Optional notes about the shoot..."
                      rows={3}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label>Shoot date</Label>
                      <Input
                        type="date"
                        value={shootDate}
                        onChange={(e) => setShootDate(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>
                        Auto-pick count:{" "}
                        <span className="text-[var(--primary)] font-semibold">
                          {autoPickCount}
                        </span>
                      </Label>
                      <Slider
                        min={10}
                        max={500}
                        step={5}
                        value={[autoPickCount]}
                        onValueChange={([v]) => setAutoPickCount(v)}
                        className="mt-3"
                      />
                    </div>
                  </div>
                </div>
              )}

              {step === 1 && (
                <div className="space-y-3">
                  <Label>Select or create a client</Label>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    Link this session to a client, or skip to add one later.
                  </p>
                  <ClientPicker
                    selectedId={clientId}
                    onChange={setClientId}
                  />
                </div>
              )}

              {step === 2 && (
                <div className="space-y-3">
                  <Label>Upload photos</Label>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    Drag and drop your shoot photos, or click to browse.
                  </p>
                  <PhotoDropzone
                    files={files}
                    onFilesAdded={handleFilesAdded}
                    onRemoveFile={handleRemoveFile}
                  />
                </div>
              )}

              {step === 3 && (
                <div className="space-y-5">
                  <div className="space-y-1.5">
                    <Label>White balance mode</Label>
                    <Select value={wbMode} onValueChange={setWbMode}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="auto">Auto (recommended)</SelectItem>
                        <SelectItem value="manual">Manual</SelectItem>
                        <SelectItem value="off">Off</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {wbMode === "manual" && (
                    <>
                      <div className="space-y-1.5">
                        <Label>
                          Temperature: <span className="text-[var(--primary)]">{wbTempShift}</span>K
                        </Label>
                        <Slider
                          min={-500}
                          max={500}
                          step={10}
                          value={[wbTempShift]}
                          onValueChange={([v]) => setWbTempShift(v)}
                        />
                        <div className="flex justify-between text-xs text-[var(--muted-foreground)]">
                          <span>Cool</span>
                          <span>Warm</span>
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        <Label>
                          Tint: <span className="text-[var(--primary)]">{wbTintShift.toFixed(1)}</span>
                        </Label>
                        <Slider
                          min={-1}
                          max={1}
                          step={0.05}
                          value={[wbTintShift]}
                          onValueChange={([v]) => setWbTintShift(v)}
                        />
                        <div className="flex justify-between text-xs text-[var(--muted-foreground)]">
                          <span>Green</span>
                          <span>Magenta</span>
                        </div>
                      </div>
                    </>
                  )}

                  {wbMode === "auto" && (
                    <div className="space-y-1.5">
                      <Label>
                        Correction strength:{" "}
                        <span className="text-[var(--primary)]">
                          {Math.round(wbStrength * 100)}%
                        </span>
                      </Label>
                      <Slider
                        min={0}
                        max={1}
                        step={0.05}
                        value={[wbStrength]}
                        onValueChange={([v]) => setWbStrength(v)}
                      />
                    </div>
                  )}

                  <div className="rounded-lg bg-[var(--muted)] p-4 text-sm text-[var(--muted-foreground)]">
                    <p>
                      <strong className="text-[var(--foreground)]">Ready to process</strong>
                    </p>
                    <p className="mt-1">
                      {files.length} photos will be scored by AI. The top{" "}
                      {autoPickCount} photos will be auto-selected for your gallery.
                    </p>
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="mt-6 flex items-center justify-between">
        <Button
          variant="ghost"
          onClick={goBack}
          disabled={step === 0}
          className="gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>

        <div className="flex gap-2">
          {step === 1 && !clientId && (
            <Button variant="ghost" onClick={goNext} className="gap-2">
              <SkipForward className="h-4 w-4" />
              Skip
            </Button>
          )}

          <Button
            onClick={handleStepAction}
            disabled={!canNext() || loading}
            className="gap-2"
          >
            {loading ? (
              "Processing..."
            ) : step === STEPS.length - 1 ? (
              <>
                <Sparkles className="h-4 w-4" />
                Start Processing
              </>
            ) : (
              <>
                Continue
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
