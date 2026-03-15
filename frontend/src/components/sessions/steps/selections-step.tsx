"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  galleries,
  sessions,
  type SessionResponse,
  type SelectionDetailResponse,
  type PhotoResponse,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Heart,
  Mail,
  User,
  MessageSquare,
  Clock,
  ImageIcon,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";
import { formatDate } from "@/lib/utils";

interface SelectionsStepProps {
  session: SessionResponse;
  onSessionUpdate: (s: SessionResponse) => void;
  onNavigateToDeliver: () => void;
}

export function SelectionsStep({
  session,
  onSessionUpdate,
  onNavigateToDeliver,
}: SelectionsStepProps) {
  const [selections, setSelections] = useState<SelectionDetailResponse[]>([]);
  const [photos, setPhotos] = useState<PhotoResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [sels, allPhotos] = await Promise.all([
        galleries.getSelections(session.id),
        sessions.listPhotos(session.id),
      ]);
      setSelections(sels);
      setPhotos(allPhotos);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [session.id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  if (selections.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center py-16 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--primary)]/10">
            <Heart className="h-7 w-7 text-[var(--primary)]" />
          </div>
          <h3 className="mb-1 text-lg font-semibold">
            Waiting for client selections
          </h3>
          <p className="max-w-sm text-sm text-[var(--muted-foreground)]">
            Your client hasn&apos;t submitted their photo selections yet. They
            will choose their favorites from the shared gallery link.
          </p>
        </CardContent>
      </Card>
    );
  }

  // Build photo lookup for thumbnails
  const photoMap = new Map(photos.map((p) => [p.id, p]));

  return (
    <div className="space-y-6">
      {selections.map((sel, idx) => {
        const selectedPhotos = sel.photo_ids
          .map((id) => photoMap.get(id))
          .filter(Boolean) as PhotoResponse[];

        return (
          <motion.div
            key={sel.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.05 }}
          >
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--success)]/10">
                      <CheckCircle2 className="h-5 w-5 text-[var(--success)]" />
                    </div>
                    <div>
                      <CardTitle className="text-base">
                        Client Selection
                      </CardTitle>
                      <div className="flex items-center gap-3 text-xs text-[var(--muted-foreground)]">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDate(sel.submitted_at)}
                        </span>
                        <span className="flex items-center gap-1">
                          <ImageIcon className="h-3 w-3" />
                          {sel.photo_ids.length} photos selected
                        </span>
                      </div>
                    </div>
                  </div>
                  <Badge variant="default">
                    {sel.photo_ids.length} photos
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                {/* Client info */}
                {(sel.client_name || sel.client_email) && (
                  <div className="flex flex-wrap gap-4 rounded-lg bg-[var(--muted)]/30 p-3">
                    {sel.client_name && (
                      <span className="flex items-center gap-1.5 text-sm">
                        <User className="h-4 w-4 text-[var(--muted-foreground)]" />
                        {sel.client_name}
                      </span>
                    )}
                    {sel.client_email && (
                      <span className="flex items-center gap-1.5 text-sm">
                        <Mail className="h-4 w-4 text-[var(--muted-foreground)]" />
                        {sel.client_email}
                      </span>
                    )}
                  </div>
                )}

                {/* Client notes */}
                {sel.notes && (
                  <div className="rounded-lg border border-[var(--border)] p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm font-medium text-[var(--muted-foreground)]">
                      <MessageSquare className="h-4 w-4" />
                      Client Note
                    </div>
                    <p className="text-sm leading-relaxed">{sel.notes}</p>
                  </div>
                )}

                {/* Selected photos grid */}
                <div>
                  <p className="mb-3 text-sm font-medium">Selected Photos</p>
                  <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6">
                    <AnimatePresence>
                      {selectedPhotos.map((photo, i) => (
                        <motion.div
                          key={photo.id}
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: i * 0.02 }}
                          className="group relative aspect-square overflow-hidden rounded-lg bg-[var(--muted)]"
                        >
                          {photo.thumbnail_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={photo.thumbnail_url}
                              alt={photo.filename}
                              className="h-full w-full object-cover"
                              loading="lazy"
                              style={photo.face_center_x != null && photo.face_center_y != null
                                ? { objectPosition: `${photo.face_center_x * 100}% ${photo.face_center_y * 100}%` }
                                : undefined}
                            />
                          ) : (
                            <div className="flex h-full items-center justify-center">
                              <ImageIcon className="h-5 w-5 text-[var(--muted-foreground)]" />
                            </div>
                          )}
                          {/* Filename on hover */}
                          <div className="absolute inset-x-0 bottom-0 bg-black/60 px-1.5 py-1 text-[10px] text-white opacity-0 transition-opacity group-hover:opacity-100 truncate">
                            {photo.filename}
                          </div>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        );
      })}

      {/* Proceed to delivery */}
      <div className="flex justify-end">
        <Button onClick={onNavigateToDeliver}>
          Proceed to Delivery
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
