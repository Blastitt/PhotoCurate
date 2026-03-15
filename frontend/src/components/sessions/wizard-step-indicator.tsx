"use client";

import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface StepConfig {
  label: string;
  icon?: React.ReactNode;
}

interface WizardStepIndicatorProps {
  steps: StepConfig[];
  currentStep: number;
}

export function WizardStepIndicator({
  steps,
  currentStep,
}: WizardStepIndicatorProps) {
  return (
    <div className="flex items-center justify-center gap-0">
      {steps.map((step, i) => {
        const isComplete = i < currentStep;
        const isActive = i === currentStep;

        return (
          <div key={i} className="flex items-center">
            {/* Step node */}
            <div className="flex flex-col items-center gap-1.5">
              <motion.div
                animate={{
                  scale: isActive ? 1 : 0.9,
                }}
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors duration-200",
                  isComplete &&
                    "border-[var(--primary)] bg-[var(--primary)] text-[var(--primary-foreground)]",
                  isActive &&
                    "border-[var(--primary)] bg-transparent text-[var(--primary)] animate-pulse-ring",
                  !isComplete &&
                    !isActive &&
                    "border-[var(--border)] bg-transparent text-[var(--muted-foreground)]",
                )}
              >
                {isComplete ? <Check className="h-4 w-4" /> : i + 1}
              </motion.div>
              <span
                className={cn(
                  "text-xs font-medium whitespace-nowrap",
                  isActive
                    ? "text-[var(--primary)]"
                    : isComplete
                      ? "text-[var(--foreground)]"
                      : "text-[var(--muted-foreground)]",
                )}
              >
                {step.label}
              </span>
            </div>

            {/* Connector line */}
            {i < steps.length - 1 && (
              <div className="mx-2 mt-[-20px] h-0.5 w-8 sm:w-12 lg:w-16">
                <div
                  className={cn(
                    "h-full rounded-full transition-colors",
                    i < currentStep
                      ? "bg-[var(--primary)]"
                      : "bg-[var(--border)]",
                  )}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
