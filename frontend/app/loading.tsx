export default function Loading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
      <div className="h-8 w-8 animate-pulse rounded-full bg-[var(--primary)] opacity-60" />
    </div>
  );
}
