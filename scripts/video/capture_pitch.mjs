import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright';
import {execFileSync} from 'node:child_process';

const ROOT=process.cwd();
const OUT=path.join(ROOT,'artifacts/pehchaan-pitch');
const chapters=JSON.parse(await fs.readFile(path.join(ROOT,'docs/pitch-video-script.json'),'utf8'));
const cards=await fs.readFile(path.join(ROOT,'assets/video/pitch-cards.html'),'utf8');
const overlaysOnly=process.argv.includes('--overlays-only');
await fs.mkdir(path.join(OUT,'overlays'),{recursive:true});
await fs.mkdir(path.join(OUT,'cards'),{recursive:true});
await fs.mkdir(path.join(OUT,'review'),{recursive:true});
const esc=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const browser=await chromium.launch({headless:true});
const overlayContext=await browser.newContext({viewport:{width:1600,height:900},deviceScaleFactor:1});
const overlayPage=await overlayContext.newPage();
const output=[];
try {
 for(const [index,c] of chapters.entries()){
  const ui=c.kind==='ui';
  const html=`<!doctype html><html><head><style>*{box-sizing:border-box}html,body{margin:0;background:transparent;font-family:Arial,Helvetica,sans-serif;width:1600px;height:900px}header{position:absolute;left:0;top:0;width:1600px;height:66px;background:#fff;border-bottom:1px solid #c5e4f4;display:flex;align-items:center;gap:28px;padding:0 34px;color:#002970}header b{font-size:25px;letter-spacing:-1px}header b span{color:#00baf2}header .title{font-size:20px}header .label{margin-left:auto;font-size:12px;letter-spacing:1px;color:#5082a2}header .part{font-size:12px;color:#7a98af;border-left:1px solid #d9e9f4;padding-left:20px}.bottom{position:absolute;left:0;top:760px;width:1600px;height:140px;background:#f6faff}.caption{position:absolute;left:88px;top:773px;width:1424px;height:105px;border:1px solid #53bcdf;border-radius:10px;background:#00295f;color:#fff;text-align:center;display:flex;align-items:center;justify-content:center;flex-direction:column;padding:12px 22px;box-shadow:0 4px 20px #00297012}.caption small{color:#95dfff;font-size:11px;letter-spacing:1.25px;margin-bottom:8px;text-transform:uppercase}.caption div{font-size:20px;line-height:1.5;white-space:pre-line}</style></head><body>${ui?`<header><b>pehchaan <span>/</span></b><span class="title">${esc(c.title)}</span><span class="label">RECORDED PROTOTYPE FLOW</span><span class="part">${String(index+1).padStart(2,'0')} / ${chapters.length}</span></header>`:''}<div class="bottom"></div><div class="caption"><small>${esc(c.eyebrow)}</small><div>${esc(c.caption)}</div></div></body></html>`;
  await overlayPage.setContent(html);
  // Assert every caption stays within its reserved band.
  const fit=await overlayPage.locator('.caption').evaluate(el=>el.scrollHeight<=el.clientHeight+2);
  if(!fit)throw new Error(c.id+': caption overflows');
  await overlayPage.screenshot({path:path.join(OUT,'overlays',c.id+'.png'),omitBackground:true});
  if(!ui && !overlaysOnly){
   const context=await browser.newContext({viewport:{width:1600,height:900},deviceScaleFactor:1,recordVideo:{dir:path.join(OUT,'cards'),size:{width:1600,height:900}}});
   const page=await context.newPage();
   await page.setContent(cards);
   await page.waitForTimeout(200);
   await page.evaluate(id=>window.showCard(id),c.id);
   await page.waitForTimeout(3000);
   await page.screenshot({path:path.join(OUT,'review',c.id+'.png')});
   await page.waitForTimeout(2500);
   const video=page.video();
   await page.close();
   await context.close();
   const source=await video.path();
   const target=path.join(OUT,'cards',c.id+'.webm');
   await fs.rename(source,target);
   const duration=Number(execFileSync('ffprobe',['-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',target],{encoding:'utf8'}).trim());
   output.push({id:c.id,raw_path:target,trim_start:Math.max(0,duration-5.65),capture_duration:5.5});
   console.log('CAPTURED',c.id,duration.toFixed(2)+'s');
  }
 }
 if(!overlaysOnly)await fs.writeFile(path.join(OUT,'card-capture.json'),JSON.stringify(output,null,2));
} finally {await browser.close();}
