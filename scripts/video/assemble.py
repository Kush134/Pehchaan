#!/usr/bin/env python3
"""Assemble real Pehchaan UI recordings with prepared narration.

No image generation, fabricated screens, or subtitle/font rendering is performed
here. Chapter headings, animated callouts, and burned captions are recorded in the
browser. External SRT/VTT files carry the complete narration for accessibility.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = PROJECT / 'artifacts' / 'pehchaan-walkthrough'
ASSEMBLER_VERSION = '2026-11-14-v1'
FPS = 30
HEAD_DELAY = 0.8
WIDTH, HEIGHT = 1920, 1080


def run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {command[0]}\n{result.stderr[-5000:]}")


def probe(path: Path) -> dict:
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def stream_duration(stream: dict, fallback: float = 0.0) -> float:
    try:
        return float(stream.get('duration', fallback))
    except (ValueError, TypeError):
        return fallback


def resolve_path(value: str, manifest_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    # Capture scripts may write repository-relative or manifest-relative paths.
    repository_path = PROJECT / path
    return repository_path if repository_path.exists() else manifest_dir / path


def target_seconds(chapter: dict) -> float:
    # A full video frame is exactly 1600 audio samples at 48 kHz. Quantizing up
    # avoids narration loss and prevents sub-frame drift across concatenated clips.
    return math.ceil(float(chapter['duration']) * FPS) / FPS


def fingerprint(chapter: dict, raw: Path, voice: Path, duration: float) -> str:
    payload = {
        'version': ASSEMBLER_VERSION,
        'assembler_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'raw': str(raw), 'raw_size': raw.stat().st_size,
        'raw_mtime': raw.stat().st_mtime_ns,
        'voice': str(voice), 'voice_size': voice.stat().st_size,
        'voice_mtime': voice.stat().st_mtime_ns,
        'trim_start': float(chapter.get('trim_start', 0)),
        'capture_duration': float(chapter['capture_duration']),
        'target_duration': duration, 'fps': FPS, 'width': WIDTH, 'height': HEIGHT,
        'voice_head_delay': HEAD_DELAY, 'codec': 'libx264', 'crf': 19,
        'preset': 'fast', 'audio_codec': 'aac', 'audio_bitrate': '192k',
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def encode_chapter(index: int, chapter: dict, manifest_dir: Path, clips_dir: Path, force: bool) -> dict:
    identifier = chapter['id']
    if not re.fullmatch(r'[a-z0-9_-]+', identifier):
        raise ValueError(f'Invalid chapter identifier: {identifier!r}')
    raw = resolve_path(chapter['raw_path'], manifest_dir)
    voice = resolve_path(chapter['audio_path'], manifest_dir)
    if not raw.is_file() or not voice.is_file():
        raise FileNotFoundError(f'Capture or narration missing for chapter {identifier}')
    duration = target_seconds(chapter)
    voice_duration = float(probe(voice)['format']['duration'])
    if voice_duration + HEAD_DELAY > duration + 0.02:
        raise ValueError(f'{identifier}: narration would be cut off ({voice_duration:.3f}s in {duration:.3f}s clip)')
    output = clips_dir / f'{index + 1:02d}-{identifier}.mp4'
    cache_path = output.with_suffix('.cache.json')
    digest = fingerprint(chapter, raw, voice, duration)
    if not force and output.exists() and cache_path.exists():
        cached = json.loads(cache_path.read_text())
        if cached.get('fingerprint') == digest and output.stat().st_mtime_ns >= max(raw.stat().st_mtime_ns, voice.stat().st_mtime_ns):
            print(f'[{index + 1:02d}] Reusing {identifier} ({duration:.2f}s)', flush=True)
            return {**chapter, 'clip_path': str(output), 'target_duration': duration, 'cached': True}
    raw_duration = float(probe(raw)['format']['duration'])
    trim_start = max(0.0, float(chapter.get('trim_start', 0)))
    capture_duration = min(float(chapter['capture_duration']), raw_duration - trim_start)
    if capture_duration <= 0:
        raise ValueError(f'{identifier}: recording ends before trim_start')
    frames = round(duration * FPS)
    video_filter = (
        f'trim=start={trim_start:.6f}:duration={capture_duration:.6f},'
        f'setpts={(duration / capture_duration):.10f}*(PTS-STARTPTS),'
        f'scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,'
        f'pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=white,'
        f'setsar=1,fps={FPS},tpad=stop_mode=clone:stop_duration=1,'
        f'trim=duration={duration:.6f},'
        f'fade=t=in:st=0:d=0.25,fade=t=out:st={max(0.0,duration - .25):.6f}:d=0.25,'
        'format=yuv420p'
    )
    audio_filter = f'adelay=800:all=1,apad,atrim=duration={duration:.6f},asetpts=PTS-STARTPTS'
    print(f'[{index + 1:02d}] Encoding {identifier}: {capture_duration:.2f}s capture → {duration:.2f}s chapter', flush=True)
    temporary = output.with_name(output.stem + '.partial.mp4')
    run([
        'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
        '-filter_threads', '1', '-i', str(raw), '-i', str(voice),
        '-map', '0:v:0', '-map', '1:a:0', '-vf', video_filter, '-af', audio_filter,
        '-c:v', 'libx264', '-crf', '19', '-preset', 'fast', '-threads', '3',
        '-pix_fmt', 'yuv420p', '-r', str(FPS), '-frames:v', str(frames),
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2',
        '-t', f'{duration:.6f}', '-movflags', '+faststart', str(temporary),
    ])
    encoded = probe(temporary)
    video = next((s for s in encoded['streams'] if s['codec_type'] == 'video'), None)
    audio = next((s for s in encoded['streams'] if s['codec_type'] == 'audio'), None)
    if not video or not audio or video['width'] != WIDTH or video['height'] != HEIGHT:
        raise RuntimeError(f'{identifier}: encoded clip is missing required 1080p video or audio')
    if abs(float(encoded['format']['duration']) - duration) > 0.15:
        raise RuntimeError(f'{identifier}: encoded duration does not match the chapter timeline')
    temporary.replace(output)
    cache_path.write_text(json.dumps({'fingerprint': digest, 'probe': encoded}, indent=2) + '\n')
    print(f'[{index + 1:02d}] Finished {identifier}', flush=True)
    return {**chapter, 'clip_path': str(output), 'target_duration': duration, 'cached': False}


def timestamp(seconds: float, *, srt: bool) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d}{"," if srt else "."}{millis:03d}'


def narration_chunks(text: str) -> list[str]:
    chunks = []
    for sentence in re.split(r'(?<=[.!?])\s+', text.strip()):
        words = sentence.split()
        while len(words) > 16:
            take = 14 if len(words) - 14 >= 8 else math.ceil(len(words) / 2)
            chunks.append(' '.join(words[:take]))
            words = words[take:]
        if words:
            chunks.append(' '.join(words))
    return chunks


def write_subtitles(chapters: list[dict], output_dir: Path, stem: str = 'Pehchaan-Walkthrough') -> tuple[Path, Path, list[dict]]:
    cues, timeline = [], []
    chapter_start = 0.0
    for chapter in chapters:
        duration = chapter['target_duration']
        timeline.append({'id': chapter['id'], 'title': chapter['title'], 'start': chapter_start, 'end': chapter_start + duration})
        chunks = narration_chunks(chapter['narration'])
        total_words = sum(len(chunk.split()) for chunk in chunks)
        audio_duration = float(chapter['audio_duration'])
        spoken_start = chapter_start + HEAD_DELAY
        word_cursor = 0
        for chunk in chunks:
            count = len(chunk.split())
            start = spoken_start + audio_duration * word_cursor / total_words
            word_cursor += count
            end = spoken_start + audio_duration * word_cursor / total_words
            cues.append((start, end, '\n'.join(textwrap.wrap(chunk, width=48))))
        chapter_start += duration
    srt, vtt = output_dir / (stem + '.srt'), output_dir / (stem + '.vtt')
    srt.write_text('\n\n'.join(f'{i}\n{timestamp(start,srt=True)} --> {timestamp(end,srt=True)}\n{text}' for i,(start,end,text) in enumerate(cues,1))+'\n', encoding='utf-8')
    vtt.write_text('WEBVTT\n\n'+'\n\n'.join(f'{timestamp(start,srt=False)} --> {timestamp(end,srt=False)}\n{text}' for start,end,text in cues)+'\n', encoding='utf-8')
    return srt, vtt, timeline


def escape_metadata(value: str) -> str:
    return value.replace('\\', '\\\\').replace('\n', ' ').replace('=', '\\=').replace(';', '\\;').replace('#', '\\#')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_DIR / 'capture.json')
    parser.add_argument('--output-dir', type=Path, default=None)
    parser.add_argument('--jobs', type=int, default=2, choices=[1,2], help='At most two simultaneous encoders')
    parser.add_argument('--force', action='store_true', help='Re-encode cached chapter clips')
    parser.add_argument('--no-voice-only', action='store_true', help='Skip the standalone M4A narration export')
    parser.add_argument('--output-stem', default='Pehchaan-Walkthrough', help='Filename stem for the MP4 and subtitles')
    parser.add_argument('--title', default='Pehchaan — Merchant Growth AI Walkthrough', help='Embedded video title')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.output_stem):
        raise ValueError('Output stem must contain only letters, numbers, underscores or hyphens')
    for tool in ('ffmpeg', 'ffprobe'):
        if shutil.which(tool) is None:
            raise RuntimeError(f'{tool} is required on PATH')
    manifest = args.manifest.resolve()
    loaded = json.loads(manifest.read_text())
    chapters = loaded['chapters'] if isinstance(loaded,dict) else loaded
    if not isinstance(chapters,list) or not chapters:
        raise ValueError('Capture manifest must contain a nonempty chapter list')
    output_dir = (args.output_dir or manifest.parent).resolve()
    clips_dir = output_dir / 'clips'
    clips_dir.mkdir(parents=True, exist_ok=True)
    ordered: list[dict | None] = [None] * len(chapters)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(encode_chapter, index, chapter, manifest.parent, clips_dir, args.force):index for index,chapter in enumerate(chapters)}
        for future in concurrent.futures.as_completed(futures):
            ordered[futures[future]] = future.result()
    encoded = [chapter for chapter in ordered if chapter is not None]
    srt, vtt, timeline = write_subtitles(encoded, output_dir, args.output_stem)
    metadata = output_dir / 'chapters.ffmetadata'
    entries = [';FFMETADATA1', 'title='+escape_metadata(args.title), 'artist=Pehchaan', 'comment=Actual application capture; synthetic merchant records; simulated payments; AI-generated Sarvam narration.']
    for chapter in timeline:
        entries.extend(['[CHAPTER]', 'TIMEBASE=1/1000', f'START={round(chapter["start"]*1000)}', f'END={round(chapter["end"]*1000)}', 'title='+escape_metadata(chapter['title'])])
    metadata.write_text('\n'.join(entries)+'\n', encoding='utf-8')
    concat_file = output_dir / 'concat.txt'
    concat_file.write_text('\n'.join("file '"+chapter['clip_path'].replace("'", "'\\''")+"'" for chapter in encoded)+'\n', encoding='utf-8')
    final = output_dir / (args.output_stem + '-1080p.mp4')
    final_temporary = final.with_name(final.stem + '.partial.mp4')
    print('Joining chapter clips and embedding navigation chapters…', flush=True)
    run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat_file),'-f','ffmetadata','-i',str(metadata),'-map','0:v:0','-map','0:a:0','-map_metadata','1','-map_chapters','1','-c','copy','-movflags','+faststart',str(final_temporary)])
    result = probe(final_temporary)
    video = next(s for s in result['streams'] if s['codec_type']=='video')
    audio = next(s for s in result['streams'] if s['codec_type']=='audio')
    actual_duration = float(result['format']['duration'])
    expected_duration = sum(chapter['target_duration'] for chapter in encoded)
    delta = abs(stream_duration(video,actual_duration)-stream_duration(audio,actual_duration))
    if video['codec_name']!='h264' or audio['codec_name']!='aac' or (video['width'],video['height'])!=(WIDTH,HEIGHT):
        raise RuntimeError('Final MP4 has unexpected video/audio encoding')
    if delta>.25 or abs(actual_duration-expected_duration)>.3:
        raise RuntimeError(f'Final duration mismatch: expected={expected_duration:.3f}, actual={actual_duration:.3f}, audio/video delta={delta:.3f}')
    final_temporary.replace(final)
    if not args.no_voice_only:
        voice_only = output_dir / ('Pehchaan-Voiceover.m4a' if args.output_stem == 'Pehchaan-Walkthrough' else args.output_stem + '-Voiceover.m4a')
        run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-i',str(final),'-vn','-c:a','copy','-movflags','+faststart',str(voice_only)])
    summary = {'video':str(final),'subtitles_srt':str(srt),'subtitles_vtt':str(vtt),'chapters':len(encoded),'duration_seconds':actual_duration,'video_duration_seconds':stream_duration(video,actual_duration),'audio_duration_seconds':stream_duration(audio,actual_duration),'audio_video_delta_seconds':delta,'resolution':[WIDTH,HEIGHT],'fps':FPS,'video_codec':video['codec_name'],'audio_codec':audio['codec_name'],'size_bytes':final.stat().st_size,'cached_chapters':sum(chapter['cached'] for chapter in encoded),'timeline':timeline,'subtitles_note':'Sentence/chunk timings are proportional estimates from actual narration durations, not forced word alignment.'}
    (output_dir/'export-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2), flush=True)


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print(f'Assembly failed: {exc}',file=sys.stderr,flush=True)
        raise SystemExit(1)
