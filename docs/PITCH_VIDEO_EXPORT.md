# Pehchaan: pitch-led hackathon video

The revised video is **4 minutes 52 seconds**, 1920×1080 at 30 fps, H.264/AAC. It contains 16 navigation chapters, real application screen recordings, animated pitch sections, short burned-in captions and Sarvam-generated English narration. The original seven-minute full walkthrough remains preserved in `artifacts/pehchaan-walkthrough/`.

## Deliverables

- `artifacts/pehchaan-pitch/Pehchaan-Pitch-1080p.mp4` — revised pitch-led demo.
- `artifacts/pehchaan-pitch/Pehchaan-Pitch.srt` and `.vtt` — optional complete narration subtitles.
- `artifacts/pehchaan-pitch/Pehchaan-Pitch-Voiceover.m4a` — audio-only narration.
- `artifacts/pehchaan-pitch/Pehchaan-Pitch-Poster.png` and `Pehchaan-Pitch-Contact-Sheet.jpg` — review artifacts.
- `docs/PITCH_STORY.md` — the complete narration and question-to-section mapping.
- `docs/PITCH_EVIDENCE.md` — primary sources, assumptions and boundaries.

## Editorial choices

The launch segment is one owner-operated kirana in Wakad, Pune, with a 1–3-person team, Hindi/Marathi preference and usable, consented repeat-customer history. This is a chosen customer profile, not claimed interview evidence. The STEM-student example is not a product pivot.

The three hero capabilities are Comeback, Voice Copilot, and Haggle with deterministic mandate guardrails. Catalogue, import, analytics and audit screens remain supporting tools, and are covered in the full walkthrough.

Monthly revenue at risk of ₹6,000, gross profit at risk of ₹1,320 at an assumed 22% margin, and a separate time scenario of 8h40m are illustrative assumptions. They are not observed merchant losses, realised savings or product results. Frequency, willingness to pay, pricing, comparative value, ten-shop pilot and Paytm partnership remain unvalidated.

The market comparison gives existing products credit for documented capabilities. Pehchaan’s differentiation is a connected workflow hypothesis, not a claim of market exclusivity or competitor failure.

## Capture and narration provenance

The six UI scenes reuse original browser screen recordings of the working prototype. Old chapter labels are cropped out; new headings and captions are added. UI footage is retimed to fit the revised voiceover. Animated title/pitch cards are captured from `assets/video/pitch-cards.html`; after the entrance animation their final frame is held. No application mockups replace the UI.

All merchant/customer records are synthetic. Campaign outcomes and payment lifecycles are simulated. No real Paytm money moves. The original voice demo used a synthetic Hindi microphone fixture passed through MediaRecorder and genuine Sarvam speech recognition/interpretation. The English narration is AI-generated and does not imitate a named person.

Takeaway captions are burned in. Complete SRT/VTT sentence timings are estimated proportionally from measured narration durations; they are not forced word alignment.

## Reproduce

Run from the repository root with installed Node dependencies/Playwright Chromium, the API virtual environment, and FFmpeg/ffprobe. Sarvam credentials are loaded server-side from the ignored `.env` and never embedded in assets. The original UI source recordings must remain available. Reusing them does not reset or mutate application data.

```sh
apps/api/.venv/bin/python scripts/video/narrate_pitch.py
node scripts/video/capture_pitch.mjs
apps/api/.venv/bin/python scripts/video/compose_pitch.py
python3 scripts/video/assemble.py --manifest artifacts/pehchaan-pitch/capture.json --output-dir artifacts/pehchaan-pitch --output-stem Pehchaan-Pitch --title 'Pehchaan — The Kirana Growth Copilot'
apps/api/.venv/bin/python scripts/video/review_pitch.py
```

The export summary records measured codecs, file size, chapter timings and A/V duration delta. QA performs a full decode, checks for black intervals exceeding 0.4 seconds and silence exceeding 3.5 seconds, and creates one review frame per chapter.

## Chapters

| Start | Section |
| --- | --- |
| 00:00 | Pehchaan, in one sentence |
| 00:14 | Exactly who we are building for |
| 00:35 | A recurring decision, not a rare event |
| 00:51 | What is the cost of missing the signal? |
| 01:16 | Useful products already exist |
| 01:40 | Three core capabilities |
| 01:59 | Demo one: recognize the returning customer |
| 02:18 | Prepare an eligible next action |
| 02:32 | Close the loop with evidence |
| 02:48 | Demo two: approve it in a familiar language |
| 03:04 | Demo three: negotiate within the mandate |
| 03:21 | Trust is a rule, not a promise |
| 03:39 | Our difference is the connected workflow |
| 03:58 | A company built around merchant value |
| 04:18 | The next step is a focused pilot |
| 04:36 | The merchant's next payment |
