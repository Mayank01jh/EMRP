import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EMRP — Emergency Medical Response",
  description: "Tap SOS to request immediate emergency medical assistance. Your location will be shared automatically.",
  manifest: "/manifest.json",
  keywords: ["emergency", "ambulance", "SOS", "medical", "help"],
  authors: [{ name: "EMRP Team" }],
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0b2545",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
