"use client";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Check, X } from "lucide-react";

export interface FilterState {
  status: string;
  sort: string;
  hasFaces: string;
}

interface PhotoFiltersProps {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  selectedCount: number;
  onApproveSelected: () => void;
  onRejectSelected: () => void;
  bulkLoading: boolean;
}

export function PhotoFilters({
  filters,
  onChange,
  selectedCount,
  onApproveSelected,
  onRejectSelected,
  bulkLoading,
}: PhotoFiltersProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-wrap gap-2">
        <Select
          value={filters.status}
          onValueChange={(v) => onChange({ ...filters, status: v })}
        >
          <SelectTrigger className="w-36 h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="scored">Scored</SelectItem>
            <SelectItem value="auto_picked">Auto-picked</SelectItem>
            <SelectItem value="gallery_ready">Approved</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filters.sort}
          onValueChange={(v) => onChange({ ...filters, sort: v })}
        >
          <SelectTrigger className="w-36 h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="score-desc">Score ↓</SelectItem>
            <SelectItem value="score-asc">Score ↑</SelectItem>
            <SelectItem value="name">Filename</SelectItem>
            <SelectItem value="date">Date</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filters.hasFaces}
          onValueChange={(v) => onChange({ ...filters, hasFaces: v })}
        >
          <SelectTrigger className="w-32 h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All photos</SelectItem>
            <SelectItem value="yes">Has faces</SelectItem>
            <SelectItem value="no">No faces</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Bulk actions */}
      {selectedCount > 0 && (
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{selectedCount} selected</Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={onApproveSelected}
            disabled={bulkLoading}
            className="gap-1 h-8 text-xs"
          >
            <Check className="h-3 w-3" />
            Approve
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onRejectSelected}
            disabled={bulkLoading}
            className="gap-1 h-8 text-xs text-[var(--destructive)]"
          >
            <X className="h-3 w-3" />
            Reject
          </Button>
        </div>
      )}
    </div>
  );
}
