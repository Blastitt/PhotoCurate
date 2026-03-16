"use client";

import { motion } from "framer-motion";
import {
  Upload,
  Cpu,
  Eye,
  Share2,
  Heart,
  Truck,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface WorkflowStep {
  id: string;
  label: string;
  icon: React.ElementType;
  status: "pending" | "active" | "complete";
}

const DEFAULT_STEPS: Omit<WorkflowStep, "status">[] = [
  { id: "upload", label: "Upload", icon: Upload },
  { id: "processing", label: "Processing", icon: Cpu },
  { id: "review", label: "Review", icon: Eye },
  { id: "gallery", label: "Gallery", icon: Share2 },
  { id: "selections", label: "Selections", icon: Heart },
  { id: "deliver", label: "Deliver", icon: Truck },
];

/** Derive step statuses from session status string */
export function deriveSteps(sessionStatus: string): WorkflowStep[] {
  const statusOrder = [
    "created",
    "uploading",
    "processing",
    "curated",
    "gallery_ready",
    "gallery_shared",
    "selection_complete",
    "editing",
    "delivered",
  ];
  const idx = statusOrder.indexOf(sessionStatus);

  // Map session status to active step index
  let activeStepIdx = 0;
  if (idx <= 1) activeStepIdx = 0; // created, uploading → Upload
  else if (idx === 2) activeStepIdx = 1; // processing → Processing
  else if (idx === 3 || idx === 4) activeStepIdx = 2; // curated, gallery_ready → Review
  else if (idx === 5) activeStepIdx = 3; // gallery_shared → Gallery
  else if (idx === 6) activeStepIdx = 4; // selection_complete → Selections
  else activeStepIdx = 5; // editing, delivered → Deliver

  return DEFAULT_STEPS.map((s, i) => ({
    ...s,
    status:
      i < activeStepIdx ? "complete" : i === activeStepIdx ? "active" : "pending",
  }));
}

interface WorkflowStepperProps {
  steps: WorkflowStep[];
  activeStep: string;
  onStepClick: (stepId: string) => void;
}

export function WorkflowStepper({
  steps,
  activeStep,
  onStepClick,
}: WorkflowStepperProps) {
  return (
    <div className="sticky top-0 z-10 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      {/* Horizontal on desktop */}
      <div className="hidden sm:flex items-center justify-between">
        {steps.map((step, i) => {
          const Icon = step.icon;
          const isClickable = step.status === "complete" || step.status === "active";
          const isViewing = step.id === activeStep;

          return (
            <div key={step.id} className="flex flex-1 items-center">
              <button
                type="button"
                onClick={() => isClickable && onStepClick(step.id)}
                disabled={!isClickable}
                className={cn(
                  "flex flex-col items-center gap-1.5 transition-all",
                  isClickable ? "cursor-pointer" : "cursor-default opacity-40",
                )}
              >
                <motion.div
                  animate={{ scale: isViewing ? 1.1 : 1 }}
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors",
                    step.status === "complete"
                      ? "border-[var(--success)] bg-[var(--success)] text-white"
                      : step.status === "active"
                        ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                        : "border-[var(--border)] text-[var(--muted-foreground)]",
                    isViewing && step.status === "active" && "animate-pulse-ring",
                  )}
                >
                  {step.status === "complete" ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                </motion.div>
                <span
                  className={cn(
                    "text-xs font-medium whitespace-nowrap",
                    isViewing
                      ? "text-[var(--primary)]"
                      : step.status === "complete"
                        ? "text-[var(--foreground)]"
                        : "text-[var(--muted-foreground)]",
                  )}
                >
                  {step.label}
                </span>
              </button>

              {/* Connector */}
              {i < steps.length - 1 && (
                <div className="mx-2 h-0.5 flex-1">
                  <div
                    className={cn(
                      "h-full rounded-full transition-colors",
                      steps[i + 1].status !== "pending"
                        ? "bg-[var(--success)]"
                        : "bg-[var(--border)]",
                    )}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Vertical on mobile */}
      <div className="flex flex-col gap-2 sm:hidden">
        {steps.map((step) => {
          const Icon = step.icon;
          const isClickable = step.status === "complete" || step.status === "active";
          const isViewing = step.id === activeStep;

          return (
            <button
              key={step.id}
              type="button"
              onClick={() => isClickable && onStepClick(step.id)}
              disabled={!isClickable}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 transition-all",
                isViewing
                  ? "bg-[var(--primary)]/10"
                  : "hover:bg-[var(--accent)]",
                !isClickable && "opacity-40 pointer-events-none",
              )}
            >
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full border-2 shrink-0",
                  step.status === "complete"
                    ? "border-[var(--success)] bg-[var(--success)] text-white"
                    : step.status === "active"
                      ? "border-[var(--primary)] text-[var(--primary)]"
                      : "border-[var(--border)] text-[var(--muted-foreground)]",
                )}
              >
                {step.status === "complete" ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <Icon className="h-3.5 w-3.5" />
                )}
              </div>
              <span
                className={cn(
                  "text-sm font-medium",
                  isViewing
                    ? "text-[var(--primary)]"
                    : step.status === "complete"
                      ? "text-[var(--foreground)]"
                      : "text-[var(--muted-foreground)]",
                )}
              >
                {step.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
