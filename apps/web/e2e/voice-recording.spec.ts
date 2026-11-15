import { chromium, expect, test } from "@playwright/test";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";

for (const sample of [
  {
    language: "hi-IN",
    name: "Hindi",
    text: "पंद्रह रुपये डिस्काउंट और ढाई सौ रुपये मिनिमम बिल की नई कैम्पेन बनाओ।",
  },
  {
    language: "mr-IN",
    name: "Marathi",
    text: "पंधरा रुपये सूट आणि अडीचशे रुपये किमान बिलाची नवीन मोहीम तयार करा.",
  },
]) {
  test(`recorded ${sample.name} audio becomes a real Sarvam proposal before approval`, async ({
    request,
    baseURL,
  }) => {
    test.setTimeout(120_000);
    const health = await (await request.get("/api/v1/health")).json();
    test.skip(
      !health.sarvam.configured,
      "A Sarvam subscription is required for genuine speech integration.",
    );
    const synthesis = await request.post("/api/v1/voice/synthesize", {
      data: { text: sample.text, language: sample.language },
    });
    expect(synthesis.ok()).toBeTruthy();
    const speech = await synthesis.json();
    expect(speech.provider).toBe("sarvam");
    expect(speech.audio_base64).toBeTruthy();
    const folder = await mkdtemp(join(tmpdir(), "pehchaan-voice-test-"));
    const source = join(folder, "source.wav");
    const microphone = join(folder, "microphone.wav");
    await writeFile(source, Buffer.from(speech.audio_base64, "base64"));
    execFileSync("ffmpeg", [
      "-y",
      "-loglevel",
      "error",
      "-i",
      source,
      "-ac",
      "1",
      "-ar",
      "48000",
      "-c:a",
      "pcm_s16le",
      microphone,
    ]);
    const duration = Number(
      execFileSync(
        "ffprobe",
        [
          "-v",
          "error",
          "-show_entries",
          "format=duration",
          "-of",
          "default=noprint_wrappers=1:nokey=1",
          microphone,
        ],
        { encoding: "utf8" },
      ).trim(),
    );
    expect(duration).toBeLessThan(28);
    const browser = await chromium.launch({
      headless: true,
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        `--use-file-for-fake-audio-capture=${microphone}`,
      ],
    });
    try {
      const context = await browser.newContext({ permissions: ["microphone"] });
      const page = await context.newPage();
      await page.goto(`${baseURL}/soundbox`);
      await page
        .getByRole("combobox", { name: "Assistant language" })
        .selectOption(sample.language);
      await page.getByRole("checkbox", { name: "Spoken responses" }).uncheck();
      const before = await (await request.get("/api/v1/campaigns")).json();
      const transcriptionResponse = page.waitForResponse((r) =>
        r.url().endsWith("/api/v1/voice/transcribe"),
      );
      const proposalResponse = page.waitForResponse((r) =>
        r.url().endsWith("/api/v1/voice/chat"),
      );
      await page
        .getByRole("button", { name: "Start microphone recording" })
        .click();
      await page.waitForTimeout((duration + 0.5) * 1000);
      await page.getByRole("button", { name: "Stop recording" }).click();
      const transcription = await (await transcriptionResponse).json();
      expect(transcription.provider).toBe("sarvam");
      expect(transcription.transcript.length).toBeGreaterThan(10);
      const proposal = await (await proposalResponse).json();
      expect(proposal.provider).toBe("sarvam");
      expect(proposal.proposal.status).toBe("pending_approval");
      await expect(
        page.getByRole("button", { name: "Approve action" }),
      ).toBeVisible();
      const after = await (await request.get("/api/v1/campaigns")).json();
      expect(after.length).toBe(before.length);
    } finally {
      await browser.close();
      await rm(folder, { recursive: true, force: true });
    }
  });
}
