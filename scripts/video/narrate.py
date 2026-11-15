import asyncio,json,sys,wave,base64
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'apps/api'))
from app.integrations.sarvam import SarvamProvider
OUT=ROOT/'artifacts/pehchaan-walkthrough/audio'
chapters=json.loads((ROOT/'docs/video-script.json').read_text())
if isinstance(chapters,dict):chapters=chapters.get('chapters',chapters.get('scenes',[]))
async def main():
 semaphore=asyncio.Semaphore(2)
 async def one(c):
  async with semaphore:
   path=OUT/(c['id']+'.wav')
   if not path.exists():
    result=await SarvamProvider().synthesize(c['narration'],'en-IN')
    if not result.get('audio_base64'):raise RuntimeError(c['id']+': '+str(result.get('error')))
    path.write_bytes(base64.b64decode(result['audio_base64']))
   with wave.open(str(path)) as f:duration=f.getnframes()/f.getframerate()
   c['audio_duration']=round(duration,3);c['duration']=round(duration+2,3)
   print(f"NARRATION {c['id']}: {duration:.1f}s",flush=True)
 await asyncio.gather(*(one(c) for c in chapters))
 (OUT.parent/'chapters.json').write_text(json.dumps(chapters,ensure_ascii=False,indent=2))
 print('TOTAL seconds',sum(c['duration'] for c in chapters),flush=True)
asyncio.run(main())
