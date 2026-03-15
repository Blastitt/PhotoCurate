"use client";

import { useEffect, useState, useCallback } from "react";
import { sessions, type SessionResponse, type PhotoResponse, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { PhotoGrid } from "@/components/sessions/photo-grid";
import { PhotoFilters, type FilterState } from "@/components/sessions/photo-filters";
import { PhotoLightbox } from "@/components/sessions/photo-lightbox";
import { Share2 } from "lucide-react";

interface ReviewStepProps {
  session: SessionResponse;
  onSessionUpdate: (s: SessionResponse) => void;
  onNavigateToGallery: () => void;
}

export function ReviewStep({
  session,
  onSessionUpdate,
  onNavigateToGallery,
}: ReviewStepProps) {
  const [photos, setPhotos] = useState<PhotoResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null);
  const [filters, setFilters] = useState<FilterState>({
    status: "all",
    sort: "score-desc",
    hasFaces: "all",
  });
  const [updatingPhotos, setUpdatingPhotos] = useState(false);

  const loadPhotos = useCallback(async () => {
    try {
      const data = await sessions.listPhotos(session.id);
      setPhotos(data);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [session.id]);

  useEffect(() => {
    loadPhotos();
  }, [loadPhotos]);

  // Apply filters/sort
  const filteredPhotos = photos
    .filter((p) => {
      if (filters.status !== "all" && p.status !== filters.status) return false;
      if (filters.hasFaces === "yes" && !p.ai_score?.face_quality) return false;
      if (filters.hasFaces === "no" && p.ai_score?.face_quality) return false;
      return true;
    })
    .sort((a, b) => {
      if (filters.sort === "score-desc") {
        return (
          (b.ai_score?.composite_score ?? 0) -
          (a.ai_score?.composite_score ?? 0)
        );
      }
      if (filters.sort === "score-asc") {
        return (
          (a.ai_score?.composite_score ?? 0) -
          (b.ai_score?.composite_score ?? 0)
        );
      }
      if (filters.sort === "name") return a.filename.localeCompare(b.filename);
      // date
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const bulkUpdateStatus = async (status: string) => {
    setUpdatingPhotos(true);
    try {
      await Promise.all(
        Array.from(selected).map((id) =>
          sessions.updatePhoto(id, { status }),
        ),
      );
      await loadPhotos();
      setSelected(new Set());
    } catch {
      // silent
    } finally {
      setUpdatingPhotos(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Review Photos</h3>
          <p className="text-sm text-[var(--muted-foreground)]">
            {photos.length} photos scored ·{" "}
            {photos.filter((p) => p.ai_score?.auto_picked).length} auto-picked
          </p>
        </div>
        <Button onClick={onNavigateToGallery} className="gap-2">
          <Share2 className="h-4 w-4" />
          Create Gallery
        </Button>
      </div>

      <PhotoFilters
        filters={filters}
        onChange={setFilters}
        selectedCount={selected.size}
        onApproveSelected={() => bulkUpdateStatus("gallery_ready")}
        onRejectSelected={() => bulkUpdateStatus("rejected")}
        bulkLoading={updatingPhotos}
      />

      <PhotoGrid
        photos={filteredPhotos}
        loading={loading}
        selected={selected}
        onToggleSelect={toggleSelect}
        onPhotoClick={(idx) => setLightboxIdx(idx)}
        onStatusChange={async (photoId, status) => {
          try {
            await sessions.updatePhoto(photoId, { status });
            await loadPhotos();
          } catch {
            // silent
          }
        }}
      />

      {lightboxIdx !== null && (
        <PhotoLightbox
          photos={filteredPhotos}
          currentIndex={lightboxIdx}
          onIndexChange={setLightboxIdx}
          onClose={() => setLightboxIdx(null)}
          onStatusChange={async (photoId, status) => {
            try {
              await sessions.updatePhoto(photoId, { status });
              await loadPhotos();
            } catch {
              // silent
            }
          }}
        />
      )}
    </div>
  );
}
