"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="error-page">
      <h1>We couldn’t load this workspace.</h1>
      <p>Your saved data is still available. Try loading the page again.</p>
      <button className="btn btn-primary" onClick={reset}>
        Reload workspace
      </button>
    </main>
  );
}
