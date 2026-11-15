import Link from "next/link";
export default function NotFound() {
  return (
    <main className="error-page">
      <h1>This page isn’t in your workspace.</h1>
      <Link href="/dashboard" className="btn btn-primary">
        Open overview
      </Link>
    </main>
  );
}
