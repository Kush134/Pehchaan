import asyncio,json,sys,wave,base64,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'artifacts/pehchaan-walkthrough';sys.path.insert(0,str(ROOT/'apps/api'))
from app.integrations.sarvam import SarvamProvider
chapters=json.loads((OUT/'chapters.json').read_text())
for c in chapters:
 target=OUT/'audio'/(c['id']+'-voice.wav')
 subprocess.run(['ffmpeg','-y','-v','error','-i',str(OUT/'audio'/(c['id']+'.wav')),'-af','atempo=1.25,loudnorm=I=-16:TP=-1.5:LRA=9','-ar','48000','-ac','2',str(target)],check=True)
 with wave.open(str(target)) as w: c['audio_duration']=w.getnframes()/w.getframerate()
 c['duration']=round(c['audio_duration']+1.8,3);c['audio_path']=str(target)
(OUT/'chapters.json').write_text(json.dumps(chapters,ensure_ascii=False,indent=2))
async def fixture():
 result=await SarvamProvider().synthesize('पंद्रह रुपये डिस्काउंट और ढाई सौ रुपये मिनिमम बिल की नई कैम्पेन बनाओ।','hi-IN')
 if not result.get('audio_base64'):raise RuntimeError(result.get('error'))
 (OUT/'audio/merchant-hi.wav').write_bytes(base64.b64decode(result['audio_base64']))
 subprocess.run(['ffmpeg','-y','-v','error','-i',str(OUT/'audio/merchant-hi.wav'),'-ar','48000','-ac','1','-c:a','pcm_s16le',str(OUT/'audio/microphone.wav')],check=True)
asyncio.run(fixture())
font='/System/Library/Fonts/Supplemental/Arial.ttf';bold='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def text(draw,xy,s,size=28,color='#173451',strong=False):draw.text(xy,s,font=ImageFont.truetype(bold if strong else font,size),fill=color)
img=Image.new('RGB',(1000,720),'#ffffff');d=ImageDraw.Draw(img);d.rectangle((0,0,1000,16),fill='#00baf2');text(d,(55,55),'SHARMA KIRANA | RATE CARD',36,strong=True);text(d,(55,115),'Synthetic document for the product walkthrough',22,color='#647d93');
for i,(name,qty,unit,price) in enumerate([('Basmati Rice',100,'kg',85),('Whole Wheat Atta',100,'kg',46),('Sunflower Oil',80,'l',145),('Assorted Snacks',200,'pack',38),('Premium Tea',20,'kg',360)]):
 y=195+i*88;d.line((55,y+65,945,y+65),fill='#dae7f2',width=2);text(d,(60,y),name,28);text(d,(525,y),f'{qty} {unit}',28);text(d,(750,y),f'INR {price}',28,strong=True)
img.save(OUT/'rate-card.png')
img=Image.new('RGB',(1000,720),'#f1f8fd');d=ImageDraw.Draw(img);text(d,(55,50),'SYNTHETIC PACKING REFERENCE',34,strong=True);text(d,(55,108),'Advisory upload only. Human delivery confirmation is required.',22,color='#647d93')
for i,label in enumerate(['RICE + ATTA','OIL + TEA','SNACKS']):
 x=70+i*305;d.rounded_rectangle((x,230,x+250,515),radius=18,fill='#dfebf5',outline='#89b7d8',width=3);d.rectangle((x+110,230,x+140,515),fill='#a8c9df');d.rounded_rectangle((x+20,335,x+230,405),radius=8,fill='white');text(d,(x+35,350),label,23,strong=True)
text(d,(55,600),'Illustrated sample: no claim of real goods or delivery.',23,color='#647d93');img.save(OUT/'packing-reference.png')
print('PREPARED',len(chapters),'chapters;',round(sum(c['duration'] for c in chapters),1),'seconds')
