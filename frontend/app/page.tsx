'use client';

import { useState, useRef } from 'react';
import Image from 'next/image';
import { FallingPattern } from '@/components/ui/falling-pattern';
import { Upload, Github, ArrowRight, Loader2, AlertCircle } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type AnalyzeResult = {
  metadata: {
    projectName: string;
    languages: string[];
    frameworks: string[];
    package_manager: string | null;
    entry_points: string[];
    has_tests: boolean;
    summary: string;
  };
  readme: string;
};

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function analyzeFile(file: File) {
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError('Please upload a .zip file.');
      return;
    }
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.detail || res.statusText || 'Analysis failed');
        return;
      }
      setResult(data as AnalyzeResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Network error. Is the backend running?');
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
      <div className="absolute inset-0 z-10 flex min-h-screen flex-col items-center px-6 pt-12 pb-64 font-pixel">
        {/* Logo - top left */}
        <header className="absolute left-6 top-6 flex items-center">
          <Image
            src="/dox-logo.png"
            alt="dox."
            width={120}
            height={40}
            className="h-8 w-auto sm:h-10"
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

        {/* Result */}
        {result && (
          <div className="mb-24 w-full max-w-2xl rounded-xl border border-zinc-700 bg-black/40 p-6">
            <div className="mb-4 flex flex-wrap gap-2 text-xs text-zinc-400">
              {result.metadata.languages?.length > 0 && (
                <span>Languages: {result.metadata.languages.join(', ')}</span>
              )}
              {result.metadata.frameworks?.length > 0 && (
                <span>Frameworks: {result.metadata.frameworks.join(', ')}</span>
              )}
              {result.metadata.package_manager && (
                <span>Package manager: {result.metadata.package_manager}</span>
              )}
              {result.metadata.has_tests && <span>Has tests</span>}
            </div>
            <div className="max-h-[60vh] overflow-auto rounded-lg border border-zinc-700 bg-zinc-900/80 p-4">
              <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-zinc-300">
                {result.readme}
              </pre>
            </div>
          </div>
        )}

        {/* Separator */}
        <p className="mb-6 text-xs text-zinc-500">or</p>

        {/* URL input + Analyze button */}
        <div className="mb-24 flex w-full max-w-2xl flex-col gap-3 sm:flex-row">
          <div className="relative flex flex-1">
            <Github className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-500" />
            <input
              type="url"
              placeholder="https://github.com/user/repo"
              className="font-pixel w-full rounded-lg border border-zinc-700 bg-white/[0.04] py-3 pl-10 pr-4 text-sm text-white placeholder:text-zinc-500 focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
            />
          </div>
          <button
            type="button"
            className="font-pixel flex shrink-0 cursor-not-allowed items-center justify-center gap-2 rounded-lg bg-zinc-600 px-6 py-3 text-sm text-zinc-400"
            title="Coming soon"
          >
            Analyze
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
