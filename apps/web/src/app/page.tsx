import { HealthCheck } from "@/components/health-check";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight text-gray-900">
        Aacharya — Web Scaffold Ready
      </h1>
      <p className="mt-3 text-sm leading-6 text-gray-600">
        Checkpoint C0 scaffold is initialized. Ananya can start implementing feature screens using
        the typed API contracts in{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-900">
          src/lib/contracts.ts
        </code>{" "}
        and the client helper in{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-900">
          src/lib/api-client.ts
        </code>
        .
      </p>
      <HealthCheck />
    </main>
  );
}
