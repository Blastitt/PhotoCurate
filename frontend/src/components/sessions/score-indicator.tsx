"use client";

import { cn } from "@/lib/utils";

interface ScoreIndicatorProps {
  score: number;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

function scoreColor(score: number): string {
  if (score >= 0.7) return "text-[var(--success)] bg-[var(--success)]";
  if (score >= 0.4) return "text-[var(--warning)] bg-[var(--warning)]";
  return "text-[var(--destructive)] bg-[var(--destructive)]";
}

export function ScoreIndicator({
  score,
  size = "md",
  showLabel = false,
}: ScoreIndicatorProps) {
  const pct = Math.round(score * 100);
  const colorClasses = scoreColor(score);
  const [textColor, bgColor] = colorClasses.split(" ");

  if (size === "sm") {
    return (
      <div
        className={cn(
          "inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-bold",
          bgColor + "/20",
          textColor,
        )}
      >
        {pct}
      </div>
    );
  }

  if (size === "lg") {
    return (
      <div className="flex flex-col items-center gap-1">
        {/* Circular gauge */}
        <div className="relative h-16 w-16">
          <svg className="h-full w-full -rotate-90" viewBox="0 0 36 36">
            <path
              d="M18 2.0845
                a 15.9155 15.9155 0 0 1 0 31.831
                a 15.9155 15.9155 0 0 1 0 -31.831"
              fill="none"
              stroke="var(--border)"
              strokeWidth="3"
            />
            <path
              d="M18 2.0845
                a 15.9155 15.9155 0 0 1 0 31.831
                a 15.9155 15.9155 0 0 1 0 -31.831"
              fill="none"
              className={cn(
                "transition-all duration-500",
                score >= 0.7
                  ? "stroke-[var(--success)]"
                  : score >= 0.4
                    ? "stroke-[var(--warning)]"
                    : "stroke-[var(--destructive)]",
              )}
              strokeWidth="3"
              strokeDasharray={`${score * 100}, 100`}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={cn("text-lg font-bold", textColor)}>{pct}</span>
          </div>
        </div>
        {showLabel && (
          <span className="text-xs text-[var(--muted-foreground)]">Score</span>
        )}
      </div>
    );
  }

  // Medium (default)
  return (
    <div className="relative h-10 w-10">
      <svg className="h-full w-full -rotate-90" viewBox="0 0 36 36">
        <path
          d="M18 2.0845
            a 15.9155 15.9155 0 0 1 0 31.831
            a 15.9155 15.9155 0 0 1 0 -31.831"
          fill="none"
          stroke="var(--border)"
          strokeWidth="3"
        />
        <path
          d="M18 2.0845
            a 15.9155 15.9155 0 0 1 0 31.831
            a 15.9155 15.9155 0 0 1 0 -31.831"
          fill="none"
          className={cn(
            "transition-all duration-500",
            score >= 0.7
              ? "stroke-[var(--success)]"
              : score >= 0.4
                ? "stroke-[var(--warning)]"
                : "stroke-[var(--destructive)]",
          )}
          strokeWidth="3"
          strokeDasharray={`${score * 100}, 100`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className={cn("text-xs font-bold", textColor)}>{pct}</span>
      </div>
    </div>
  );
}
