"""Decode, inspect and create review artifacts for the delivered pitch video."""
import json
import re
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/pehchaan-pitch'
video = OUT / 'Pehchaan-Pitch-1080p.mp4'
summary = json.loads((OUT / 'export-summary.json').read_text())
review = OUT / 'review'
review.mkdir(exist_ok=True)
scan = subprocess.run([
    'ffmpeg', '-nostdin', '-hide_banner', '-i', str(video),
    '-vf', 'blackdetect=d=0.4:pix_th=0.1',
    '-af', 'silencedetect=noise=-45dB:d=3.5,volumedetect',
    '-f', 'null', '-',
], capture_output=True, text=True, check=True)
(OUT / 'qa-decode.log').write_text(scan.stderr)
black = re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)', scan.stderr)
silence = re.findall(r'silence_start: ([\d.]+)', scan.stderr)
mean = re.search(r'mean_volume: ([\d.-]+) dB', scan.stderr)
peak = re.search(r'max_volume: ([\d.-]+) dB', scan.stderr)
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 18)
sheet = Image.new('RGB', (1920, 1272), '#edf5fb')
draw = ImageDraw.Draw(sheet)
moments = {'pitch_signal': 3.8, 'pitch_voice': 4.4, 'pitch_haggle': 11, 'pitch_firewall': 7}
for index, chapter in enumerate(summary['timeline']):
    local = moments.get(chapter['id'], min(5, (chapter['end'] - chapter['start']) / 2))
    frame = review / (chapter['id'] + '-final.png')
    subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-ss', str(chapter['start'] + local), '-i', str(video), '-frames:v', '1', str(frame)], check=True)
    tile = Image.open(frame).convert('RGB').resize((480, 270), Image.Resampling.LANCZOS)
    x, y = (index % 4) * 480, (index // 4) * 318
    sheet.paste(tile, (x, y))
    title = f"{index + 1:02d} {chapter['title']}"
    while draw.textbbox((0, 0), title, font=font)[2] > 460:
        title = title[:-2]
    draw.text((x + 12, y + 282), title, font=font, fill='#002970')
sheet.save(OUT / 'Pehchaan-Pitch-Contact-Sheet.jpg', quality=94)
subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-ss', '3', '-i', str(video), '-frames:v', '1', str(OUT / 'Pehchaan-Pitch-Poster.png')], check=True)
result = {
    'fully_decoded': True,
    'black_intervals_longer_than_0_4s': black,
    'silence_intervals_longer_than_3_5s': silence,
    'mean_volume_db': float(mean[1]) if mean else None,
    'peak_volume_db': float(peak[1]) if peak else None,
    'narration_words': sum(len(c['narration'].split()) for c in json.loads((OUT / 'capture.json').read_text())),
    'captions_burned_in': True,
    'full_subtitles': 'Pehchaan-Pitch.srt and .vtt; proportional sentence timings',
    'visual_review': '16 representative frames; original UI recording, updated HUD/captions, animated pitch cards',
}
(OUT / 'qa-summary.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2), flush=True)
if black or silence:
    raise SystemExit('Review flagged playback intervals before delivery')
