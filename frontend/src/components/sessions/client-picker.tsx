"use client";

import { useEffect, useState } from "react";
import { clients, type ClientResponse, ApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { Search, Plus, User, X } from "lucide-react";

interface ClientPickerProps {
  selectedId: string | null;
  onChange: (id: string | null) => void;
}

export function ClientPicker({ selectedId, onChange }: ClientPickerProps) {
  const [allClients, setAllClients] = useState<ClientResponse[]>([]);
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    clients
      .list()
      .then(setAllClients)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = allClients.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.email?.toLowerCase().includes(search.toLowerCase()),
  );

  const selected = allClients.find((c) => c.id === selectedId);

  async function handleCreate() {
    if (!newName.trim()) return;
    setError("");
    try {
      const created = await clients.create({
        name: newName.trim(),
        email: newEmail.trim() || undefined,
      });
      setAllClients((prev) => [created, ...prev]);
      onChange(created.id);
      setCreating(false);
      setNewName("");
      setNewEmail("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to create client");
    }
  }

  if (selected) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--muted)]">
          <User className="h-4 w-4 text-[var(--muted-foreground)]" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium">{selected.name}</p>
          {selected.email && (
            <p className="text-xs text-[var(--muted-foreground)]">
              {selected.email}
            </p>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => onChange(null)}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {!creating ? (
        <>
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted-foreground)]" />
            <Input
              placeholder="Search clients..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Client list */}
          <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg">
            {loading ? (
              <p className="py-4 text-center text-sm text-[var(--muted-foreground)]">
                Loading...
              </p>
            ) : filtered.length === 0 ? (
              <p className="py-4 text-center text-sm text-[var(--muted-foreground)]">
                No clients found
              </p>
            ) : (
              filtered.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => onChange(c.id)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--accent)]",
                  )}
                >
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--muted)]">
                    <User className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
                  </div>
                  <div>
                    <p className="font-medium">{c.name}</p>
                    {c.email && (
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {c.email}
                      </p>
                    )}
                  </div>
                </button>
              ))
            )}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setCreating(true)}
            className="w-full gap-2"
          >
            <Plus className="h-3.5 w-3.5" />
            New Client
          </Button>
        </>
      ) : (
        /* Inline create form */
        <div className="space-y-3 rounded-lg border border-[var(--border)] p-4">
          <div className="space-y-1.5">
            <Label>Client name</Label>
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Jane Smith"
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label>Email (optional)</Label>
            <Input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              placeholder="jane@example.com"
            />
          </div>
          {error && (
            <p className="text-xs text-[var(--destructive)]">{error}</p>
          )}
          <div className="flex gap-2">
            <Button size="sm" onClick={handleCreate} disabled={!newName.trim()}>
              Create
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setCreating(false);
                setNewName("");
                setNewEmail("");
                setError("");
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
