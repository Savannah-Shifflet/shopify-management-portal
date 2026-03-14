"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Package,
  Upload,
  DollarSign,
  Truck,
  RefreshCw,
  Settings,
  LayoutDashboard,
  Sparkles,
  LogOut,
  FileText,
  ShoppingCart,
  ClipboardList,
  Search,
} from "lucide-react";
import { clearToken } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/products", label: "Products", icon: Package },
  { href: "/import", label: "Import", icon: Upload },
  { href: "/enrichment", label: "AI Enrichment", icon: Sparkles },
  { href: "/templates", label: "Templates", icon: FileText },
  { href: "/pricing", label: "Pricing", icon: DollarSign },
  { href: "/suppliers", label: "Suppliers", icon: Truck },
  { href: "/reorders", label: "Reorders", icon: ShoppingCart },
  { href: "/sync", label: "Shopify Sync", icon: RefreshCw },
  { href: "/audit-log", label: "Audit Log", icon: ClipboardList },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };

  return (
    <aside className="w-60 min-h-screen bg-slate-900 text-slate-100 flex flex-col">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Package className="h-6 w-6 text-blue-400" />
          <span className="font-bold text-lg">ProductHub</span>
        </div>
        <p className="text-xs text-slate-400 mt-0.5">E-commerce Manager</p>
      </div>

      {/* Search trigger */}
      <div className="px-3 pt-3 pb-1">
        <button
          onClick={() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true }))}
          className="w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors border border-slate-700"
        >
          <Search className="h-3.5 w-3.5" />
          <span>Search</span>
          <kbd className="ml-auto text-xs bg-slate-800 border border-slate-600 rounded px-1">⌘K</kbd>
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                active
                  ? "bg-blue-600 text-white"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              )}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-slate-700 space-y-2">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium w-full text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
        >
          <LogOut className="h-4 w-4 flex-shrink-0" />
          Sign Out
        </button>
        <p className="text-xs text-slate-500 px-3">Shopify-authorized dealer tools</p>
      </div>
    </aside>
  );
}
