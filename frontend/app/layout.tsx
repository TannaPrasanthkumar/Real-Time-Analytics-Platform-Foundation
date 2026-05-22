import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Real-Time SaaS Analytics & Reporting Platform",
  description: "Next-generation production-grade SaaS analytical platform offering high-frequency event ingestion, sub-second latency aggregations, and live alerts.",
  keywords: ["SaaS", "Real-time Analytics", "Business Intelligence", "Event Ingestion", "Reporting Dashboards"],
  authors: [{ name: "SaaS Dev Team" }],
  icons: {
    icon: "/favicon.ico",
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-[#09090b] text-slate-100 selection:bg-purple-900 selection:text-white">
        <div className="relative overflow-hidden min-h-screen">
          {/* Ambient Glowing Background Elements */}
          <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-indigo-950/20 blur-[120px] pointer-events-none" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-purple-950/20 blur-[120px] pointer-events-none" />
          
          <main className="relative z-10">
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}
