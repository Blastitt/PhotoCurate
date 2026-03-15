"use client";

import { useState, useEffect, useCallback } from "react";
import {
  sessions,
  galleries,
  type SessionResponse,
  type PhotoResponse,
  type GalleryResponse,
  ApiError,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Copy, ExternalLink, Lock, ImageIcon } from "lucide-react";
import { statusLabel } from "@/lib/utils";

interface GalleryStepProps {
  session: SessionResponse;
  onSessionUpdate: (s: SessionResponse) => void;
}

export function GalleryStep({ session, onSessionUpdate }: GalleryStepProps) {
  const [photos, setPhotos] = useState<PhotoResponse[]>([]);
  const [gallery, setGallery] = useState<GalleryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  // Config
  const [usePin, setUsePin] = useState(false);
  const [pin, setPin] = useState("");
  const [maxSelections, setMaxSelections] = useState(20);
  const [selectedPhotoIds, setSelectedPhotoIds] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const photoList = await sessions.listPhotos(session.id);
      setPhotos(photoList);

      // Auto-select approved/auto-picked photos
      const approved = photoList.filter(
        (p) =>
          p.ai_score?.auto_picked ||
          p.status === "gallery_ready" ||
          p.status === "scored",
      );
      setSelectedPhotoIds(approved.map((p) => p.id));
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [session.id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = async () => {
    setError("");
    setCreating(true);
    try {
      const g = await galleries.create(session.id, {
        pin: usePin && pin.length >= 4 ? pin : undefined,
        max_selections: maxSelections,
        photo_ids: selectedPhotoIds.length > 0 ? selectedPhotoIds : undefined,
      });
      setGallery(g);
      const updated = await sessions.get(session.id);
      onSessionUpdate(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create gallery");
    } finally {
      setCreating(false);
    }
  };

  const copyLink = () => {
    if (!gallery?.gallery_url) return;
    navigator.clipboard.writeText(gallery.gallery_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const togglePhoto = (id: string) => {
    setSelectedPhotoIds((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id],
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
      </div>
    );
  }

  // Gallery already created
  if (gallery || session.status === "gallery_shared" || session.status === "selection_complete") {
    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold">Gallery Shared</h3>
          <p className="text-sm text-[var(--muted-foreground)]">
            Your gallery is live and ready for client review.
          </p>
        </div>

        {gallery && (
          <Card>
            <CardContent className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <Badge variant={statusVariant(gallery.status)}>
                  {statusLabel(gallery.status)}
                </Badge>
                {gallery.max_selections && (
                  <span className="text-sm text-[var(--muted-foreground)]">
                    Max {gallery.max_selections} selections
                  </span>
                )}
              </div>

              {gallery.gallery_url && (
                <div className="flex items-center gap-2">
                  <Input
                    readOnly
                    value={gallery.gallery_url}
                    className="font-mono text-sm"
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={copyLink}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() =>
                      window.open(gallery.gallery_url!, "_blank")
                    }
                  >
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                </div>
              )}

              {copied && (
                <p className="text-xs text-[var(--success)]">
                  Link copied to clipboard!
                </p>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    );
  }

  // Gallery setup
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Gallery Setup</h3>
        <p className="text-sm text-[var(--muted-foreground)]">
          Configure and create a shareable gallery for your client.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Photo selection */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Gallery Photos ({selectedPhotoIds.length} selected)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2 mb-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setSelectedPhotoIds(
                    photos
                      .filter(
                        (p) =>
                          p.ai_score?.auto_picked ||
                          p.status === "gallery_ready",
                      )
                      .map((p) => p.id),
                  )
                }
              >
                Select auto-picked
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedPhotoIds(photos.map((p) => p.id))}
              >
                Select all
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedPhotoIds([])}
              >
                Clear
              </Button>
            </div>
            <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-2 max-h-80 overflow-y-auto">
              {photos.map((p) => {
                const isSelected = selectedPhotoIds.includes(p.id);
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => togglePhoto(p.id)}
                    className={`relative aspect-square rounded-lg overflow-hidden border-2 transition-all ${
                      isSelected
                        ? "border-[var(--primary)] ring-1 ring-[var(--primary)]"
                        : "border-transparent hover:border-[var(--border)]"
                    }`}
                  >
                    <div className="h-full w-full bg-[var(--muted)] flex items-center justify-center">
                      {p.thumbnail_url ? (
                        <img
                          src={p.thumbnail_url}
                          alt={p.filename}
                          className="h-full w-full object-cover"
                          style={p.face_center_x != null && p.face_center_y != null
                            ? { objectPosition: `${p.face_center_x * 100}% ${p.face_center_y * 100}%` }
                            : undefined}
                        />
                      ) : (
                        <ImageIcon className="h-4 w-4 text-[var(--muted-foreground)]" />
                      )}
                    </div>
                    {isSelected && (
                      <div className="absolute inset-0 bg-[var(--primary)]/20 flex items-center justify-center">
                        <div className="h-5 w-5 rounded-full bg-[var(--primary)] flex items-center justify-center">
                          <span className="text-[10px] font-bold text-[var(--primary-foreground)]">
                            ✓
                          </span>
                        </div>
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Settings */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* PIN protection */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4 text-[var(--muted-foreground)]" />
                  <Label>PIN protection</Label>
                </div>
                <Switch checked={usePin} onCheckedChange={setUsePin} />
              </div>

              {usePin && (
                <Input
                  type="text"
                  maxLength={6}
                  placeholder="4-6 digit PIN"
                  value={pin}
                  onChange={(e) =>
                    setPin(e.target.value.replace(/\D/g, "").slice(0, 6))
                  }
                />
              )}

              {/* Max selections */}
              <div className="space-y-2">
                <Label>
                  Max selections:{" "}
                  <span className="text-[var(--primary)] font-semibold">
                    {maxSelections}
                  </span>
                </Label>
                <Slider
                  min={1}
                  max={selectedPhotoIds.length || 50}
                  step={1}
                  value={[maxSelections]}
                  onValueChange={([v]) => setMaxSelections(v)}
                />
              </div>
            </CardContent>
          </Card>

          {error && (
            <p className="text-sm text-[var(--destructive)]">{error}</p>
          )}

          <Button
            onClick={handleCreate}
            disabled={creating || selectedPhotoIds.length === 0}
            className="w-full gap-2"
            size="lg"
          >
            {creating ? "Creating..." : "Create Gallery"}
          </Button>
        </div>
      </div>
    </div>
  );
}
