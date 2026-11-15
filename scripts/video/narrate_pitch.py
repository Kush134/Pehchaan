"""Generate the revised pitch narration with the configured Sarvam provider."""
import asyncio
import base64
import hashlib
import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/api'))
from app.integrations.sarvam import SarvamProvider

OUT = ROOT / 'artifacts/pehchaan-pitch'
OUT.joinpath('audio').mkdir(parents=True, exist_ok=True)
chapters = json.loads((ROOT / 'docs/pitch-video-script.json').read_text())


async def main():
    semaphore = asyncio.Semaphore(2)

    async def one(chapter):
        async with semaphore:
            raw = OUT / 'audio' / (chapter['id'] + '.wav')
            stamp = raw.with_suffix('.sha256')
            digest = hashlib.sha256(chapter['narration'].encode()).hexdigest()
            if not raw.exists() or not stamp.exists() or stamp.read_text() != digest:
                result = await SarvamProvider().synthesize(chapter['narration'], 'en-IN')
                if not result.get('audio_base64'):
                    raise RuntimeError(chapter['id'] + ': speech generation did not return audio')
                raw.write_bytes(base64.b64decode(result['audio_base64']))
                stamp.write_text(digest)
            target = raw.with_name(raw.stem + '-voice.wav')
            # A consistent conversational pace and loudness across chapters.
            await asyncio.to_thread(subprocess.run, [
                'ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(raw),
                '-af', 'atempo=1.25,loudnorm=I=-16:TP=-1.5:LRA=9',
                '-ar', '48000', '-ac', '2', str(target),
            ], check=True)
            with wave.open(str(target)) as audio:
                duration = audio.getnframes() / audio.getframerate()
            chapter.update(audio_duration=duration, duration=round(duration + 1.8, 3), audio_path=str(target))
            print(f"NARRATED {chapter['id']}: {duration:.1f}s", flush=True)

    await asyncio.gather(*(one(chapter) for chapter in chapters))
    (OUT / 'chapters.json').write_text(json.dumps(chapters, ensure_ascii=False, indent=2))
    print(f"PREPARED {len(chapters)} chapters, {sum(c['duration'] for c in chapters):.1f}s", flush=True)


if __name__ == '__main__':
    asyncio.run(main())
