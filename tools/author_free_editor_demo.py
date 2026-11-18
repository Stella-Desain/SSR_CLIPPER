"""Author two bespoke editorial films; no campaign template is used."""
from pathlib import Path
import json
import html
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'output/editor-free-20261007'

COMMON_CSS='''
@font-face{font-family:Editorial;src:url('fonts/MontserratBlack.ttf');font-weight:900}
@font-face{font-family:Literary;src:url('fonts/Georgia.ttf');font-weight:400}
@font-face{font-family:Detail;src:url('fonts/Consolas.ttf');font-weight:400}
*{box-sizing:border-box}html,body{margin:0;width:1080px;height:1920px;overflow:hidden;background:var(--ink);color:var(--paper)}
#root{width:100%;height:100%;position:relative;overflow:hidden;font-family:Editorial,sans-serif}
.stage{position:absolute;left:0;top:0;width:1080px;height:1920px;overflow:hidden;border-radius:0;z-index:1;transform-origin:50% 50%}
.stage video,.stage img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:47% 50%}
.shade{position:absolute;inset:0;z-index:2;background:linear-gradient(180deg,rgba(17,19,15,.60),transparent 30%,transparent 50%,rgba(17,19,15,.84) 75%,var(--ink));pointer-events:none}
.byline{position:absolute;left:82px;top:122px;font:30px Detail,monospace;letter-spacing:3px;z-index:9;color:var(--paper)}
.caption{position:absolute;left:88px;top:1230px;width:820px;height:185px;display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;align-content:center;z-index:20;text-align:center;opacity:0;font-size:56px;line-height:1.16;letter-spacing:-1.5px;text-shadow:0 4px 4px rgba(0,0,0,.75),0 0 18px rgba(0,0,0,.75);padding:14px 8px}
.caption span{display:inline-block}.hero{position:absolute;left:82px;top:280px;z-index:10;max-width:830px;font-size:92px;line-height:.98;letter-spacing:-4px;opacity:0}
.hero em{font-family:Literary,serif;font-weight:400;letter-spacing:-3px;color:var(--accent);font-style:italic}
.rule{position:absolute;left:82px;top:205px;width:200px;height:4px;background:var(--accent);z-index:10;transform-origin:left}
.section{position:absolute;inset:0;z-index:5;opacity:0;pointer-events:none}
.section .heading{position:absolute;left:82px;top:255px;max-width:790px;font-size:78px;line-height:1.02;letter-spacing:-3px}
.section .heading em{font-family:Literary,serif;font-weight:400;color:var(--accent)}
.note{font:28px Detail,monospace;letter-spacing:2px;color:var(--paper)}
.end-line{position:absolute;left:82px;top:960px;max-width:800px;font-size:80px;line-height:1.04;letter-spacing:-3px;z-index:10;opacity:0}
.end-line em{font-family:Literary,serif;color:var(--accent);font-weight:400}
.caption-screen{position:absolute;left:40px;top:1200px;width:970px;height:220px;background:linear-gradient(180deg,transparent,rgba(17,19,15,.72) 28%,rgba(17,19,15,.72) 75%,transparent);z-index:15}
svg{overflow:visible} .draw-path{fill:none;stroke:var(--accent);stroke-width:4;stroke-linecap:round;stroke-linejoin:round}
'''


def groups(words):
    result=[]; current=[]
    for index,w in enumerate(words):
        current.append(w)
        next_start=words[index+1]['start'] if index+1<len(words) else w['end']+.07
        if len(current)>=4 or w['text'].endswith(('.', '?','!')) or next_start-w['end']>.25 or index+1==len(words):
            result.append({'words':current,'start':max(0,current[0]['start']),
                'end':min(next_start, current[-1]['end']+.08)})
            current=[]
    return result


def captions_js(groups_data, accent):
    return '''
const GROUPS=__GROUPS__;
const EMPHASIS=new Set(['progres','keliatan','akarnya','pohon','tanah','kesuksesan','sukses','skill','tree','ngacak','accounting','manajerial','sistem','sop']);
GROUPS.forEach((g,i)=>{
 const el=document.createElement('div');el.className='caption clip';el.id='caption-'+i;
 el.dataset.start=g.start;el.dataset.duration=g.end-g.start;el.dataset.trackIndex='5';
 g.words.forEach((w,j)=>{const span=document.createElement('span');span.textContent=w.text;span.id='word-'+i+'-'+j;el.appendChild(span)});
 document.getElementById('caption-layer').appendChild(el);
 const count=g.words.reduce((n,w)=>n+w.text.length,0);
 if(count>27)el.style.fontSize='49px';
 tl.fromTo(el,{opacity:0,y:14},{opacity:1,y:0,duration:Math.min(.12,(g.end-g.start)/3),ease:'power3.out',immediateRender:false},g.start);
 g.words.forEach((w,j)=>{
  const span=document.getElementById('word-'+i+'-'+j);
  tl.to(span,{color:'__ACCENT__',duration:.055,ease:'none'},Math.max(g.start,w.start));
  tl.to(span,{color:paper,duration:.06,ease:'none'},Math.min(g.end-.015,w.end));
  if(EMPHASIS.has(w.text.toLowerCase().replace(/[^a-z]/g,'')))
   tl.fromTo(span,{scale:.97},{scale:1.065,duration:Math.min(.14,w.end-w.start),ease:'back.out(1.2)',immediateRender:false},Math.max(g.start,w.start));
 });
 tl.set(el,{opacity:0},g.end);
});
'''.replace('__GROUPS__',json.dumps(groups_data,ensure_ascii=False)).replace('__ACCENT__',accent)


def root_svg():
    branches=[
        'M 420 320 C 420 395 300 402 260 480 S 250 610 180 670',
        'M 420 320 C 410 408 485 454 485 550 S 520 660 585 722',
        'M 420 350 C 340 432 365 527 340 610 S 350 712 295 790',
        'M 420 364 C 450 436 610 460 650 540 S 682 678 746 710',
        'M 278 455 C 192 490 200 533 120 573',
        'M 485 522 C 555 545 580 590 612 623',
        'M 339 573 C 270 608 270 650 215 682',
        'M 652 543 C 745 550 745 618 807 646',
        'M 420 333 C 433 440 423 604 426 784',
        'M 424 687 C 468 725 445 750 470 803',
    ]
    paths=''.join(f'<path class="root-branch draw-path" id="root-b-{i}" pathLength="1" d="{d}" />' for i,d in enumerate(branches))
    return f'''<svg id="roots-svg" viewBox="0 0 850 850" width="850" height="850" aria-label="Ilustrasi akar tumbuh sebelum hasil terlihat">
    <path d="M 50 320 H 800" stroke="var(--paper)" opacity=".35" stroke-width="2"/>
    <path id="stem" class="draw-path" pathLength="1" d="M420 320 C416 260 443 207 425 175"/>
    <path id="leaf" d="M426 214 C367 218 357 151 386 142 C440 144 453 190 426 214" fill="var(--accent)"/>
    {paths}<circle id="seed" cx="420" cy="320" r="11" fill="var(--accent)"/>
    </svg>'''


def film_one():
    markup=f'''
<div id="opening" class="hero">BELUM<br>KELIHATAN.<br><em>Tetap tumbuh.</em></div>
<div id="quiet-header" class="hero" style="top:237px;font-size:64px">PROGRES YANG<br><em>tak terlihat.</em></div>
<div id="roots-scene" class="section" style="background:var(--ink)">
 <div class="heading" id="roots-heading">AKAR DULU.<br><em>Hasil nanti.</em></div>
 <div id="roots-art" style="position:absolute;left:110px;top:475px">{root_svg()}</div>
 <div id="below-ground" class="note" style="position:absolute;left:130px;top:1450px">YANG TUMBUH BELUM TENTU TERLIHAT.</div>
 <div id="small-seed" style="position:absolute;left:100px;top:1510px;width:8px;height:8px;background:var(--accent);border-radius:50%"></div>
</div>
<div id="score-scene" class="section">
 <div id="score-80" style="position:absolute;left:85px;top:440px;font-size:158px;line-height:1;color:var(--accent)">80</div>
 <div id="score-90" style="position:absolute;left:700px;top:580px;font-size:158px;line-height:1;color:var(--accent)">90</div>
</div>
<div id="ending" class="end-line">ADA HASIL<br>YANG DATANG<br><em>belakangan.</em></div>
'''
    timeline='''
tl.fromTo('#byline',{opacity:0,x:-18},{opacity:1,x:0,duration:.48,ease:'power2.out'},.15);
tl.fromTo('#rule',{scaleX:0},{scaleX:1,duration:.75,ease:'expo.out'},.3);
tl.fromTo('#opening',{opacity:0,y:35},{opacity:1,y:0,duration:.65,ease:'power3.out'},.28);
tl.to('#opening',{opacity:0,duration:.4,ease:'sine.inOut'},4.3);
tl.to('#stage',{x:68,y:475,width:944,height:730,borderRadius:34,duration:.65,ease:'power3.inOut'},4.35);
tl.fromTo('#quiet-header',{opacity:0,y:18},{opacity:1,y:0,duration:.55,ease:'power2.out'},4.6);
tl.to('#quiet-header',{opacity:0,duration:.45,ease:'sine.inOut'},14.05);
tl.fromTo('#roots-scene',{opacity:0},{opacity:1,duration:.55,ease:'sine.inOut'},14.1);
tl.fromTo('#roots-heading',{opacity:0,y:24},{opacity:1,y:0,duration:.55,ease:'power2.out'},14.35);
tl.fromTo('#roots-art',{opacity:0,scale:.98},{opacity:1,scale:1,duration:.6,ease:'power3.out'},14.5);
tl.fromTo('#seed',{scale:0},{scale:1,duration:.55,ease:'back.out(1.4)',transformOrigin:'50% 50%'},14.4);
document.querySelectorAll('.root-branch').forEach((p,i)=>{
 p.style.strokeDasharray='1';p.style.strokeDashoffset='1';
 tl.to(p,{strokeDashoffset:0,duration:2.2+i*.06,ease:'sine.inOut'},14.8+i*.18);
});
document.getElementById('stem').style.strokeDasharray='1';document.getElementById('stem').style.strokeDashoffset='1';
tl.to('#stem',{strokeDashoffset:0,duration:1.1,ease:'power2.out'},17.25);
tl.fromTo('#leaf',{opacity:0},{opacity:1,duration:.8,ease:'sine.out'},18.05);
tl.fromTo('#below-ground',{opacity:0,x:-14},{opacity:1,x:0,duration:.6,ease:'expo.out'},16.5);
tl.fromTo('#small-seed',{opacity:.3,scale:.7},{opacity:.9,scale:1.3,duration:1.2,yoyo:true,repeat:2,ease:'sine.inOut'},15.3);
tl.to('#roots-scene',{opacity:0,duration:.6,ease:'sine.inOut'},20.05);
tl.to('#stage',{x:0,y:0,width:1080,height:1920,borderRadius:0,duration:.6,ease:'power3.inOut'},20.05);
tl.fromTo('#score-scene',{opacity:0},{opacity:1,duration:.24,ease:'power2.out'},31.55);
tl.fromTo('#score-80',{opacity:0,y:20,scale:.9},{opacity:1,y:0,scale:1,duration:.26,ease:'back.out(1.15)'},31.75);
tl.fromTo('#score-90',{opacity:0,x:20},{opacity:1,x:0,duration:.25,ease:'expo.out'},32.30);
tl.to('#score-scene',{opacity:0,duration:.35,ease:'sine.inOut'},33.65);
tl.to('#stage',{x:60,y:245,width:960,height:700,borderRadius:28,duration:.6,ease:'power3.inOut'},35.0);
tl.fromTo('#ending',{opacity:0,y:20},{opacity:1,y:0,duration:.75,ease:'power2.out'},35.7);
tl.to('#stage',{scale:1.025,duration:7.5,ease:'none'},35.7);
tl.to('#rule',{scaleX:1.45,duration:4,ease:'sine.inOut'},37.0);
'''
    return markup,timeline


def film_two():
    markup='''
<div id="opening" class="hero">HIDUP PUNYA<br><em>skill tree.</em></div>
<div id="tree-scene" class="section" style="background:var(--ink)">
 <div id="tree-title" class="heading" style="max-width:550px;top:290px">SKILL<br><em>yang nyambung.</em></div>
 <svg id="tree-map" viewBox="0 0 900 690" width="900" height="690" style="position:absolute;left:65px;top:610px" aria-label="Ilustrasi skill yang saling terhubung">
  <g id="tree-lines" fill="none" stroke="var(--accent)" stroke-width="4" stroke-linecap="round">
   <path class="tree-branch" pathLength="1" d="M450 550 L450 400 L170 220 L170 105"/>
   <path class="tree-branch" pathLength="1" d="M450 400 L450 115"/>
   <path class="tree-branch" pathLength="1" d="M450 400 L730 220 L730 105"/>
  </g>
  <g id="broken-links" stroke="var(--paper)" opacity=".30" stroke-width="2" stroke-dasharray="8 12">
   <path d="M170 130 L610 400 M730 140 L230 460 M450 100 L120 310"/>
  </g>
  <circle id="tree-core" cx="450" cy="550" r="31" fill="var(--accent)"/>
  <g id="node-a"><circle cx="170" cy="100" r="48" fill="var(--ink)" stroke="var(--accent)" stroke-width="4"/><text x="170" y="113" text-anchor="middle" fill="var(--paper)" font-size="36" font-family="Detail">01</text></g>
  <g id="node-b"><circle cx="450" cy="100" r="48" fill="var(--ink)" stroke="var(--accent)" stroke-width="4"/><text x="450" y="113" text-anchor="middle" fill="var(--paper)" font-size="36" font-family="Detail">02</text></g>
  <g id="node-c"><circle cx="730" cy="100" r="48" fill="var(--ink)" stroke="var(--accent)" stroke-width="4"/><text x="730" y="113" text-anchor="middle" fill="var(--paper)" font-size="36" font-family="Detail">03</text></g>
 </svg>
 <div id="scattered" style="position:absolute;left:84px;top:1430px;font:italic 60px Literary;color:var(--paper)">Jangan asal menambah skill.</div>
 <div id="connected" style="position:absolute;left:84px;top:1430px;font:italic 60px Literary;color:var(--accent)">Bangun satu cabang sampai utuh.</div>
</div>
<div id="business-scene" class="section" style="background:var(--ink)">
 <div id="business-title" class="heading" style="top:280px;max-width:570px">CONTOH:<br><em>bangun bisnis.</em></div>
 <svg id="business-lines" width="840" height="650" viewBox="0 0 840 650" style="position:absolute;left:90px;top:580px">
  <path id="business-spine" d="M100 60 V 565" stroke="var(--accent)" stroke-width="4" fill="none" pathLength="1"/>
  <path d="M100 85 H220 M100 275 H220 M100 465 H220" stroke="var(--accent)" stroke-width="4" fill="none"/>
  <circle cx="100" cy="85" r="12" fill="var(--accent)"/><circle cx="100" cy="275" r="12" fill="var(--accent)"/><circle cx="100" cy="465" r="12" fill="var(--accent)"/>
 </svg>
 <div id="business-a" class="business-node" style="top:630px"><span>01</span>AKUNTANSI<small>Pahami bahasa angka.</small></div>
 <div id="business-b" class="business-node" style="top:820px"><span>02</span>MANAJEMEN<small>Atur orang dan pekerjaan.</small></div>
 <div id="business-c" class="business-node" style="top:1010px"><span>03</span>SISTEM<small>SOP yang bisa direplikasi.</small></div>
</div>
<div id="ending" class="end-line">SATU ARAH.<br>SKILL SALING<br><em>menguatkan.</em></div>
'''
    timeline='''
tl.fromTo('#byline',{opacity:0,x:-15},{opacity:1,x:0,duration:.35,ease:'power2.out'},.15);
tl.fromTo('#rule',{scaleX:0},{scaleX:1,duration:.4,ease:'expo.out'},.28);
tl.fromTo('#opening',{opacity:0,y:28},{opacity:1,y:0,duration:.48,ease:'power3.out'},.28);
tl.to('#opening',{opacity:0,duration:.35,ease:'sine.inOut'},3.65);
tl.fromTo('#tree-scene',{opacity:0},{opacity:1,duration:.45,ease:'sine.inOut'},3.75);
tl.to('#stage',{x:690,y:195,width:308,height:372,borderRadius:24,duration:.6,ease:'power3.inOut'},3.75);
tl.set('#stage',{zIndex:8},3.75);
tl.fromTo('#tree-title',{opacity:0,x:-25},{opacity:1,x:0,duration:.4,ease:'power2.out'},4.05);
tl.fromTo('#tree-map',{opacity:0,y:20},{opacity:1,y:0,duration:.55,ease:'sine.out'},4.15);
tl.fromTo('#tree-core',{opacity:0},{opacity:1,duration:.4,ease:'sine.out'},4.25);
['#node-a','#node-b','#node-c'].forEach((id,i)=>{
 tl.fromTo(id,{opacity:0,y:28},{opacity:1,y:0,duration:.34,ease:['expo.out','power3.out','sine.out'][i]},4.55+i*.14);
});
document.querySelectorAll('.tree-branch').forEach(p=>{p.style.strokeDasharray='1';p.style.strokeDashoffset='1'});
tl.set('#broken-links',{opacity:0},0);
tl.to('#broken-links',{opacity:.30,duration:.5,ease:'power2.out'},7.25);
tl.to('#node-a',{x:-35,y:80,duration:.5,ease:'power2.inOut'},7.4);
tl.to('#node-b',{x:55,y:-25,duration:.5,ease:'sine.inOut'},7.4);
tl.to('#node-c',{x:-5,y:145,duration:.5,ease:'power3.inOut'},7.4);
tl.fromTo('#scattered',{opacity:0,y:20},{opacity:1,y:0,duration:.4,ease:'power2.out'},7.55);
tl.to('#broken-links',{opacity:0,duration:.5,ease:'sine.inOut'},10.8);
['#node-a','#node-b','#node-c'].forEach(id=>tl.to(id,{x:0,y:0,duration:.7,ease:'power3.inOut'},11.2));
document.querySelectorAll('.tree-branch').forEach((p,i)=>tl.to(p,{strokeDashoffset:0,duration:1.2,ease:'power2.out'},11.45+i*.22));
tl.to('#scattered',{opacity:0,duration:.4,ease:'sine.inOut'},13.6);
tl.fromTo('#connected',{opacity:0,y:15},{opacity:1,y:0,duration:.55,ease:'expo.out'},14.0);
tl.to('#tree-core',{opacity:.55,duration:.55,yoyo:true,repeat:1,ease:'sine.inOut'},20.30);
tl.to('#tree-scene',{opacity:0,duration:.5,ease:'sine.inOut'},24.0);
tl.fromTo('#business-scene',{opacity:0},{opacity:1,duration:.5,ease:'sine.inOut'},24.0);
tl.fromTo('#business-title',{opacity:0,y:24},{opacity:1,y:0,duration:.45,ease:'power3.out'},24.55);
document.getElementById('business-spine').style.strokeDasharray='1';document.getElementById('business-spine').style.strokeDashoffset='1';
tl.fromTo('#business-lines',{opacity:0},{opacity:1,duration:.4,ease:'sine.out'},25.0);
tl.to('#business-spine',{strokeDashoffset:0,duration:15.5,ease:'none'},25.0);
[['#business-a',31.45],['#business-b',34.6],['#business-c',40.65]].forEach(([id,t],i)=>{
 tl.fromTo(id,{opacity:0,x:35},{opacity:1,x:0,duration:.4,ease:['expo.out','power3.out','back.out(1.12)'][i]},t);
});
tl.to('#business-scene',{opacity:0,duration:.55,ease:'sine.inOut'},43.25);
tl.to('#stage',{x:45,y:205,width:990,height:710,borderRadius:24,duration:.6,ease:'power3.inOut'},43.25);
tl.fromTo('#ending',{opacity:0,y:20},{opacity:1,y:0,duration:.65,ease:'power2.out'},43.7);
'''
    return markup,timeline


def main():
    selection=json.loads((BASE/'selection.json').read_text(encoding='utf-8'))
    existing_gsap=BASE/'video-01'/'composition'/'gsap.min.js'
    gsap=existing_gsap.read_bytes() if existing_gsap.is_file() else urllib.request.urlopen('https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js',timeout=40).read()
    for i,item in enumerate(selection['clips'],1):
        folder=BASE/f'video-{i:02d}'/'composition'
        folder.mkdir(exist_ok=True)
        (folder/'gsap.min.js').write_bytes(gsap)
        ink,paper,accent=('#151812','#F5F0E2','#C8D6A0') if i==1 else ('#191514','#F7EFE5','#F7B474')
        duration=item['end']-item['start'];total=duration+.55
        words=json.loads((BASE/f'video-{i:02d}'/'words.json').read_text(encoding='utf-8'))
        # Correct only compound-word hyphen splitting, retaining observed timing.
        cleaned=[]
        for w in words:
            w=dict(w)
            if w['text'].startswith('-') and cleaned:
                cleaned[-1]['text']+=w['text'];cleaned[-1]['end']=w['end']
            else:
                cleaned.append(w)
        data=groups(cleaned)
        content,timeline=film_one() if i==1 else film_two()
        specific='.business-node{position:absolute;left:335px;z-index:8;opacity:0;font-size:48px;line-height:1.1;letter-spacing:-1px}.business-node span{display:none}.business-node small{display:block;font:32px Literary,serif;color:var(--paper);margin-top:13px}'
        doc=f'''<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=1080,height=1920"><title>{html.escape(item['title'])}</title><script src="gsap.min.js"></script><style>:root{{--ink:{ink};--paper:{paper};--accent:{accent}}}{COMMON_CSS}{specific}</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="1080" data-height="1920" data-fps="24">
 <div id="stage" class="stage"><video id="footage" class="clip" data-start="0" data-duration="{duration:.3f}" data-track-index="0" src="source.mp4" muted playsinline></video>
 <img id="tail-hold" class="clip" data-start="{duration:.3f}" data-duration="0.55" data-track-index="0" src="last-frame.jpg" alt="Penutup setelah ucapan terakhir" /></div>
 <div class="shade" aria-hidden="true"></div><div id="byline" class="byline">TIMOTHY RONALD</div><div id="rule" class="rule"></div>
 {content}<div class="caption-screen" aria-hidden="true"></div><div id="caption-layer" style="position:absolute;inset:0;z-index:20;pointer-events:none"></div>
 <audio id="soundtrack" data-start="0" data-duration="{total:.3f}" data-track-index="6" src="mix.wav" data-volume="1"></audio>
</div><script>const paper='{paper}';const tl=gsap.timeline({{paused:true}});
{timeline}
{captions_js(data,accent)}
tl.to('#caption-layer',{{opacity:0,duration:.05,ease:'none'}},{data[-1]['end']:.5f});
tl.set('#caption-layer',{{opacity:0}},{total:.5f});
window.__timelines=window.__timelines||{{}};window.__timelines.main=tl;tl.seek(0);
</script></body></html>'''
        (folder/'index.html').write_text(doc,encoding='utf-8')
        (folder/'design.md').write_text(f'''# Creative direction: {item['title']}
Palette: ink {ink}, paper {paper}, accent {accent}. Use these exact colors.
Fonts: Editorial = local Montserrat Black (900), Literary = local Georgia (400), Detail = local Consolas (400).
Canvas: 1080 by 1920, 24fps. Speech stays in its original order and speed. Quiet 0.55s visual/music tail after the last word.
Mood: {'contemplative, intimate, organic; roots become the visual metaphor' if i==1 else 'confident, warm, articulate; a connected skill tree becomes the visual metaphor'}.
References: bold speech-synced text, deliberate speaker framing, relevant visual inserts.
Readability: captions stay at lower middle, clear of the face; full-opacity paper text with a shadow and dark scrim.
No inherited campaign template. Layout changes are bespoke editorial decisions for this passage.
''',encoding='utf-8')
        (folder/'BRIEF.md').write_text(f'''---
workflow: general-video
flow: companion
---
# Brief
User delegates full creative editing, using this randomly selected Timothy Ronald passage.
Source: {selection['source_url']} at {item['start']:.2f}–{item['end']:.2f}s.
Title: {item['title']}
Deliver a complete original 9:16 social video with music, original diagrams, accurate captions and deliberate framing.
User has already authorized construction and render; no further storyboard confirmation is required.
Preserve original meaning and complete spoken ending. Do not upload.
''',encoding='utf-8')
        plan_dir=folder/'.hyperframes';plan_dir.mkdir(exist_ok=True)
        beats=([('0–4.7','Intimate opening; large restrained headline'),('4.7–14.3','Speaker settles into a framed portrait; invisible progress gets breathing room'),('14.3–20.6','Original root illustration grows below the soil as the analogy is spoken'),('20.6–35','Return to speaker; 80 and 90 appear only when spoken'),('35–44.37','Resolve to the delayed-result lesson, with a readable full last word')]
            if i==1 else [('0–4.1','Speaker and skill-tree opening'),('4.1–11.2','Loose branches and misplaced nodes illustrate random skills'),('11.2–24.5','Connections align; a single branch becomes coherent'),('24.5–43.8','Business spine fills: accounting, management, systems; labels appear at actual speech times'),('43.8–47.83','Speaker returns for the replication conclusion')])
        (plan_dir/'expanded-prompt.md').write_text('# Production breakdown\n\n'+f'Palette {ink}, {paper}, {accent}. Montserrat Black / Georgia / Consolas.\n\n'+
            ('Rhythm: intimate-hook → breathe → metaphor-build → concrete-example → resolve.\n' if i==1 else 'Rhythm: hook → scatter → connect → examples-build → resolve.\n')+
            '\n'.join(f'## {t}\n{description}. Depth: real footage, structural illustration, speech caption. Entrances vary between expo, power3 and sine. Related concepts dissolve over 0.35–0.65s.\n' for t,description in beats)+
            '\nAvoid: random stock footage, invented facts, fake source quotes, cut-off words, excessive glitches, default campaign layouts. Music is an original quiet score with narration ducking.\n',encoding='utf-8')
        (folder/'caption-groups.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'AUTHORED {i} {total:.2f}s {len(data)} caption groups')


if __name__=='__main__':main()
