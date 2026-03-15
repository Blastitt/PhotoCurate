import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-[var(--primary)] text-[var(--primary-foreground)]",
        secondary:
          "border-transparent bg-[var(--secondary)] text-[var(--secondary-foreground)]",
        destructive:
          "border-transparent bg-[var(--destructive)] text-[var(--destructive-foreground)]",
        outline: "text-[var(--foreground)]",
        created:
          "border-transparent bg-[var(--status-created)]/20 text-[var(--status-created)]",
        uploading:
          "border-transparent bg-[var(--status-uploading)]/20 text-[var(--status-uploading)]",
        processing:
          "border-transparent bg-[var(--status-processing)]/20 text-[var(--status-processing)] animate-pulse-ring",
        curated:
          "border-transparent bg-[var(--status-curated)]/20 text-[var(--status-curated)]",
        "gallery-shared":
          "border-transparent bg-[var(--status-gallery-shared)]/20 text-[var(--status-gallery-shared)]",
        "selection-complete":
          "border-transparent bg-[var(--status-selection-complete)]/20 text-[var(--status-selection-complete)]",
        editing:
          "border-transparent bg-[var(--status-editing)]/20 text-[var(--status-editing)]",
        delivered:
          "border-transparent bg-[var(--status-delivered)]/20 text-[var(--status-delivered)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

/** Map a session/photo status string to a badge variant */
function statusVariant(
  status: string,
): VariantProps<typeof badgeVariants>["variant"] {
  const map: Record<string, VariantProps<typeof badgeVariants>["variant"]> = {
    created: "created",
    uploading: "uploading",
    processing: "processing",
    curated: "curated",
    gallery_shared: "gallery-shared",
    selection_complete: "selection-complete",
    editing: "editing",
    delivered: "delivered",
    scored: "curated",
    auto_picked: "default",
    rejected: "destructive",
    gallery_ready: "curated",
    client_selected: "selection-complete",
    client_rejected: "destructive",
    edited_uploaded: "editing",
    active: "curated",
    expired: "secondary",
  };
  return map[status] ?? "secondary";
}

export { Badge, badgeVariants, statusVariant };
