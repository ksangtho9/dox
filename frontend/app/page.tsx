'use client';

import { useState, useRef } from 'react';
import Image from 'next/image';
import { createPortal } from 'react-dom';
import { FallingPattern } from '@/components/ui/falling-pattern';
import { Upload, Loader2, AlertCircle } from 'lucide-react';

function getApiBaseUrl(): string {
  const env = process.env.NEXT_PUBLIC_API_URL ?? '';
  if (env) return env.replace(/\/$/, '');
  if (typeof window !== 'undefined') {
    const { hostname } = window.location;
    if (hostname === 'localhost' || hostname === '127.0.0.1') return 'http://localhost:8000';
  }
  return '';
}

type DownloadSuccess = {
  filename: string;
};

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadSuccess, setDownloadSuccess] = useState<DownloadSuccess | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function analyzeFile(file: File) {
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError('Please upload a .zip file.');
      return;
    }
    setError(null);
    setDownloadSuccess(null);
    setLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      if (!baseUrl) {
        setError(
          'Backend URL not set. On Vercel: Project → Settings → Environment Variables → add NEXT_PUBLIC_API_URL with your Railway backend URL (e.g. https://your-app.up.railway.app), then redeploy.'
        );
        return;
      }
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${baseUrl}/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const msg = Array.isArray(data.detail) ? data.detail.map((e: { msg?: string }) => e?.msg).filter(Boolean).join(', ') : data.detail;
        setError(msg || res.statusText || 'Analysis failed');
        return;
      }

      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition');
      const match = disposition?.match(/filename="?([^";]+)"?/);
      const filename = match ? match[1].trim() : 'repo-with-readme.zip';

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setDownloadSuccess({ filename });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Network error. Ensure the backend is running and CORS allows this origin.');
    } finally {
      setLoading(false);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      analyzeFile(file);
    }
    e.target.value = '';
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) {
      setSelectedFile(file);
      analyzeFile(file);
    }
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
  }

  return (
    <div className="relative min-h-screen w-full">
      <FallingPattern
        className="absolute inset-0 h-screen [mask-image:radial-gradient(ellipse_at_center,transparent,var(--background))]"
        color="var(--primary)"
        backgroundColor="var(--background)"
      />
      <div className="absolute inset-0 z-10 flex min-h-screen flex-col items-center px-6 pt-20 pb-64 font-pixel">
        {/* Logo - top left */}
        <header className="absolute left-6 top-8 flex items-center">
          <Image
            src="/dox-logo.png"
            alt="dox."
            width={160}
            height={53}
            className="h-10 w-auto sm:h-12"
            priority
          />
        </header>

        {/* Headline & description */}
        <div className="mb-12 max-w-2xl text-center">
          <h1 className="mb-4 text-2xl leading-relaxed text-white sm:text-3xl">
            Understand any codebase instantly
          </h1>
          <p className="text-xs leading-relaxed text-zinc-400 sm:text-sm">
            Drop a repository and get instant documentation, dependency graphs,
            and actionable insights.
          </p>
        </div>

        {/* Drop zone */}
        <div className="mb-6 w-full max-w-2xl">
          <label
            htmlFor="repo-drop"
            className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-[var(--primary)] bg-white/[0.03] px-8 py-14 transition-colors hover:bg-white/[0.06]"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
          >
            {loading ? (
              <>
                <Loader2 className="mb-3 h-10 w-10 animate-spin text-[var(--primary)]" />
                <p className="text-center text-xs text-zinc-300 sm:text-sm">
                  Analyzing…
                </p>
              </>
            ) : (
              <>
                <Upload className="mb-3 h-10 w-10 text-[var(--primary)]" />
                <p className="mb-1 text-center text-xs text-zinc-300 sm:text-sm">
                  Drop your repo here or{' '}
                  <span className="font-medium text-[var(--primary)]">browse</span>
                </p>
                <p className="text-[10px] text-zinc-500 sm:text-xs">
                  .zip only
                </p>
              </>
            )}
            <input
              ref={inputRef}
              id="repo-drop"
              type="file"
              className="sr-only"
              accept=".zip,application/zip"
              onChange={handleFileChange}
              disabled={loading}
            />
          </label>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 flex w-full max-w-2xl items-center gap-2 rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-3 text-left text-xs text-red-300 sm:text-sm">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Download success: portal to body so it never affects layout */}
        {downloadSuccess &&
          typeof document !== 'undefined' &&
          createPortal(
            <div className="fixed bottom-6 left-1/2 z-[9999] w-full max-w-2xl -translate-x-1/2 rounded-xl border border-emerald-500/50 bg-emerald-500/10 px-4 py-3 text-center text-sm text-emerald-300 shadow-lg">
              Your repo with generated README is downloading ({downloadSuccess.filename}).
            </div>,
            document.body
          )}
      </div>
    </div>
  );
}
