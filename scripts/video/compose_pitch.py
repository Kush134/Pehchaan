"""Reframe existing real UI captures and animated cards for the revised pitch."""
import concurrent.futures
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/pehchaan-pitch'
chapters = json.loads((OUT / 'chapters.json').read_text())
originals = {c['id']: c for c in json.loads((ROOT / 'artifacts/pehchaan-walkthrough/capture.json').read_text())}
cards = {c['id']: c for c in json.loads((OUT / 'card-capture.json').read_text())}
(OUT / 'raw').mkdir(exist_ok=True)


def compose(chapter):
    ui = chapter['kind'] == 'ui'
    source = originals[chapter['source_id']] if ui else cards[chapter['id']]
    duration = math.ceil(chapter['duration'] * 30) / 30
    offset, captured = float(source['trim_start']), float(source['capture_duration'])
    target = OUT / 'raw' / (chapter['id'] + '.mp4')
    # Remove the old chapter HUD and caption pixels. The central region is the
    # original application recording, including real pointer and click motion.
    video = f'[0:v]trim=start={offset:.6f}:duration={captured:.6f},setpts=PTS-STARTPTS,'
    if ui:
        video += f'crop=1600:694:0:66,pad=1600:900:0:66:color=0xf6faff,setpts={duration / captured:.10f}*PTS,'
    video += f'fps=30,tpad=stop_mode=clone:stop_duration={duration:.6f},trim=duration={duration:.6f}[scene];[scene][1:v]overlay=0:0:format=auto,format=yuv420p[v]'
    subprocess.run([
        'ffmpeg', '-nostdin', '-y', '-v', 'error', '-filter_complex_threads', '1',
        '-i', source['raw_path'], '-i', str(OUT / 'overlays' / (chapter['id'] + '.png')),
        '-filter_complex', video, '-map', '[v]', '-an', '-t', str(duration),
        '-c:v', 'libx264', '-crf', '18', '-preset', 'fast', '-threads', '3',
        '-movflags', '+faststart', str(target),
    ], check=True)
    chapter.update(raw_path=str(target), trim_start=0, capture_duration=duration)
    print(f"COMPOSED {chapter['id']}: {duration:.2f}s", flush=True)
    return chapter


with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    output = list(pool.map(compose, chapters))
(OUT / 'capture.json').write_text(json.dumps(output, ensure_ascii=False, indent=2))
print('READY', len(output), 'chapters', flush=True)
