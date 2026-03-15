"use client";

import { useState } from "react";
import { galleries, type SessionResponse, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Truck, Cloud, CheckCircle2, XCircle } from "lucide-react";

interface DeliverStepProps {
  session: SessionResponse;
  onSessionUpdate: (s: SessionResponse) => void;
}

export function DeliverStep({ session, onSessionUpdate }: DeliverStepProps) {
  const [provider, setProvider] = useState("google_drive");
  const [delivering, setDelivering] = useState(false);
  const [error, setError] = useState("");
  const [deliveryStatus, setDeliveryStatus] = useState<string | null>(null);

  const handleDeliver = async () => {
    setError("");
    setDelivering(true);
    try {
      // NOTE: In a real app, gallery ID would come from session data.
      // Using session.id as a proxy since the gallery is linked to this session.
      const delivery = await galleries.deliver(session.id, {
        provider,
      });
      setDeliveryStatus(delivery.status);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Delivery failed",
      );
    } finally {
      setDelivering(false);
    }
  };

  if (session.status === "delivered") {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <CheckCircle2 className="h-6 w-6 text-[var(--success)]" />
          <div>
            <h3 className="text-lg font-semibold">Delivered</h3>
            <p className="text-sm text-[var(--muted-foreground)]">
              All edited photos have been delivered to the client.
            </p>
          </div>
        </div>
        <Card>
          <CardContent className="flex items-center gap-3 p-6">
            <Badge variant="delivered">Complete</Badge>
            <span className="text-sm text-[var(--muted-foreground)]">
              Session delivery is complete.
            </span>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Delivery</h3>
        <p className="text-sm text-[var(--muted-foreground)]">
          Deliver edited photos to your client&apos;s cloud storage.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Cloud className="h-4 w-4" /> Choose delivery method
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Select value={provider} onValueChange={setProvider}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="google_drive">Google Drive</SelectItem>
              <SelectItem value="dropbox">Dropbox</SelectItem>
              <SelectItem value="onedrive">OneDrive</SelectItem>
            </SelectContent>
          </Select>

          {deliveryStatus && (
            <div className="flex items-center gap-2 text-sm">
              {deliveryStatus === "completed" ? (
                <CheckCircle2 className="h-4 w-4 text-[var(--success)]" />
              ) : deliveryStatus === "failed" ? (
                <XCircle className="h-4 w-4 text-[var(--destructive)]" />
              ) : (
                <Truck className="h-4 w-4 text-[var(--primary)] animate-pulse" />
              )}
              <span className="capitalize">{deliveryStatus}</span>
            </div>
          )}

          {error && (
            <p className="text-sm text-[var(--destructive)]">{error}</p>
          )}

          <Button
            onClick={handleDeliver}
            disabled={delivering}
            className="w-full gap-2"
          >
            <Truck className="h-4 w-4" />
            {delivering ? "Delivering..." : "Start Delivery"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
