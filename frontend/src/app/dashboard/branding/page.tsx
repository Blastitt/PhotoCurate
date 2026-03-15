"use client";

import { useEffect, useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { motion } from "framer-motion";
import { Upload, ImageIcon, Check } from "lucide-react";
import { branding, type BrandingResponse, ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function BrandingPage() {
  const [data, setData] = useState<BrandingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const [opacity, setOpacity] = useState(0.3);
  const [position, setPosition] = useState("bottom-right");
  const [scale, setScale] = useState(0.15);
  const [padding, setPadding] = useState(0.02);
  const [tileRotation, setTileRotation] = useState(45);
  const [tileSpacing, setTileSpacing] = useState(0.5);

  useEffect(() => {
    branding
      .get()
      .then((d) => {
        setData(d);
        setOpacity(d.watermark_opacity);
        setPosition(d.watermark_position);
        setScale(d.watermark_scale);
        setPadding(d.watermark_padding);
        setTileRotation(d.watermark_tile_rotation);
        setTileSpacing(d.watermark_tile_spacing);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    try {
      const updated = await branding.uploadLogo(file);
      setData(updated);
      setMessage("Logo uploaded successfully.");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Upload failed");
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/png": [".png"] },
    maxFiles: 1,
  });

  async function handleSave() {
    setSaving(true);
    setMessage("");
    try {
      const updated = await branding.update({
        watermark_opacity: opacity,
        watermark_position: position,
        watermark_scale: scale,
        watermark_padding: padding,
        watermark_tile_rotation: tileRotation,
        watermark_tile_spacing: tileSpacing,
      });
      setData(updated);
      setMessage("Settings saved.");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  // Watermark position CSS
  const positionClasses: Record<string, string> = {
    center: "inset-0 flex items-center justify-center",
    "bottom-right": "bottom-3 right-3",
    "bottom-left": "bottom-3 left-3",
    tiled: "inset-0 overflow-hidden",
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Branding &amp; Watermark
        </h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Customize watermarks applied to gallery previews.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        {/* Left: controls */}
        <div className="space-y-6">
          {/* Logo upload */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Watermark Logo</CardTitle>
            </CardHeader>
            <CardContent>
              <div
                {...getRootProps()}
                className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
                  isDragActive
                    ? "border-[var(--primary)] bg-[var(--primary)]/5"
                    : "border-[var(--border)] hover:border-[var(--primary)]/50"
                }`}
              >
                <input {...getInputProps()} />
                {data?.watermark_logo_key ? (
                  <div className="flex flex-col items-center gap-2">
                    <Check className="h-8 w-8 text-[var(--success)]" />
                    <p className="text-sm font-medium">Logo uploaded</p>
                    <p className="text-xs text-[var(--muted-foreground)]">
                      {data.watermark_logo_key.split("/").pop()}
                    </p>
                    <p className="text-xs text-[var(--muted-foreground)]">
                      Drop a new PNG to replace
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <Upload className="h-8 w-8 text-[var(--muted-foreground)]" />
                    <p className="text-sm font-medium">
                      Drop a PNG logo here
                    </p>
                    <p className="text-xs text-[var(--muted-foreground)]">
                      Transparent background recommended
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Settings */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label>Position</Label>
                <Select value={position} onValueChange={setPosition}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="center">Center</SelectItem>
                    <SelectItem value="bottom-right">Bottom Right</SelectItem>
                    <SelectItem value="bottom-left">Bottom Left</SelectItem>
                    <SelectItem value="tiled">Tiled (diagonal)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Opacity</Label>
                  <span className="text-xs font-mono text-[var(--muted-foreground)]">
                    {(opacity * 100).toFixed(0)}%
                  </span>
                </div>
                <Slider
                  value={[opacity]}
                  onValueChange={([v]) => setOpacity(v)}
                  min={0}
                  max={1}
                  step={0.05}
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Scale</Label>
                  <span className="text-xs font-mono text-[var(--muted-foreground)]">
                    {(scale * 100).toFixed(0)}%
                  </span>
                </div>
                <Slider
                  value={[scale]}
                  onValueChange={([v]) => setScale(v)}
                  min={0.01}
                  max={0.5}
                  step={0.01}
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Edge Padding</Label>
                  <span className="text-xs font-mono text-[var(--muted-foreground)]">
                    {(padding * 100).toFixed(0)}%
                  </span>
                </div>
                <Slider
                  value={[padding]}
                  onValueChange={([v]) => setPadding(v)}
                  min={0}
                  max={0.2}
                  step={0.005}
                />
              </div>

              {position === "tiled" && (
                <>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Tile Rotation</Label>
                      <span className="text-xs font-mono text-[var(--muted-foreground)]">
                        {tileRotation.toFixed(0)}°
                      </span>
                    </div>
                    <Slider
                      value={[tileRotation]}
                      onValueChange={([v]) => setTileRotation(v)}
                      min={0}
                      max={360}
                      step={5}
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Tile Spacing</Label>
                      <span className="text-xs font-mono text-[var(--muted-foreground)]">
                        {(tileSpacing * 100).toFixed(0)}%
                      </span>
                    </div>
                    <Slider
                      value={[tileSpacing]}
                      onValueChange={([v]) => setTileSpacing(v)}
                      min={0.1}
                      max={2}
                      step={0.05}
                    />
                  </div>
                </>
              )}

              {message && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className={`text-sm ${
                    message.toLowerCase().includes("fail")
                      ? "text-[var(--destructive)]"
                      : "text-[var(--success)]"
                  }`}
                >
                  {message}
                </motion.p>
              )}

              <Button
                onClick={handleSave}
                disabled={saving}
                className="w-full"
              >
                {saving ? "Saving..." : "Save Settings"}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Right: live preview */}
        <Card className="self-start">
          <CardHeader>
            <CardTitle className="text-base">Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="relative aspect-[4/3] overflow-hidden rounded-lg bg-[var(--muted)]/20">
              <div className="flex h-full items-center justify-center">
                <ImageIcon className="h-12 w-12 text-[var(--muted-foreground)]/30" />
              </div>
              {/* Watermark overlay */}
              <div
                className={`absolute ${positionClasses[position] || positionClasses["bottom-right"]}`}
                style={{ opacity }}
              >
                {position === "tiled" ? (
                  (() => {
                    const tileSize = Math.max(scale * 200, 20);
                    const gap = tileSize * tileSpacing;
                    const step = tileSize + gap;
                    // Generate enough tiles to cover the preview area (generous)
                    const cols = Math.ceil(400 / step) + 2;
                    const rows = Math.ceil(300 / step) + 2;
                    const tiles: { key: string; x: number; y: number }[] = [];
                    for (let r = -1; r < rows; r++) {
                      for (let c = -1; c < cols; c++) {
                        tiles.push({
                          key: `${r}-${c}`,
                          x: c * step,
                          y: r * step,
                        });
                      }
                    }
                    return (
                      <div className="relative h-full w-full">
                        {tiles.map((t) => (
                          <div
                            key={t.key}
                            className="absolute"
                            style={{
                              left: t.x,
                              top: t.y,
                              width: tileSize,
                              height: tileSize,
                              transform: `rotate(${tileRotation}deg)`,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                            }}
                          >
                            {data?.watermark_logo_url ? (
                              <img
                                src={data.watermark_logo_url}
                                alt=""
                                style={{
                                  maxWidth: "100%",
                                  maxHeight: "100%",
                                  objectFit: "contain",
                                }}
                              />
                            ) : (
                              <span
                                className="whitespace-nowrap font-semibold text-[var(--foreground)]/30"
                                style={{ fontSize: `${Math.max(tileSize * 0.4, 8)}px` }}
                              >
                                LOGO
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    );
                  })()
                ) : data?.watermark_logo_url ? (
                  <img
                    src={data.watermark_logo_url}
                    alt="Watermark"
                    style={{ width: `${Math.max(scale * 200, 20)}px` }}
                  />
                ) : (
                  <span
                    className="font-semibold text-[var(--foreground)]/30"
                    style={{ fontSize: `${Math.max(scale * 120, 10)}px` }}
                  >
                    LOGO
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
