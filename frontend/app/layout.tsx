import type { Metadata } from "next";
import { Fraunces, Schibsted_Grotesk, Spline_Sans_Mono } from "next/font/google";
import "./globals.css";

// Variable font: full wght axis (covers 400-900) loads by default; opsz added for optical sizing
const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  axes: ["opsz"],
  style: ["normal", "italic"],
});

const schibstedGrotesk = Schibsted_Grotesk({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["400", "500", "700"],
});

const splineSansMono = Spline_Sans_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Bangun - Build Smarter with AI-Powered Cost Estimates",
  description: "Know your construction costs before you build. AI-powered material pricing and contractor comparison for Indonesia.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${schibstedGrotesk.variable} ${splineSansMono.variable}`}
    >
      <body className="antialiased font-body">
        {children}
      </body>
    </html>
  );
}
