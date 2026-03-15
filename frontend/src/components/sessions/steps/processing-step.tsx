"use client";

import { useEffect, useState, useRef } from "react";
import { sessions, type SessionResponse, type PhotoResponse } from "@/lib/api";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Cpu, ImageIcon } from "lucide-react";
import { motion } from "framer-motion";

interface ProcessingStepProps {
  session: SessionResponse;
  onSessionUpdate: (s: SessionResponse) => void;
}

export function ProcessingStep({ session, onSessionUpdate }: ProcessingStepProps) {
  const [photos, setPhotos] = useState<PhotoResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [scoredCount, setScoredCount] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const photoList = await sessions.listPhotos(session.id);
        setPhotos(photoList);
        setTotalCount(photoList.length);

        const scored = photoList.filter(
          (p) =>
            p.status !== "uploaded" &&
            p.status !== "processing",
        ).length;
        setScoredCount(scored);

        // Check if processing is complete
        if (
          photoList.length > 0 &&
          scored === photoList.length
        ) {
          // Refresh session to get updated status
          const updated = await sessions.get(session.id);
          onSessionUpdate(updated);
        }
      } catch {
        // Silently retry on next interval
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 3000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [session.id, onSessionUpdate]);

  const progress = totalCount > 0 ? Math.round((scoredCount / totalCount) * 100) : 0;
  const latestScored = photos
    .filter((p) => p.ai_score)
    .sort((a, b) => {
      const aTime = a.ai_score?.scored_at ?? "";
      const bTime = b.ai_score?.scored_at ?? "";
      return bTime.localeCompare(aTime);
    })[0];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        >
          <Cpu className="h-6 w-6 text-[var(--primary)]" />
        </motion.div>
        <div>
          <h3 className="text-lg font-semibold">AI Processing</h3>
          <p className="text-sm text-[var(--muted-foreground)]">
            Analyzing and scoring your photos...
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span>
            Scoring{" "}
            <span className="font-semibold text-[var(--primary)]">
              {scoredCount}
            </span>{" "}
            of{" "}
            <span className="font-semibold">{totalCount}</span> photos
          </span>
          <Badge variant="processing">{progress}%</Badge>
        </div>
        <Progress value={progress} className="h-3" />
      </div>

      {/* Latest scored photo preview */}
      {latestScored && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-4 rounded-lg bg-[var(--muted)] p-4"
        >
          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-[var(--secondary)] overflow-hidden">
            {latestScored.thumbnail_url ? (
              <img
                src={latestScored.thumbnail_url}
                alt={latestScored.filename}
                className="h-full w-full object-cover"
                style={latestScored.face_center_x != null && latestScored.face_center_y != null
                  ? { objectPosition: `${latestScored.face_center_x * 100}% ${latestScored.face_center_y * 100}%` }
                  : undefined}
              />
            ) : (
              <ImageIcon className="h-6 w-6 text-[var(--muted-foreground)]" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium">
              {latestScored.filename}
            </p>
            <p className="text-xs text-[var(--muted-foreground)]">
              Latest scored · Composite:{" "}
              <span className="text-[var(--primary)] font-semibold">
                {latestScored.ai_score
                  ? (latestScored.ai_score.composite_score * 100).toFixed(0)
                  : "—"}
              </span>
            </p>
          </div>
        </motion.div>
      )}

      {totalCount === 0 && (
        <div className="rounded-lg bg-[var(--muted)] p-6 text-center">
          <p className="text-sm text-[var(--muted-foreground)]">
            Waiting for photos to begin processing...
          </p>
        </div>
      )}
    </div>
  );
}
