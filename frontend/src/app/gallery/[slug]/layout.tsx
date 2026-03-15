import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Photo Gallery — PhotoCurate",
  description: "View and select your photos",
};

export default function GalleryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div data-theme="dark">{children}</div>;
}
