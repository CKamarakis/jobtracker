// Placeholder for routes that are linked-to but not built yet (Applications, Saved).
// A real page replaces this when its flow lands — keeping the route alive now means the
// nav never dead-ends and the URL space is reserved.
export function StubPage({ title }: { title: string }) {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="text-sm text-muted-foreground">Coming soon.</p>
    </div>
  );
}
