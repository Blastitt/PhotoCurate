"use client";

import { useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  ChevronLeft,
  ChevronRight,
  Check,
  Star,
  ImageIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScoreIndicator } from "@/components/sessions/score-indicator";
import { cn, formatFileSize } from "@/lib/utils";
import type { PhotoResponse } from "@/lib/api";

interface PhotoLightboxProps {
  photos: PhotoResponse[];
  currentIndex: number;
  onIndexChange: (idx: number) => void;
  onClose: () => void;
  onStatusChange: (photoId: string, status: string) => void;
}

export function PhotoLightbox({
  photos,
  currentIndex,
  onIndexChange,
  onClose,
  onStatusChange,
}: PhotoLightboxProps) {
  const photo = photos[currentIndex];

  const goNext = useCallback(() => {
    if (currentIndex < photos.length - 1) onIndexChange(currentIndex + 1);
  }, [currentIndex, photos.length, onIndexChange]);

  const goPrev = useCallback(() => {
    if (currentIndex > 0) onIndexChange(currentIndex - 1);
  }, [currentIndex, onIndexChange]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") goNext();
      if (e.key === "ArrowLeft") goPrev();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose, goNext, goPrev]);

  if (!photo) return null;

  const score = photo.ai_score;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex bg-black/90 backdrop-blur-sm"
      >
        {/* Close */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="absolute right-4 top-4 z-10 text-white/80 hover:text-white hover:bg-white/10"
        >
          <X className="h-5 w-5" />
        </Button>

        {/* Nav counter */}
        <div className="absolute left-4 top-4 z-10 text-sm text-white/60">
          {currentIndex + 1} / {photos.length}
        </div>

        {/* Previous */}
        <button
          type="button"
          onClick={goPrev}
          disabled={currentIndex === 0}
          className="absolute left-2 top-1/2 z-10 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-black/50 text-white/80 hover:bg-black/70 disabled:opacity-30 transition-all"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>

        {/* Next */}
        <button
          type="button"
          onClick={goNext}
          disabled={currentIndex === photos.length - 1}
          className="absolute right-2 top-1/2 z-10 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-black/50 text-white/80 hover:bg-black/70 disabled:opacity-30 transition-all sm:right-80"
        >
          <ChevronRight className="h-5 w-5" />
        </button>

        {/* Main image */}
        <div className="flex flex-1 items-center justify-center p-4 sm:pr-80">
          <AnimatePresence mode="wait">
            <motion.div
              key={photo.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="relative max-h-full max-w-full"
            >
              {photo.preview_url ? (
                <img
                  src={photo.preview_url}
                  alt={photo.filename}
                  className="max-h-[85vh] max-w-full rounded-lg object-contain"
                />
              ) : (
                <div className="flex h-80 w-80 items-center justify-center rounded-lg bg-[var(--muted)]">
                  <ImageIcon className="h-16 w-16 text-[var(--muted-foreground)]" />
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Score sidebar */}
        <div className="hidden sm:flex w-76 flex-col border-l border-white/10 bg-black/80 p-6">
          {/* Filename & meta */}
          <div className="mb-6">
            <h3 className="truncate text-base font-semibold text-white">
              {photo.filename}
            </h3>
            <div className="mt-1 flex items-center gap-2 text-xs text-white/50">
              {photo.width && photo.height && (
                <span>
                  {photo.width}×{photo.height}
                </span>
              )}
              {photo.file_size_bytes && (
                <span>{formatFileSize(photo.file_size_bytes)}</span>
              )}
            </div>
            {photo.ai_score?.auto_picked && (
              <Badge className="mt-2 gap-1 bg-[var(--primary)]/20 text-[var(--primary)] border-none">
                <Star className="h-3 w-3 fill-current" />
                Auto-picked
              </Badge>
            )}
          </div>

          {/* Score */}
          {score && (
            <div className="space-y-4">
              <div className="flex items-center justify-center">
                <ScoreIndicator
                  score={score.composite_score}
                  size="lg"
                  showLabel
                />
              </div>

              <div className="space-y-2">
                {score.sharpness != null && (
                  <ScoreRow label="Sharpness" value={score.sharpness} />
                )}
                {score.exposure != null && (
                  <ScoreRow label="Exposure" value={score.exposure} />
                )}
                {score.composition != null && (
                  <ScoreRow label="Composition" value={score.composition} />
                )}
                {score.aesthetic != null && (
                  <ScoreRow label="Aesthetic" value={score.aesthetic} />
                )}
                {score.face_quality != null && (
                  <ScoreRow label="Face Quality" value={score.face_quality} />
                )}
                {score.uniqueness != null && (
                  <ScoreRow label="Uniqueness" value={score.uniqueness} />
                )}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="mt-auto flex gap-2 pt-6">
            <Button
              variant="outline"
              className="flex-1 gap-1 border-white/20 text-white hover:bg-[var(--success)]/20 hover:text-[var(--success)] hover:border-[var(--success)]"
              onClick={() => onStatusChange(photo.id, "gallery_ready")}
            >
              <Check className="h-4 w-4" />
              Approve
            </Button>
            <Button
              variant="outline"
              className="flex-1 gap-1 border-white/20 text-white hover:bg-[var(--destructive)]/20 hover:text-[var(--destructive)] hover:border-[var(--destructive)]"
              onClick={() => onStatusChange(photo.id, "rejected")}
            >
              <X className="h-4 w-4" />
              Reject
            </Button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

function ScoreRow({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 text-xs text-white/60">{label}</span>
      <div className="h-1.5 flex-1 rounded-full bg-white/10">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            value >= 0.7
              ? "bg-[var(--success)]"
              : value >= 0.4
                ? "bg-[var(--warning)]"
                : "bg-[var(--destructive)]",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-right text-xs text-white/80">{pct}</span>
    </div>
  );
}
