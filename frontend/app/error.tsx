'use client';

import { useEffect } from 'react';
import Link from 'next/link';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-[var(--background)] px-6">
      <h1 className="text-2xl font-semibold text-white">Something went wrong</h1>
      <p className="max-w-md text-center text-zinc-400">{error.message}</p>
      <div className="flex gap-4">
        <button
          onClick={reset}
          className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          Try again
        </button>
        <Link
          href="/"
          className="rounded-lg border border-zinc-600 px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-white/5"
        >
          Back to home
        </Link>
      </div>
    </div>
  );
}
