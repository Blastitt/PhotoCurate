"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  Calendar,
  ImageIcon,
  MoreHorizontal,
  Trash2,
} from "lucide-react";
import { sessions, type SessionResponse, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  WorkflowStepper,
  deriveSteps,
} from "@/components/sessions/workflow-stepper";
import { UploadStep } from "@/components/sessions/steps/upload-step";
import { ProcessingStep } from "@/components/sessions/steps/processing-step";
import { ReviewStep } from "@/components/sessions/steps/review-step";
import { GalleryStep } from "@/components/sessions/steps/gallery-step";
import { SelectionsStep } from "@/components/sessions/steps/selections-step";
import { DeliverStep } from "@/components/sessions/steps/deliver-step";
import { formatDate, statusLabel } from "@/lib/utils";

const stepContentVariants = {
  enter: { opacity: 0, y: 20 },
  center: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
};

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeStep, setActiveStep] = useState("upload");
  const [deleting, setDeleting] = useState(false);

  const loadSession = useCallback(async () => {
    try {
      const s = await sessions.get(id);
      setSession(s);

      // Auto-set active step based on session status
      const steps = deriveSteps(s.status);
      const active = steps.find((st) => st.status === "active");
      if (active) setActiveStep(active.id);
    } catch {
      setError("Failed to load session");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  const handleSessionUpdate = useCallback(
    (updated: SessionResponse) => {
      setSession(updated);
      const steps = deriveSteps(updated.status);
      const active = steps.find((st) => st.status === "active");
      if (active) setActiveStep(active.id);
    },
    [],
  );

  const handleDelete = async () => {
    if (!confirm("Delete this session and all its photos?")) return;
    setDeleting(true);
    try {
      await sessions.delete(id);
      router.push("/dashboard/sessions");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete");
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-16 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-[var(--destructive)]">{error || "Session not found"}</p>
        <Button
          variant="ghost"
          onClick={() => router.push("/dashboard/sessions")}
          className="mt-4"
        >
          Back to sessions
        </Button>
      </div>
    );
  }

  const steps = deriveSteps(session.status);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <button
            onClick={() => router.push("/dashboard/sessions")}
            className="mb-3 flex items-center gap-1 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Sessions
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">
              {session.title}
            </h1>
            <Badge variant={statusVariant(session.status)}>
              {statusLabel(session.status)}
            </Badge>
          </div>
          <div className="mt-1 flex items-center gap-3 text-sm text-[var(--muted-foreground)]">
            <span className="flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5" />
              {formatDate(session.shoot_date)}
            </span>
            <span className="flex items-center gap-1">
              <ImageIcon className="h-3.5 w-3.5" />
              {session.auto_pick_count} auto-picks
            </span>
          </div>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="icon">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={handleDelete}
              disabled={deleting}
              className="text-[var(--destructive)] focus:text-[var(--destructive)]"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {deleting ? "Deleting..." : "Delete session"}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Workflow stepper */}
      <WorkflowStepper
        steps={steps}
        activeStep={activeStep}
        onStepClick={setActiveStep}
      />

      {/* Step content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeStep}
          variants={stepContentVariants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{ duration: 0.2 }}
        >
          {activeStep === "upload" && (
            <UploadStep
              session={session}
              onSessionUpdate={handleSessionUpdate}
            />
          )}
          {activeStep === "processing" && (
            <ProcessingStep
              session={session}
              onSessionUpdate={handleSessionUpdate}
            />
          )}
          {activeStep === "review" && (
            <ReviewStep
              session={session}
              onSessionUpdate={handleSessionUpdate}
              onNavigateToGallery={() => setActiveStep("gallery")}
            />
          )}
          {activeStep === "gallery" && (
            <GalleryStep
              session={session}
              onSessionUpdate={handleSessionUpdate}
            />
          )}
          {activeStep === "selections" && (
            <SelectionsStep
              session={session}
              onSessionUpdate={handleSessionUpdate}
              onNavigateToDeliver={() => setActiveStep("deliver")}
            />
          )}
          {activeStep === "deliver" && (
            <DeliverStep
              session={session}
              onSessionUpdate={handleSessionUpdate}
            />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
