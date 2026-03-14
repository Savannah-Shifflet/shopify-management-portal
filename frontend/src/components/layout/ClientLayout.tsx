"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { AuthGuard } from "./AuthGuard";
import { ErrorBoundary } from "./ErrorBoundary";

const AUTH_PATHS = ["/login", "/register"];

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAuthPage = AUTH_PATHS.includes(pathname);

  if (isAuthPage) {
    return <ErrorBoundary>{children}</ErrorBoundary>;
  }

  return (
    <AuthGuard>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 overflow-hidden">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </div>
    </AuthGuard>
  );
}
