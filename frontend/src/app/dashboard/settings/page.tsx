"use client";

import { useEffect, useState, useCallback } from "react";
import { ExternalLink, RefreshCw, Unplug, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { useFeatures } from "@/lib/features-context";
import { adobe, type AdobeStatusResponse } from "@/lib/api";

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <h1 className="text-2xl font-bold tracking-tight">Settings</h1>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Integrations</h2>
        <AdobeLightroomCard />
      </section>
    </div>
  );
}

function AdobeLightroomCard() {
  const { features, loading: featuresLoading } = useFeatures();
  const [status, setStatus] = useState<AdobeStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState("");

  const enabled = features?.adobe_lightroom ?? false;

  const fetchStatus = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      const s = await adobe.status();
      setStatus(s);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  async function handleConnect() {
    setActionLoading(true);
    setMessage("");
    try {
      const { redirect_url } = await adobe.connect();
      window.location.href = redirect_url;
    } catch (err: any) {
      setMessage(err.message || "Failed to initiate connection");
      setActionLoading(false);
    }
  }

  async function handleDisconnect() {
    setActionLoading(true);
    setMessage("");
    try {
      await adobe.disconnect();
      setStatus(null);
      setMessage("Disconnected from Adobe Lightroom.");
    } catch (err: any) {
      setMessage(err.message || "Failed to disconnect");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleRetry() {
    setActionLoading(true);
    setMessage("");
    try {
      const result = await adobe.retryPending();
      setMessage(`Retried ${result.retried} pending task(s).`);
      await fetchStatus();
    } catch (err: any) {
      setMessage(err.message || "Retry failed");
    } finally {
      setActionLoading(false);
    }
  }

  if (featuresLoading) {
    return <Skeleton className="h-48 rounded-xl" />;
  }

  const isDisabled = !enabled;
  const isConnected = status?.connected ?? false;

  return (
    <Card className={isDisabled ? "opacity-60 pointer-events-none select-none" : ""}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Adobe Lightroom</CardTitle>
            <CardDescription>
              {isDisabled
                ? "Adobe Lightroom integration is not configured. Contact your administrator."
                : "Sync photos with your Adobe Lightroom catalog."}
            </CardDescription>
          </div>
          {isConnected && (
            <Badge variant="outline" className="text-green-600 border-green-600">
              Connected
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {isDisabled ? null : loading ? (
          <Skeleton className="h-10 w-full" />
        ) : isConnected ? (
          <>
            {status?.catalog_id && (
              <p className="text-sm text-[var(--muted-foreground)]">
                Catalog: <span className="font-mono text-xs">{status.catalog_id}</span>
              </p>
            )}

            {(status?.pending_task_count ?? 0) > 0 && (
              <div className="flex items-center gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-3 py-2 text-sm">
                <AlertTriangle className="h-4 w-4 text-yellow-500" />
                <span>
                  {status!.pending_task_count} Lightroom task(s) waiting for authentication.
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRetry}
                  disabled={actionLoading}
                >
                  <RefreshCw className="mr-1 h-3 w-3" />
                  Retry now
                </Button>
              </div>
            )}

            <Button
              variant="destructive"
              size="sm"
              onClick={handleDisconnect}
              disabled={actionLoading}
            >
              <Unplug className="mr-1 h-4 w-4" />
              Disconnect
            </Button>
          </>
        ) : (
          <Button onClick={handleConnect} disabled={actionLoading}>
            <ExternalLink className="mr-2 h-4 w-4" />
            Connect Adobe Lightroom
          </Button>
        )}

        {message && (
          <p className="text-sm text-[var(--muted-foreground)]">{message}</p>
        )}
      </CardContent>
    </Card>
  );
}
