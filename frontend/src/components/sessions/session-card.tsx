"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Calendar, ImageIcon, ChevronRight } from "lucide-react";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { Badge, statusVariant } from "@/components/ui/badge";
import { cn, formatDate, statusLabel } from "@/lib/utils";
import type { SessionResponse } from "@/lib/api";

interface SessionCardProps {
  session: SessionResponse;
  index?: number;
}

const STATUS_ICONS: Record<string, string> = {
  created: "📋",
  uploading: "⬆️",
  processing: "⚡",
  curated: "✨",
  gallery_shared: "🔗",
  selection_complete: "✅",
  editing: "🖊️",
  delivered: "📦",
};

export function SessionCard({ session, index = 0 }: SessionCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
    >
      <Link href={`/dashboard/sessions/${session.id}`}>
        <Card className="group cursor-pointer overflow-hidden hover:shadow-lg hover:shadow-[var(--primary)]/5 hover:-translate-y-0.5 transition-all duration-200">
          {/* Cover image area */}
          <div className="relative aspect-[16/9] bg-gradient-to-br from-[var(--secondary)] to-[var(--muted)] overflow-hidden">
            {/* Placeholder gradient with session-specific color */}
            <div
              className={cn(
                "absolute inset-0 opacity-30",
                session.status === "delivered"
                  ? "bg-gradient-to-br from-emerald-500/40 to-teal-600/40"
                  : session.status === "processing"
                    ? "bg-gradient-to-br from-amber-500/40 to-orange-600/40"
                    : session.status === "gallery_shared"
                      ? "bg-gradient-to-br from-purple-500/40 to-violet-600/40"
                      : "bg-gradient-to-br from-zinc-500/20 to-zinc-700/20",
              )}
            />

            {/* Center icon */}
            <div className="absolute inset-0 flex items-center justify-center">
              <ImageIcon className="h-10 w-10 text-[var(--muted-foreground)] opacity-30" />
            </div>

            {/* Status badge */}
            <div className="absolute top-3 left-3">
              <Badge variant={statusVariant(session.status)}>
                <span className="mr-1">{STATUS_ICONS[session.status] ?? "📋"}</span>
                {statusLabel(session.status)}
              </Badge>
            </div>

            {/* Hover arrow */}
            <div className="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--primary)] text-[var(--primary-foreground)]">
                <ChevronRight className="h-4 w-4" />
              </div>
            </div>
          </div>

          <CardContent className="p-4">
            <h3 className="font-semibold text-base group-hover:text-[var(--primary)] transition-colors truncate">
              {session.title}
            </h3>

            {session.description && (
              <p className="mt-1 text-sm text-[var(--muted-foreground)] line-clamp-1">
                {session.description}
              </p>
            )}

            <div className="mt-3 flex items-center gap-3 text-xs text-[var(--muted-foreground)]">
              <span className="flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5" />
                {formatDate(session.shoot_date)}
              </span>
              <span className="flex items-center gap-1">
                <ImageIcon className="h-3.5 w-3.5" />
                {session.auto_pick_count} auto-picks
              </span>
            </div>
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
}
