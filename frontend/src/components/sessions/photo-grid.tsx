"use client";

import { cn } from "@/lib/utils";
import { ScoreIndicator } from "@/components/sessions/score-indicator";
import { Skeleton } from "@/components/ui/skeleton";
import { motion } from "framer-motion";
import { Check, X, Expand, Star, ImageIcon } from "lucide-react";
import type { PhotoResponse } from "@/lib/api";

interface PhotoGridProps {
  photos: PhotoResponse[];
  loading: boolean;
  selected: Set<string>;
  onToggleSelect: (id: string) => void;
  onPhotoClick: (index: number) => void;
  onStatusChange: (photoId: string, status: string) => void;
}

export function PhotoGrid({
  photos,
  loading,
  selected,
  onToggleSelect,
  onPhotoClick,
  onStatusChange,
}: PhotoGridProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        {Array.from({ length: 12 }).map((_, i) => (
          <Skeleton key={i} className="aspect-square w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (photos.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--border)] py-16">
        <ImageIcon className="h-10 w-10 text-[var(--muted-foreground)] mb-3" />
        <p className="text-sm text-[var(--muted-foreground)]">No photos match your filters</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
      {photos.map((photo, i) => (
        <PhotoCard
          key={photo.id}
          photo={photo}
          index={i}
          isSelected={selected.has(photo.id)}
          onToggleSelect={() => onToggleSelect(photo.id)}
          onClick={() => onPhotoClick(i)}
          onStatusChange={(status) => onStatusChange(photo.id, status)}
        />
      ))}
    </div>
  );
}

function PhotoCard({
  photo,
  index,
  isSelected,
  onToggleSelect,
  onClick,
  onStatusChange,
}: {
  photo: PhotoResponse;
  index: number;
  isSelected: boolean;
  onToggleSelect: () => void;
  onClick: () => void;
  onStatusChange: (status: string) => void;
}) {
  const score = photo.ai_score?.composite_score;
  const isAutoPicked = photo.ai_score?.auto_picked;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: Math.min(index * 0.02, 0.3) }}
      className="group relative"
    >
      <div
        className={cn(
          "relative aspect-square cursor-pointer overflow-hidden rounded-xl border-2 transition-all duration-150",
          isSelected
            ? "border-[var(--primary)] ring-2 ring-[var(--primary)]/30"
            : "border-transparent hover:border-[var(--border)]",
          isAutoPicked && !isSelected && "ring-1 ring-[var(--primary)]/20",
        )}
      >
        {/* Image */}
        <div className="h-full w-full bg-[var(--muted)]">
          {photo.thumbnail_url ? (
            <img
              src={photo.thumbnail_url}
              alt={photo.filename}
              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
              style={photo.face_center_x != null && photo.face_center_y != null
                ? { objectPosition: `${photo.face_center_x * 100}% ${photo.face_center_y * 100}%` }
                : undefined}
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <ImageIcon className="h-8 w-8 text-[var(--muted-foreground)]" />
            </div>
          )}
        </div>

        {/* Auto-picked star */}
        {isAutoPicked && (
          <div className="absolute top-2 right-2">
            <Star className="h-4 w-4 fill-[var(--primary)] text-[var(--primary)]" />
          </div>
        )}

        {/* Score badge */}
        {score != null && (
          <div className="absolute bottom-2 left-2">
            <ScoreIndicator score={score} size="sm" />
          </div>
        )}

        {/* Selection checkbox */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onToggleSelect();
          }}
          className={cn(
            "absolute top-2 left-2 flex h-5 w-5 items-center justify-center rounded border transition-all",
            isSelected
              ? "border-[var(--primary)] bg-[var(--primary)] text-[var(--primary-foreground)]"
              : "border-white/60 bg-black/30 text-white opacity-0 group-hover:opacity-100",
          )}
        >
          {isSelected && <Check className="h-3 w-3" strokeWidth={3} />}
        </button>

        {/* Hover overlay with actions */}
        <div
          className="absolute inset-0 flex items-center justify-center gap-2 bg-black/40 opacity-0 transition-opacity group-hover:opacity-100"
          onClick={onClick}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onStatusChange("gallery_ready");
            }}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--success)] text-white hover:brightness-110 transition-all"
            title="Approve"
          >
            <Check className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onClick();
            }}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-white/20 text-white hover:bg-white/30 transition-all"
            title="View"
          >
            <Expand className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onStatusChange("rejected");
            }}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--destructive)] text-white hover:brightness-110 transition-all"
            title="Reject"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Hover score breakdown */}
        {photo.ai_score && (
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent px-2 pb-2 pt-6 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
            <div className="grid grid-cols-3 gap-x-2 gap-y-0.5 text-[10px] text-white/80">
              {photo.ai_score.sharpness != null && (
                <ScoreBar label="Sharp" value={photo.ai_score.sharpness} />
              )}
              {photo.ai_score.exposure != null && (
                <ScoreBar label="Expos" value={photo.ai_score.exposure} />
              )}
              {photo.ai_score.composition != null && (
                <ScoreBar label="Comp" value={photo.ai_score.composition} />
              )}
              {photo.ai_score.aesthetic != null && (
                <ScoreBar label="Aesth" value={photo.ai_score.aesthetic} />
              )}
              {photo.ai_score.face_quality != null && (
                <ScoreBar label="Face" value={photo.ai_score.face_quality} />
              )}
              {photo.ai_score.uniqueness != null && (
                <ScoreBar label="Uniq" value={photo.ai_score.uniqueness} />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Filename */}
      <p className="mt-1 truncate px-1 text-xs text-[var(--muted-foreground)]">
        {photo.filename}
      </p>
    </motion.div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-1">
      <span className="w-8 truncate">{label}</span>
      <div className="h-1 flex-1 rounded-full bg-white/20">
        <div
          className="h-full rounded-full bg-white/80"
          style={{ width: `${value * 100}%` }}
        />
      </div>
    </div>
  );
}
