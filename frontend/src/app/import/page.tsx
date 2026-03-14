"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { importsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Upload, FileText, Globe, Image, CheckCircle, AlertCircle,
  Loader2, Clock, ChevronRight,
} from "lucide-react";
import { formatDate, statusColor } from "@/lib/utils";
import { cn } from "@/lib/utils";

export default function ImportPage() {
  const qc = useQueryClient();
  const [activeMethod, setActiveMethod] = useState<"csv" | "pdf" | "scrape" | "images" | null>(null);
  const [scrapeUrl, setScrapeUrl] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ["import-jobs"],
    queryFn: () => importsApi.jobs().then((r) => r.data),
    refetchInterval: (query: any) => {
      const data = query.state.data;
      if (!Array.isArray(data)) return 5000;
      const hasRunning = data.some((j: any) => j.status === "running" || j.status === "queued");
      return hasRunning ? 2000 : 10000;
    },
  });

  const csvMutation = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return importsApi.uploadCsv(fd);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["import-jobs"] });
      setActiveMethod(null);
    },
  });

  const pdfMutation = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return importsApi.uploadPdf(fd);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["import-jobs"] });
      setActiveMethod(null);
    },
  });

  const scrapeMutation = useMutation({
    mutationFn: (url: string) => importsApi.startScrape({ url }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["import-jobs"] });
      setScrapeUrl("");
      setActiveMethod(null);
    },
  });

  const imagesMutation = useMutation({
    mutationFn: (files: File[]) => {
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f));
      return importsApi.uploadImages(fd);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["import-jobs"] });
      setActiveMethod(null);
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, type: "csv" | "pdf" | "images") => {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    if (type === "csv") csvMutation.mutate(files[0]);
    else if (type === "pdf") pdfMutation.mutate(files[0]);
    else imagesMutation.mutate(files);
    e.target.value = "";
  };

  const importMethods = [
    {
      id: "csv" as const,
      label: "CSV / Excel",
      description: "Import product data from spreadsheets. AI will help map columns.",
      icon: FileText,
      accept: ".csv,.xlsx,.xls",
      color: "text-green-600",
      bg: "bg-green-50",
      border: "border-green-200",
    },
    {
      id: "pdf" as const,
      label: "PDF Catalog",
      description: "Upload a supplier catalog or line sheet. AI extracts products.",
      icon: FileText,
      accept: ".pdf",
      color: "text-red-600",
      bg: "bg-red-50",
      border: "border-red-200",
    },
    {
      id: "scrape" as const,
      label: "Scrape Website",
      description: "Enter a supplier or manufacturer URL to scrape products.",
      icon: Globe,
      color: "text-blue-600",
      bg: "bg-blue-50",
      border: "border-blue-200",
    },
    {
      id: "images" as const,
      label: "Product Images",
      description: "Upload product photos. AI identifies and creates product listings.",
      icon: Image,
      accept: "image/*",
      multiple: true,
      color: "text-purple-600",
      bg: "bg-purple-50",
      border: "border-purple-200",
    },
  ];

  return (
    <PageShell title="Import Products" description="Add products from various sources">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {importMethods.map((method) => (
          <Card
            key={method.id}
            className={cn(
              "cursor-pointer hover:shadow-sm transition-all border-2",
              activeMethod === method.id ? method.border : "border-transparent hover:border-gray-200"
            )}
            onClick={() => setActiveMethod(activeMethod === method.id ? null : method.id)}
          >
            <CardContent className="p-5">
              <div className="flex items-start gap-4">
                <div className={`p-3 rounded-lg ${method.bg}`}>
                  <method.icon className={`h-6 w-6 ${method.color}`} />
                </div>
                <div className="flex-1">
                  <p className="font-semibold">{method.label}</p>
                  <p className="text-sm text-gray-500 mt-0.5">{method.description}</p>

                  {/* Expanded action for this method */}
                  {activeMethod === method.id && (
                    <div className="mt-4" onClick={(e) => e.stopPropagation()}>
                      {method.id === "scrape" ? (
                        <div className="flex gap-2">
                          <Input
                            placeholder="https://supplier.com/products"
                            value={scrapeUrl}
                            onChange={(e) => setScrapeUrl(e.target.value)}
                          />
                          <Button
                            onClick={() => scrapeUrl && scrapeMutation.mutate(scrapeUrl)}
                            disabled={!scrapeUrl || scrapeMutation.isPending}
                          >
                            {scrapeMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Scrape"}
                          </Button>
                        </div>
                      ) : (
                        <>
                          <input
                            ref={fileInputRef}
                            type="file"
                            accept={method.accept}
                            multiple={method.multiple}
                            className="hidden"
                            onChange={(e) => handleFileChange(e, method.id as "csv" | "pdf" | "images")}
                          />
                          <Button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={csvMutation.isPending || pdfMutation.isPending || imagesMutation.isPending}
                          >
                            {(csvMutation.isPending || pdfMutation.isPending || imagesMutation.isPending)
                              ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" />Uploading...</>
                              : <><Upload className="h-4 w-4 mr-1" />Choose File{method.multiple ? "s" : ""}</>}
                          </Button>
                        </>
                      )}
                    </div>
                  )}
                </div>
                <ChevronRight className={`h-4 w-4 text-gray-400 transition-transform ${activeMethod === method.id ? "rotate-90" : ""}`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Import jobs */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Recent Import Jobs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {jobsLoading ? (
            <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>
          ) : !jobs || jobs.length === 0 ? (
            <div className="p-8 text-center text-gray-400">No import jobs yet</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Type</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Progress</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Started</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job: any) => (
                  <tr key={job.id} className="border-b last:border-0">
                    <td className="px-4 py-3 capitalize font-medium">{job.job_type.replace(/_/g, " ")}</td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        "flex items-center gap-1 text-xs font-medium w-fit px-2 py-0.5 rounded-full",
                        statusColor(job.status)
                      )}>
                        {job.status === "running" || job.status === "queued"
                          ? <Loader2 className="h-3 w-3 animate-spin" />
                          : job.status === "done"
                          ? <CheckCircle className="h-3 w-3" />
                          : job.status === "failed"
                          ? <AlertCircle className="h-3 w-3" />
                          : <Clock className="h-3 w-3" />}
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {job.total_rows > 0 ? (
                        <div>
                          <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                            <span className="text-green-600">{job.success_rows} ok</span>
                            {job.error_rows > 0 && <span className="text-red-600">{job.error_rows} err</span>}
                            <span>/ {job.total_rows}</span>
                          </div>
                          <div className="w-32 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-500 rounded-full transition-all"
                              style={{ width: `${(job.processed_rows / job.total_rows) * 100}%` }}
                            />
                          </div>
                        </div>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">{formatDate(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}
