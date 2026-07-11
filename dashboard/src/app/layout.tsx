import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { DashboardHeader } from "@/components/dashboard-header";
import { AuthProvider } from "@/components/auth-provider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const SITE_URL = "https://platform-agent-red.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Platform Agent — Multi-Cloud Operations Dashboard",
    template: "%s | Platform Agent",
  },
  description:
    "Autonomous multi-cloud operations: provision, deploy, detect, analyze, decide, execute across AWS, GCP, Azure & On-Premise — AI Agent orchestrated.",
  keywords: [
    "platform engineering",
    "multi-cloud",
    "operations dashboard",
    "AWS",
    "GCP",
    "Azure",
    "incident response",
    "AI agent",
    "DevOps",
    "SRE",
  ],
  authors: [{ name: "platform-agent" }],
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: "Platform Agent",
    title: "Platform Agent — Multi-Cloud Operations Dashboard",
    description:
      "Autonomous multi-cloud operations: provision, deploy, detect, analyze, decide, execute across AWS, GCP, Azure & On-Premise.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Platform Agent — Multi-Cloud Operations Dashboard",
    description:
      "AI Agent-driven operations across 4 cloud providers. Detect → Analyze → Decide → Execute.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex">
        <AuthProvider>
          <Sidebar />
          <main className="min-w-0 flex-1 overflow-auto px-5 py-6 sm:px-8 lg:px-10 lg:py-8">
            <DashboardHeader />
            {children}
          </main>
        </AuthProvider>
      </body>
    </html>
  );
}
