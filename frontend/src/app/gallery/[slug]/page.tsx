"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Lock,
  Check,
  ChevronLeft,
  ChevronRight,
  X,
  ImageIcon,
  Send,
} from "lucide-react";
import {
  publicGallery,
  type GalleryPublicResponse,
  type GalleryPhotoPublic,
  ApiError,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

export default function PublicGalleryPage() {
  const { slug } = useParams<{ slug: string }>();
  const [gallery, setGallery] = useState<GalleryPublicResponse | null>(null);
  const [needsPin, setNeedsPin] = useState(false);
  const [pin, setPin] = useState("");
  const [pinError, setPinError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadGallery = useCallback(async () => {
    try {
      const storedToken = localStorage.getItem(`gallery_token_${slug}`) ?? undefined;
      const data = await publicGallery.get(slug, storedToken);
      setGallery(data);
      setNeedsPin(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setNeedsPin(true);
      } else {
        setError(
          err instanceof ApiError ? err.message : "Gallery not found",
        );
      }
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    loadGallery();
  }, [loadGallery]);

  async function handlePinSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPinError("");
    try {
      const result = await publicGallery.verifyPin(slug, pin);
      if (result.valid) {
        if (result.token) {
          localStorage.setItem(`gallery_token_${slug}`, result.token);
        }
        await loadGallery();
      } else {
        setPinError("Invalid PIN. Please try again.");
      }
    } catch {
      setPinError("Verification failed. Please try again.");
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
        <motion.div
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          className="text-[var(--muted-foreground)]"
        >
          Loading gallery...
        </motion.div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
        <div className="text-center">
          <ImageIcon className="mx-auto mb-3 h-12 w-12 text-[var(--muted-foreground)]" />
          <h1 className="mb-2 text-2xl font-bold">Gallery Not Found</h1>
          <p className="text-[var(--muted-foreground)]">{error}</p>
        </div>
      </div>
    );
  }

  if (needsPin) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--background)] p-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className="w-full max-w-sm shadow-2xl">
            <CardContent className="p-8 text-center">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--primary)]/10">
                <Lock className="h-6 w-6 text-[var(--primary)]" />
              </div>
              <h1 className="mb-1 text-xl font-bold">Protected Gallery</h1>
              <p className="mb-6 text-sm text-[var(--muted-foreground)]">
                Enter the PIN to view this gallery.
              </p>
              <form onSubmit={handlePinSubmit} className="space-y-4">
                <Input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  required
                  value={pin}
                  onChange={(e) =>
                    setPin(e.target.value.replace(/\D/g, "").slice(0, 6))
                  }
                  placeholder="Enter PIN"
                  className="text-center text-lg tracking-[0.3em]"
                />
                {pinError && (
                  <p className="text-sm text-[var(--destructive)]">{pinError}</p>
                )}
                <Button type="submit" className="w-full">
                  View Gallery
                </Button>
              </form>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }

  if (!gallery) return null;

  return <GalleryView gallery={gallery} slug={slug} />;
}

// ─── Gallery View ────────────────────────────────────────────────────────────

function GalleryView({
  gallery,
  slug,
}: {
  gallery: GalleryPublicResponse;
  slug: string;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [lightboxPhoto, setLightboxPhoto] = useState<GalleryPhotoPublic | null>(
    null,
  );
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [clientName, setClientName] = useState("");
  const [clientEmail, setClientEmail] = useState("");
  const [notes, setNotes] = useState("");
  const [showSubmitForm, setShowSubmitForm] = useState(false);

  const maxSelections = gallery.max_selections;
  const photos = gallery.photos.sort((a, b) => a.sort_order - b.sort_order);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (maxSelections && next.size >= maxSelections) return prev;
        next.add(id);
      }
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (selected.size === 0) return;
    setSubmitting(true);
    try {
      await publicGallery.submitSelection(slug, {
        photo_ids: Array.from(selected),
        client_name: clientName || undefined,
        client_email: clientEmail || undefined,
        notes: notes || undefined,
      });
      setSubmitted(true);
    } catch {
      alert("Failed to submit selection. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="text-center"
        >
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[var(--success)]/10">
            <Check className="h-8 w-8 text-[var(--success)]" />
          </div>
          <h1 className="mb-2 text-2xl font-bold">Selection Submitted!</h1>
          <p className="text-[var(--muted-foreground)]">
            You selected {selected.size} photos. Your photographer will be
            notified.
          </p>
        </motion.div>
      </div>
    );
  }

  if (gallery.status === "selection_complete") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
        <div className="text-center">
          <h1 className="mb-2 text-2xl font-bold">Selection Complete</h1>
          <p className="text-[var(--muted-foreground)]">
            Selections have already been submitted for this gallery.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div>
            <h1 className="text-lg font-bold tracking-tight">Photo Gallery</h1>
            <p className="text-xs text-[var(--muted-foreground)]">
              {selected.size} selected
              {maxSelections ? ` / ${maxSelections} max` : ""}
            </p>
          </div>
          <AnimatePresence>
            {selected.size > 0 && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
              >
                <Button onClick={() => setShowSubmitForm(true)}>
                  <Send className="mr-2 h-4 w-4" />
                  Submit ({selected.size})
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </header>

      {/* Photo Grid */}
      <div className="mx-auto max-w-7xl p-4">
        {photos.length === 0 ? (
          <div className="flex flex-col items-center py-20 text-center">
            <ImageIcon className="mb-3 h-12 w-12 text-[var(--muted-foreground)]" />
            <p className="text-[var(--muted-foreground)]">
              No photos available yet.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {photos.map((photo, i) => (
              <motion.div
                key={photo.id}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.02 }}
                className={`group relative cursor-pointer overflow-hidden rounded-lg border-2 transition-all ${
                  selected.has(photo.id)
                    ? "border-[var(--primary)] ring-2 ring-[var(--primary)]/30"
                    : "border-transparent hover:border-[var(--border)]"
                }`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <div
                  onClick={() => setLightboxPhoto(photo)}
                  className="aspect-[3/2] bg-[var(--muted)]"
                >
                  {photo.preview_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={photo.preview_url}
                      alt=""
                      className="h-full w-full object-cover"
                      loading="lazy"
                      style={photo.face_center_x != null && photo.face_center_y != null
                        ? { objectPosition: `${photo.face_center_x * 100}% ${photo.face_center_y * 100}%` }
                        : undefined}
                    />
                  ) : photo.thumbnail_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={photo.thumbnail_url}
                      alt=""
                      className="h-full w-full object-cover"
                      loading="lazy"
                      style={photo.face_center_x != null && photo.face_center_y != null
                        ? { objectPosition: `${photo.face_center_x * 100}% ${photo.face_center_y * 100}%` }
                        : undefined}
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center">
                      <ImageIcon className="h-6 w-6 text-[var(--muted-foreground)]" />
                    </div>
                  )}
                </div>

                {/* Select button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleSelect(photo.id);
                  }}
                  className={`absolute top-2 right-2 flex h-7 w-7 items-center justify-center rounded-full text-sm transition-all ${
                    selected.has(photo.id)
                      ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                      : "bg-black/40 text-white opacity-0 group-hover:opacity-100"
                  }`}
                >
                  {selected.has(photo.id) ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    "+"
                  )}
                </button>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Floating selection counter (mobile) */}
      <AnimatePresence>
        {selected.size > 0 && (
          <motion.div
            initial={{ y: 80, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 80, opacity: 0 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 sm:hidden z-20"
          >
            <Button
              onClick={() => setShowSubmitForm(true)}
              className="rounded-full px-6 shadow-xl"
            >
              <Send className="mr-2 h-4 w-4" />
              Submit {selected.size} photos
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Lightbox */}
      <AnimatePresence>
        {lightboxPhoto && (
          <GalleryLightbox
            photo={lightboxPhoto}
            photos={photos}
            selected={selected}
            onSelect={toggleSelect}
            onClose={() => setLightboxPhoto(null)}
            onNavigate={setLightboxPhoto}
          />
        )}
      </AnimatePresence>

      {/* Submit Form Dialog */}
      <Dialog open={showSubmitForm} onOpenChange={setShowSubmitForm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Submit Your Selections</DialogTitle>
            <DialogDescription>
              You&apos;ve selected {selected.size} photos.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              placeholder="Your name (optional)"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
            />
            <Input
              type="email"
              placeholder="Your email (optional)"
              value={clientEmail}
              onChange={(e) => setClientEmail(e.target.value)}
            />
            <Textarea
              placeholder="Any notes for your photographer? (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
            />
            <div className="flex gap-3 pt-1">
              <Button type="submit" disabled={submitting} className="flex-1">
                {submitting ? "Submitting..." : "Confirm Selection"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowSubmitForm(false)}
              >
                Cancel
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── Gallery Lightbox ────────────────────────────────────────────────────────

function GalleryLightbox({
  photo,
  photos,
  selected,
  onSelect,
  onClose,
  onNavigate,
}: {
  photo: GalleryPhotoPublic;
  photos: GalleryPhotoPublic[];
  selected: Set<string>;
  onSelect: (id: string) => void;
  onClose: () => void;
  onNavigate: (photo: GalleryPhotoPublic) => void;
}) {
  const idx = photos.findIndex((p) => p.id === photo.id);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft" && idx > 0) onNavigate(photos[idx - 1]);
      if (e.key === "ArrowRight" && idx < photos.length - 1)
        onNavigate(photos[idx + 1]);
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [idx, photos, onClose, onNavigate]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/95"
    >
      {/* Close */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white/80 hover:bg-white/20 hover:text-white transition-colors"
      >
        <X className="h-5 w-5" />
      </button>

      {/* Nav arrows */}
      {idx > 0 && (
        <button
          onClick={() => onNavigate(photos[idx - 1])}
          className="absolute left-4 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white/80 hover:bg-white/20 hover:text-white transition-colors"
        >
          <ChevronLeft className="h-6 w-6" />
        </button>
      )}
      {idx < photos.length - 1 && (
        <button
          onClick={() => onNavigate(photos[idx + 1])}
          className="absolute right-4 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white/80 hover:bg-white/20 hover:text-white transition-colors"
        >
          <ChevronRight className="h-6 w-6" />
        </button>
      )}

      {/* Image */}
      <AnimatePresence mode="wait">
        <motion.div
          key={photo.id}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="flex max-h-[85vh] max-w-[90vw] flex-col items-center"
        >
          {photo.preview_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={photo.preview_url}
              alt=""
              className="max-h-[80vh] max-w-full rounded object-contain"
            />
          ) : (
            <div className="flex h-96 w-96 items-center justify-center rounded bg-white/5 text-white/30">
              <ImageIcon className="h-12 w-12" />
            </div>
          )}

          {/* Select button */}
          <button
            onClick={() => onSelect(photo.id)}
            className={`mt-4 flex items-center gap-2 rounded-full px-6 py-2 text-sm font-medium transition-colors ${
              selected.has(photo.id)
                ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                : "bg-white/20 text-white hover:bg-white/30"
            }`}
          >
            {selected.has(photo.id) ? (
              <>
                <Check className="h-4 w-4" /> Selected
              </>
            ) : (
              "Select"
            )}
          </button>
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}
