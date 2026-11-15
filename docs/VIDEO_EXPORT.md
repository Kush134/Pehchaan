# Pehchaan walkthrough video

The walkthrough uses actual recordings of the blue-and-white Pehchaan interface, with animated chapter cards, cursor/callout guidance, and captions captured in the browser. It is not a collection of generated application mockups.

The English voiceover is AI-generated with the configured server-side Sarvam subscription. The prepared twenty-chapter cut is approximately seven minutes and twelve seconds; the final measured duration is recorded in `export-summary.json`. The script covers the merchant problem, solution, end-to-end feature workflows, architecture, USP, and a **proposed** business model. No real-person voice is imitated. No music bed is added, so speech and UI explanations remain clear.

## Outputs

Under `artifacts/pehchaan-walkthrough/`:

- `Pehchaan-Walkthrough-1080p.mp4` — 1920×1080, 30 fps, H.264 video, AAC stereo audio, embedded navigation chapters, fast-start MP4.
- `Pehchaan-Walkthrough.srt` and `Pehchaan-Walkthrough.vtt` — the full narration as optional player subtitles.
- `Pehchaan-Voiceover.m4a` — the continuous voiceover, including chapter pacing.
- `export-summary.json` — measured duration, resolution, codecs, audio/video timing difference, file size, and chapter start/end times.
- `Pehchaan-Poster.png` — a 1080p opening-frame poster.
- `Pehchaan-Contact-Sheet.jpg` and `review/` — a twenty-scene overview and full-resolution review frames.
- `qa-summary.json` and `qa-*.log` — black-frame, silence, and audio-level scan results.
- `clips/` — reproducible chapter renders with source/parameter fingerprint caches.
- `raw/` — original browser recordings.
- `capture.json` — the chapter manifest written by the capture workflow.

The short takeaway captions and chapter headings are already burned into the browser recording. The SRT/VTT files contain the more complete spoken explanation. Their sentence/chunk timings are estimated proportionally from each narration file's measured duration; they are not forced word alignment.

## What the video demonstrates

The recording follows a connected merchant workflow: dashboard and customer history, a comeback campaign with A/B/control allocation and simulated redemptions, the voice assistant, reviewed buyer intake, a four-round three-seller negotiation, live agent events, deterministic firewall rejection, dual order approval, packing and human delivery confirmation, and simulated settlement. It also shows catalogue/document workflows, transaction CSV tools, and saved language preferences.

Customer identities and transaction records are synthetic. Campaign outcomes and payment states are simulations. The merchant-voice microphone input used for reproducible recording is a synthetic Hindi speech fixture generated through Sarvam TTS and fed through browser MediaRecorder/STT; it is not a claim about a person's live speech. Rate-card and packing-image fixtures are explicitly synthetic. A packing-image advisory never proves real delivery or authorizes settlement.

The business-model chapter is a proposal for basic insights plus a paid merchant-growth subscription. It does not claim implemented billing, validated pricing, production-scale rollout, or a commercial Paytm partnership. Paytm money movement remains disabled.

## Reproduce the export

Prerequisites: the application's Python environment and Node dependencies, Chromium for Playwright, FFmpeg with `libx264`, and `ffprobe`. Keep the Sarvam key only in the ignored backend `.env`. The API must run on port 8000 and the web application on port 3000 during recording.

From the repository root, prepare narration and demonstration fixtures:

```sh
apps/api/.venv/bin/python scripts/video/narrate.py
apps/api/.venv/bin/python scripts/video/prepare.py
```

Record the application and animated chapter cards:

```sh
node scripts/video/capture.mjs
```

This operates the application's internal synthetic workflows, including campaign simulation and simulated order confirmation. It uses the synthetic demonstration fixtures prepared above. Do not point the recording workflow at real merchant data.

The browser capture step writes `raw/<chapter-id>.webm` and a `capture.json` entry for every chapter. Each entry contains:

```json
{
  "id": "overview",
  "title": "One view of merchant growth",
  "eyebrow": "OVERVIEW",
  "narration": "The complete chapter voiceover text.",
  "caption": "A short on-screen takeaway.",
  "audio_path": "/absolute/path/to/overview-voice.wav",
  "audio_duration": 16.83,
  "duration": 18.63,
  "raw_path": "/absolute/path/to/overview.webm",
  "trim_start": 0.0,
  "capture_duration": 18.63
}
```

An interrupted capture can resume from its saved progress and synthetic workflow state:

```sh
node scripts/video/capture.mjs --resume
```

Capture must complete before final assembly. Then run:

```sh
python3 scripts/video/assemble.py --jobs 2
```

For another manifest or output directory:

```sh
python3 scripts/video/assemble.py \
  --manifest /absolute/path/to/capture.json \
  --output-dir /absolute/path/to/export \
  --jobs 2
```

At most two video encoders run simultaneously. Add `--force` to rebuild every chapter or `--no-voice-only` to omit the separate M4A. Otherwise, unchanged clips are reused only when their source files, timestamps, trim parameters, and encoding configuration match the cache fingerprint.

## Assembly and quality checks

Each source capture is trimmed to its recorded action interval and smoothly retimed to its narration chapter duration. Small speed adjustments keep longer interactions comprehensible without adding dead waiting time. The frame is scaled/padded without stretching, converted to 1080p/30 fps, and given brief 0.25-second fades. Narration starts 0.8 seconds into each chapter and is padded with silence to preserve the tail.

Chapter durations are rounded **up** to whole 30 fps frames. This provides exact audio-sample/frame boundaries at 48 kHz and avoids cumulative sub-frame drift or cutting off speech. Prepared voice files are already normalized and modestly sped up; assembly does not apply another tempo change.

The exporter verifies an audio track and a 1920×1080 video track in every encoded chapter. It probes the final MP4 to confirm H.264/AAC codecs, expected total duration, and audio/video duration agreement within 0.25 seconds. It writes the measured results to `export-summary.json` and fails rather than silently delivering an invalid export.

For a separate inspection:

```sh
ffprobe -v error -show_format -show_streams \
  -of json artifacts/pehchaan-walkthrough/Pehchaan-Walkthrough-1080p.mp4
```

The final video should also be visually reviewed at the opening, important UI interactions, the firewall block, order confirmation, and the closing card. Confirm that captions remain readable, confidential values/credentials are absent, and the spoken explanation matches the visible actions.

## Verified export result

The completed twenty-chapter export is **432.255 seconds (7 minutes 12 seconds)**, 1920×1080 at 30 fps, with H.264 video and AAC stereo audio. Its file size is 34,867,817 bytes. Video and audio durations differ by **21.3 milliseconds**, and all twenty navigation chapters are embedded.

The final scan found no black interval lasting at least 0.5 seconds and no silence interval lasting at least 5 seconds at a −42 dB threshold. Audio mean volume is −19.5 dB and peak volume is −4.2 dB, leaving clean headroom without digital clipping. Review frames from all twenty scenes were inspected together; the firewall retake prominently shows the blocked decision, and document extraction shows editable reviewed entries.
