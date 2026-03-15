import type { Metadata } from "next";
import { ThemeWrapper } from "./theme-wrapper";
import "./globals.css";

export const metadata: Metadata = {
  title: "PhotoCurate",
  description: "AI-powered photo curation for professional photographers",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <body>
        <ThemeWrapper>{children}</ThemeWrapper>
      </body>
    </html>
  );
}
