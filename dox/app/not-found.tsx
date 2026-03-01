import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-[var(--background)] px-6">
      <h1 className="text-2xl font-semibold text-white">Page not found</h1>
      <p className="max-w-md text-center text-zinc-400">
        The page you’re looking for doesn’t exist or was moved.
      </p>
      <Link
        href="/"
        className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
      >
        Back to home
      </Link>
    </div>
  );
}
