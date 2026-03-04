import type { Metadata } from "next";
import "./globals.css";
import { AuthSessionProvider } from "@/lib/session-provider";

export const metadata: Metadata = {
  title: "DevShowcase",
  description: "Turn GitHub repos into LinkedIn posts with AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-win98-silver text-win98-black">
        <AuthSessionProvider>{children}</AuthSessionProvider>
      </body>
    </html>
  );
}
