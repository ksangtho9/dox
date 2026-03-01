'use client';

import Image from 'next/image';
import { FallingPattern } from '@/components/ui/falling-pattern';
import { Upload, Github, ArrowRight } from 'lucide-react';

export default function Home() {
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
          >
            <Upload className="mb-3 h-10 w-10 text-[var(--primary)]" />
            <p className="mb-1 text-center text-xs text-zinc-300 sm:text-sm">
              Drop your repo here or{' '}
              <span className="font-medium text-[var(--primary)]">browse</span>
            </p>
            <p className="text-[10px] text-zinc-500 sm:text-xs">
              .zip, .tar.gz, or folder
            </p>
            <input
              id="repo-drop"
              type="file"
              className="sr-only"
              accept=".zip,.tar.gz"
              multiple
            />
          </label>
        </div>

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
            className="font-pixel flex shrink-0 items-center justify-center gap-2 rounded-lg bg-[var(--primary)] px-6 py-3 text-sm text-white transition-opacity hover:opacity-90"
          >
            Analyze
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
