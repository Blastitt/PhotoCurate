"use client";

import { AuthProvider } from "@/lib/auth-context";
import { FeaturesProvider } from "@/lib/features-context";
import { DashboardShell } from "@/components/dashboard-shell";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider>
      <FeaturesProvider>
        <DashboardShell>{children}</DashboardShell>
      </FeaturesProvider>
    </AuthProvider>
  );
}
