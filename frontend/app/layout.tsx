import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bali Renovation OS - Fair Pricing for Your Bali Renovation",
  description: "Get accurate material costs and find trusted workers for your Bali renovation project",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
