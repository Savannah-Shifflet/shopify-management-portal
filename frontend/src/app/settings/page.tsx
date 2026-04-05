"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settingsApi, storeSettingsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Wifi, WifiOff, Loader2, Unplug, CheckCircle, RefreshCw, Inbox } from "lucide-react";
import { supplierSrmApi } from "@/lib/api";

export default function SettingsPage() {
  const qc = useQueryClient();
  const [storeDomain, setStoreDomain] = useState("");
  const [connectError, setConnectError] = useState<string | null>(null);

  // Store settings state
  const [storeForm, setStoreForm] = useState<any>(null);
  const [storeSaved, setStoreSaved] = useState(false);
  const [testEmailResult, setTestEmailResult] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  const { data: shopify, isLoading } = useQuery({
    queryKey: ["shopify-settings"],
    queryFn: () => settingsApi.getShopify().then((r) => r.data),
  });

  const handleConnectShopify = () => {
    const shop = storeDomain.trim().toLowerCase()
      .replace(/^https?:\/\//, "")
      .replace(/\/$/, "");
    if (!shop) return;
    if (!shop.endsWith(".myshopify.com")) {
      setConnectError("Must be your .myshopify.com domain (e.g. mystore.myshopify.com)");
      return;
    }
    setConnectError(null);
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    window.location.href = `${apiBase}/api/v1/auth/shopify?shop=${encodeURIComponent(shop)}`;
  };

  const disconnectMutation = useMutation({
    mutationFn: () => settingsApi.disconnectShopify(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shopify-settings"] });
      qc.invalidateQueries({ queryKey: ["sync-status"] });
    },
  });

  // Store settings queries
  const { data: storeData } = useQuery({
    queryKey: ["store-settings"],
    queryFn: () => storeSettingsApi.get().then((r) => r.data),
  });

  useEffect(() => {
    if (storeData && !storeForm) {
      setStoreForm(storeData);
    }
  }, [storeData]);

  const storeUpdateMutation = useMutation({
    mutationFn: () => storeSettingsApi.update(storeForm),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["store-settings"] });
      setStoreSaved(true);
      setTimeout(() => setStoreSaved(false), 3000);
    },
  });

  const testEmailMutation = useMutation({
    mutationFn: () => storeSettingsApi.testEmail(),
    onSuccess: () => setTestEmailResult("Test email sent successfully!"),
    onError: () => setTestEmailResult("Failed to send test email. Check your SMTP settings."),
  });

  const syncInboxMutation = useMutation({
    mutationFn: () => supplierSrmApi.syncInbox(),
    onSuccess: (res) => {
      const d = res.data;
      setSyncResult(`Sync complete: ${d.new_emails} new email${d.new_emails !== 1 ? "s" : ""} from ${d.matched_suppliers} supplier${d.matched_suppliers !== 1 ? "s" : ""}.`);
    },
    onError: (err: any) => setSyncResult(`Sync failed: ${err.response?.data?.detail || err.message}`),
  });

  return (
    <PageShell title="Settings" description="Configure your API connections">
      <div className="max-w-2xl space-y-6">
        {/* Shopify */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-base flex items-center gap-2">
              <svg viewBox="0 0 109 124" className="h-5 w-5 text-[#96bf48]" fill="currentColor">
                <path d="M74.7 14.8c0 0-1.4.4-3.7 1.1c-.4-1.3-1-2.8-1.8-4.4c-2.6-5-6.5-7.7-11.1-7.7c0 0 0 0 0 0c-.3 0-.6 0-1 .1c-.1-.2-.3-.3-.4-.5c-2-2.2-4.6-3.2-7.7-3.1c-6 .2-12 4.5-16.8 12.2c-3.4 5.4-6 12.2-6.7 17.5c-6.9 2.1-11.7 3.6-11.8 3.7c-3.5 1.1-3.6 1.2-4 4.5C9.3 41.1 0 111.3 0 111.3l75.7 13.1V14.5C75.2 14.6 74.9 14.7 74.7 14.8z"/>
              </svg>
              Shopify Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Current status */}
            {isLoading ? (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading...
              </div>
            ) : shopify?.connected ? (
              <div className="flex items-center justify-between p-3 rounded-lg border bg-green-50 border-green-200">
                <div className="flex items-center gap-2">
                  <Wifi className="h-4 w-4 text-green-600" />
                  <span className="text-sm font-medium text-green-700">
                    Connected: {shopify.store_domain}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  onClick={() => disconnectMutation.mutate()}
                  disabled={disconnectMutation.isPending}
                >
                  {disconnectMutation.isPending
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <><Unplug className="h-4 w-4 mr-1" />Disconnect</>}
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2 p-3 rounded-lg border bg-amber-50 border-amber-200">
                <WifiOff className="h-4 w-4 text-amber-600" />
                <span className="text-sm text-amber-700">Not connected to Shopify</span>
              </div>
            )}

            {/* Connect form (only shown when not connected) */}
            {!shopify?.connected && (
              <>
                <div>
                  <Label>Store Domain</Label>
                  <Input
                    className="mt-1"
                    value={storeDomain}
                    onChange={(e) => setStoreDomain(e.target.value)}
                    placeholder="your-store.myshopify.com"
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    Must be your <strong>.myshopify.com</strong> domain — not a custom domain (e.g. <code className="bg-gray-100 px-1 rounded">mystore.myshopify.com</code>). You will be redirected to Shopify to approve the connection.
                  </p>
                </div>

                {connectError && (
                  <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3">
                    {connectError}
                  </p>
                )}

                <Button
                  size="sm"
                  onClick={handleConnectShopify}
                  disabled={!storeDomain.trim()}
                >
                  <Wifi className="h-4 w-4 mr-1" />Connect with Shopify
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        {/* Claude API */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-base">Anthropic Claude API</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500">
              Set <code className="bg-gray-100 px-1 rounded text-xs">ANTHROPIC_API_KEY</code> in your{" "}
              <code className="bg-gray-100 px-1 rounded text-xs">.env</code> file and restart the backend.
            </p>
          </CardContent>
        </Card>

        {/* Environment info */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-base">Environment</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500">
              Backend API: <code className="bg-gray-100 px-1 rounded text-xs">{process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}</code>
            </p>
          </CardContent>
        </Card>

        {/* Store Settings */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-base">Store Settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Store Name</Label>
                <Input
                  className="mt-1"
                  value={storeForm?.store_name || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, store_name: e.target.value }))}
                  placeholder="My Store"
                />
              </div>
              <div>
                <Label>Owner Name</Label>
                <Input
                  className="mt-1"
                  value={storeForm?.owner_name || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, owner_name: e.target.value }))}
                  placeholder="Jane Smith"
                />
              </div>
              <div>
                <Label>Currency</Label>
                <Input
                  className="mt-1"
                  value={storeForm?.currency || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, currency: e.target.value }))}
                  placeholder="USD"
                />
              </div>
              <div>
                <Label>Timezone</Label>
                <Input
                  className="mt-1"
                  value={storeForm?.timezone || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, timezone: e.target.value }))}
                  placeholder="America/New_York"
                />
              </div>
            </div>
            <Button
              size="sm"
              onClick={() => storeUpdateMutation.mutate()}
              disabled={storeUpdateMutation.isPending || !storeForm}
            >
              {storeUpdateMutation.isPending
                ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" />Saving...</>
                : storeSaved
                ? <><CheckCircle className="h-4 w-4 mr-1 text-green-500" />Saved</>
                : "Save Store Settings"}
            </Button>
          </CardContent>
        </Card>

        {/* Email (SMTP) */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-base">Email (SMTP)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>SMTP Host</Label>
                <Input
                  className="mt-1"
                  value={storeForm?.smtp_host || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, smtp_host: e.target.value }))}
                  placeholder="smtp.gmail.com"
                />
              </div>
              <div>
                <Label>SMTP Port</Label>
                <Input
                  className="mt-1"
                  type="number"
                  value={storeForm?.smtp_port || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, smtp_port: e.target.value ? Number(e.target.value) : null }))}
                  placeholder="587"
                />
              </div>
              <div>
                <Label>SMTP Username</Label>
                <Input
                  className="mt-1"
                  value={storeForm?.smtp_user || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, smtp_user: e.target.value }))}
                  placeholder="you@gmail.com"
                />
              </div>
              <div>
                <Label>SMTP Password</Label>
                <Input
                  className="mt-1"
                  type="password"
                  value={storeForm?.smtp_password || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, smtp_password: e.target.value }))}
                  placeholder="••••••••"
                />
              </div>
              <div>
                <Label>From Name</Label>
                <Input
                  className="mt-1"
                  value={storeForm?.smtp_from_name || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, smtp_from_name: e.target.value }))}
                  placeholder="My Store"
                />
              </div>
              <div>
                <Label>From Email</Label>
                <Input
                  className="mt-1"
                  type="email"
                  value={storeForm?.smtp_from_email || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, smtp_from_email: e.target.value }))}
                  placeholder="noreply@mystore.com"
                />
              </div>
            </div>
            <div className="flex gap-2 items-center">
              <Button
                size="sm"
                onClick={() => storeUpdateMutation.mutate()}
                disabled={storeUpdateMutation.isPending || !storeForm}
              >
                {storeUpdateMutation.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
                Save Email Settings
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => { setTestEmailResult(null); testEmailMutation.mutate(); }}
                disabled={testEmailMutation.isPending}
              >
                {testEmailMutation.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
                Test Email
              </Button>
            </div>
            {testEmailResult && (
              <p className={`text-sm ${testEmailResult.startsWith("Test email sent") ? "text-green-600" : "text-red-600"}`}>
                {testEmailResult}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Email Receiving (IMAP) */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-base flex items-center gap-2">
              <Inbox className="h-4 w-4 text-gray-500" />
              Email Receiving (IMAP)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-gray-500 bg-gray-50 border rounded p-3">
              Connect your inbox so replies from suppliers are automatically matched and logged in their communication thread.
              For Gmail, use an <strong>App Password</strong> (not your regular password).
              The inbox is polled every 15 minutes automatically — only emails <em>from</em> supplier addresses you have on file will be imported.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>IMAP Host</Label>
                <Input
                  className="mt-1"
                  value={storeForm?.imap_host || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, imap_host: e.target.value }))}
                  placeholder="imap.gmail.com"
                />
              </div>
              <div>
                <Label>IMAP Port</Label>
                <Input
                  className="mt-1"
                  type="number"
                  value={storeForm?.imap_port || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, imap_port: e.target.value ? Number(e.target.value) : null }))}
                  placeholder="993"
                />
              </div>
              <div>
                <Label>IMAP Username</Label>
                <Input
                  className="mt-1"
                  value={storeForm?.imap_user || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, imap_user: e.target.value }))}
                  placeholder="you@gmail.com"
                />
              </div>
              <div>
                <Label>IMAP Password / App Password</Label>
                <Input
                  className="mt-1"
                  type="password"
                  value={storeForm?.imap_password || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, imap_password: e.target.value }))}
                  placeholder="••••••••"
                />
              </div>
              <div>
                <Label>Folder</Label>
                <Input
                  className="mt-1"
                  value={storeForm?.imap_folder || ""}
                  onChange={(e) => setStoreForm((prev: any) => ({ ...prev, imap_folder: e.target.value }))}
                  placeholder="INBOX"
                />
              </div>
            </div>
            <div className="flex gap-2 items-center">
              <Button
                size="sm"
                onClick={() => storeUpdateMutation.mutate()}
                disabled={storeUpdateMutation.isPending || !storeForm}
              >
                {storeUpdateMutation.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
                Save IMAP Settings
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => { setSyncResult(null); syncInboxMutation.mutate(); }}
                disabled={syncInboxMutation.isPending}
              >
                {syncInboxMutation.isPending
                  ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" />Syncing...</>
                  : <><RefreshCw className="h-4 w-4 mr-1" />Sync Now</>}
              </Button>
            </div>
            {syncResult && (
              <p className={`text-sm ${syncResult.startsWith("Sync complete") ? "text-green-600" : "text-red-600"}`}>
                {syncResult}
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}
