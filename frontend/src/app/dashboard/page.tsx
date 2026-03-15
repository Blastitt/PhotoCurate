"use client";

import { useEffect, useState } from "react";
import { sessions, type SessionResponse } from "@/lib/api";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Camera,
  FolderOpen,
  Cpu,
  CheckCircle2,
  ArrowRight,
  Plus,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, statusLabel } from "@/lib/utils";

export default function DashboardPage() {
  const [allSessions, setAllSessions] = useState<SessionResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    sessions
      .list()
      .then(setAllSessions)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const recent = allSessions.slice(0, 6);
  const stats = {
    total: allSessions.length,
    processing: allSessions.filter((s) => s.status === "processing").length,
    curated: allSessions.filter(
      (s) => s.status === "curated" || s.status === "gallery_shared",
    ).length,
    delivered: allSessions.filter((s) => s.status === "delivered").length,
  };

  const statCards = [
    { label: "Total Sessions", value: stats.total, icon: FolderOpen, color: "var(--primary)" },
    { label: "Processing", value: stats.processing, icon: Cpu, color: "var(--info)" },
    { label: "Curated", value: stats.curated, icon: CheckCircle2, color: "var(--success)" },
    { label: "Delivered", value: stats.delivered, icon: Camera, color: "var(--accent)" },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            Welcome back. Here&apos;s what&apos;s happening.
          </p>
        </div>
        <Link href="/dashboard/sessions/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Session
          </Button>
        </Link>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {loading
          ? Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-[104px] rounded-xl" />
            ))
          : statCards.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card>
                  <CardContent className="flex items-center gap-4 p-5">
                    <div
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                      style={{ backgroundColor: `color-mix(in srgb, ${s.color} 15%, transparent)` }}
                    >
                      <s.icon className="h-5 w-5" style={{ color: s.color }} />
                    </div>
                    <div>
                      <p className="text-sm text-[var(--muted-foreground)]">{s.label}</p>
                      <p className="text-2xl font-bold">{s.value}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
      </div>

      {/* Recent sessions */}
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle className="text-lg">Recent Sessions</CardTitle>
          <Link href="/dashboard/sessions">
            <Button variant="ghost" size="sm">
              View all
              <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-16 rounded-lg" />
              ))}
            </div>
          ) : recent.length === 0 ? (
            <div className="flex flex-col items-center py-10 text-center">
              <FolderOpen className="mb-3 h-10 w-10 text-[var(--muted-foreground)]" />
              <p className="mb-1 font-medium">No sessions yet</p>
              <p className="text-sm text-[var(--muted-foreground)]">
                Create your first session to start curating photos.
              </p>
              <Link href="/dashboard/sessions/new">
                <Button className="mt-4" size="sm">
                  <Plus className="mr-1 h-4 w-4" />
                  Create session
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {recent.map((session, i) => (
                <motion.div
                  key={session.id}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <Link
                    href={`/dashboard/sessions/${session.id}`}
                    className="flex items-center justify-between rounded-lg border border-[var(--border)] p-3.5 transition-colors hover:bg-[var(--accent)]/5"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium">{session.title}</p>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {formatDate(session.shoot_date)} &middot;{" "}
                        {session.auto_pick_count} auto-picks
                      </p>
                    </div>
                    <Badge variant={statusVariant(session.status)}>
                      {statusLabel(session.status)}
                    </Badge>
                  </Link>
                </motion.div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
