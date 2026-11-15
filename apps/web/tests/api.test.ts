import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, post } from "../lib/api";

afterEach(() => vi.unstubAllGlobals());
describe("backend request boundary", () => {
  it("reports a rejected financial action without treating it as success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: "Explicit buyer confirmation is required.",
          }),
          { status: 403 },
        ),
      ),
    );
    await expect(
      post("/haggle/sessions/demo/confirm", {
        merchant_approved: true,
        buyer_confirmed: false,
      }),
    ).rejects.toMatchObject({
      status: 403,
      message: "Explicit buyer confirmation is required.",
    });
  });
  it("surfaces structured provider errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: { message: "Speech provider timed out." },
          }),
          { status: 503 },
        ),
      ),
    );
    await expect(api("/voice/synthesize")).rejects.toThrow(
      "Speech provider timed out.",
    );
  });
  it("handles non-JSON upstream failures as actionable errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("Bad gateway", { status: 502 })),
    );
    try {
      await api("/dashboard/summary");
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(502);
      expect((error as Error).message).toContain("Request failed");
    }
  });
  it("lets the browser set the multipart boundary for actual audio uploads", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ transcript: "नमस्ते" })));
    vi.stubGlobal("fetch", fetch);
    const form = new FormData();
    form.append(
      "file",
      new Blob(["audio"], { type: "audio/webm" }),
      "command.webm",
    );
    await api("/voice/transcribe", { method: "POST", body: form });
    const options = fetch.mock.calls[0][1] as RequestInit;
    expect(new Headers(options.headers).has("Content-Type")).toBe(false);
    expect(options.body).toBe(form);
  });
  it("gives mutating requests independent idempotency keys without exposing credentials", async () => {
    const fetch = vi
      .fn()
      .mockImplementation(() => Promise.resolve(new Response("{}")));
    vi.stubGlobal("fetch", fetch);
    await post("/campaigns", { name: "A" });
    await post("/campaigns", { name: "B" });
    const first = new Headers(fetch.mock.calls[0][1].headers);
    const second = new Headers(fetch.mock.calls[1][1].headers);
    expect(first.get("Idempotency-Key")).toMatch(/^[a-f0-9-]{36}$/);
    expect(first.get("Idempotency-Key")).not.toBe(
      second.get("Idempotency-Key"),
    );
    expect(first.get("api-subscription-key")).toBeNull();
    expect(first.get("Content-Type")).toBe("application/json");
  });
  it("accepts a successful no-content response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );
    await expect(
      api("/catalog/products/test", { method: "DELETE" }),
    ).resolves.toBeUndefined();
  });
});

it("preserves a caller-supplied idempotency key for retrying the same mutation", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response("{}"));
  vi.stubGlobal("fetch", fetch);
  await api("/transactions/import", {
    method: "POST",
    headers: { "Idempotency-Key": "transaction-file-verified-digest" },
    body: new FormData(),
  });
  expect(
    new Headers(fetch.mock.calls[0][1].headers).get("Idempotency-Key"),
  ).toBe("transaction-file-verified-digest");
});
