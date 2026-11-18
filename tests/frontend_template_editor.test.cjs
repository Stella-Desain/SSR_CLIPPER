// Code-only tests. No browser, desktop window, production files, AI, or network.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const M=require('../web/editor-model.js');
const root=path.resolve(__dirname,'..');
const clone=value=>JSON.parse(JSON.stringify(value));
const settle=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
function design(){return {schema_version:1,id:'design-'+'a'.repeat(32),name:'Template uji',revision:1,canvas:{width:1080,height:1920,fps:30,background:'#101820'},layers:[M.layer('video',{width:1080,height:1920},{id:'video'})],assets:[],preview:{video_path:'',music_path:'',subtitle_path:'',title:'Judul contoh',duration:30},audio:{voice_volume:1,music_volume:.12,ducking:true,fade_in:.5,fade_out:1},published_versions:[]};}
function setup(overrides={}){
  const {window}=parseHTML('<html><body></body></html>');
  Object.defineProperty(window.HTMLSelectElement.prototype,'value',{configurable:true,get(){return this._value??this.querySelector('option')?.value??'';},set(value){this._value=String(value);}});
  const create=window.document.createElement.bind(window.document);
  window.document.createElement=tag=>{const element=create(tag);if(['video','audio'].includes(tag)){element.pause=()=>{};element.load=()=>{};element.play=async()=>{};}if(tag==='input')element.focus=()=>{};return element;};
  let stored=design(),calls=[],saved=[],timers=new Map(),timerId=0;
  const api={editor_list_projects:async()=>({status:'ok',projects:[clone(stored)]}),editor_list_fonts:async()=>({status:'ok',fonts:['Arial','Georgia']}),editor_get_project:async()=>({status:'ok',project:clone(stored)}),editor_create_project:async options=>{stored=design();stored.name=options.name;M.resizeCanvas(stored,options.ratio);return {status:'ok',project:clone(stored)};},editor_save_project:async project=>{saved.push(clone(project));stored=clone(project);stored.revision++;return {status:'ok',project:clone(stored)};},editor_publish_project:async()=>({status:'ok',project:clone(stored),preset:{id:'design:fixture',version:1}}),editor_browse_asset:async()=>({status:'cancelled'}),...overrides};
  const tracked=new Proxy(api,{get(target,key){return typeof target[key]==='function'?(...args)=>{calls.push([key,...clone(args)]);return target[key](...args);}:target[key];}});
  window.pywebview={api:tracked};window.Components={};
  const context=vm.createContext({window,document:window.document,Event:window.Event,CustomEvent:window.CustomEvent,console,structuredClone,Image:class {},setTimeout:(fn,delay)=>{const id=++timerId;timers.set(id,{fn,delay});return id;},clearTimeout:id=>timers.delete(id)});
  for(const file of ['web/editor-model.js','web/components/template-editor.js'])vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),context,{filename:file});
  const view=window.Components.TemplateEditorView();window.document.body.append(view.element);
  const fireTimers=async delay=>{const due=[...timers].filter(([,t])=>t.delay===delay);for(const [id,item] of due){timers.delete(id);item.fn();}await settle();};
  return {window,view,api,calls,saved,timers,fireTimers,getStored:()=>clone(stored)};
}
function byLabel(view,label){return view.element.querySelector('[aria-label="'+label+'"]');}
function byText(view,text){return [...view.element.querySelectorAll('button')].find(el=>el.textContent===text);}
async function open(state){await state.view.refresh();byText(state.view,'Buka').onclick();await settle();}
function edit(state,label,value){const input=byLabel(state.view,label);assert.ok(input,'field '+label);input.value=String(value);input.onchange();return input;}

test('relative timing follows source duration; sample duration never controls output',()=>{
  for(const duration of [15,45,70,120]){
    assert.deepEqual(M.interval({mode:'full',duration:30},duration),{start:0,end:duration});
    assert.deepEqual(M.interval({mode:'end',start:0,duration:2},duration),{start:duration-2,end:duration});
    assert.deepEqual(M.interval({mode:'percent',start:50,duration:25},duration),{start:duration*.5,end:duration*.75});
  }
  assert.deepEqual(M.interval({mode:'end',start:0,duration:4},2),{start:0,end:2});
  assert.deepEqual(M.interval({mode:'start',start:20,duration:3},15),{start:15,end:15});
});
test('canvas resize converts output coordinates independently of editor zoom',()=>{
  const project=design();project.layers.push(M.layer('text',project.canvas,{x:108,y:192,width:864,height:192,font_size:60}));M.resizeCanvas(project,'16:9');
  assert.equal(project.canvas.width,1920);assert.equal(project.layers[1].x,192);assert.equal(project.layers[1].y,108);assert.equal(project.layers[1].font_size,107);
});
test('SRT parser preserves words and absolute cue boundaries',()=>{
  const cues=M.parseSrt('1\n00:00:01,500 --> 00:00:03,000\n<b>Jangan berhenti.</b>\n\n2\n00:00:04,000 --> 00:00:05,000\nBangkit kembali.');
  assert.equal(cues.length,2);assert.deepEqual(cues[0],{start:1.5,end:3,text:'Jangan berhenti.'});assert.equal(M.subtitleAt(cues,3.5),'');
});
test('subtitle preview groups timed words, breaks silence, and respects max lines',()=>{
  const layer={width:400,font_size:50,words_per_group:4,max_lines:2};
  const cues=[{start:0,end:2,text:'satu dua tiga empat'},{start:4,end:5,text:'lima enam'}];
  assert.deepEqual(M.subtitleFrame(cues,.75,layer),{tokens:['satu','dua','tiga','empat'],lines:[[0,1,2],[3]],active:1});
  assert.equal(M.subtitleFrame(cues,3,layer).tokens.length,0);
  assert.deepEqual(M.subtitleFrame(cues,4.75,layer).tokens,['lima','enam']);
});
test('undo and redo preserve latest backend revision and isolate snapshots',()=>{
  const history=new M.History(),project=design();history.push(project);project.name='Updated';project.revision=5;const restored=history.undo(project);assert.equal(restored.name,'Template uji');assert.equal(restored.revision,5);restored.name='Changed restored';assert.equal(history.redo(restored).name,'Updated');
});
test('undo and redo preserve backend asset registry and published versions added after snapshot',()=>{
  const history=new M.History(),project=design();history.push(project);project.layers.push(M.layer('text',project.canvas,{font_asset_id:'font-a'}));project.assets.push({id:'font-a',kind:'font',font_family:'Arial'});project.published_versions.push({version:1});project.revision=4;
  const restored=history.undo(project);assert.equal(restored.layers.length,1);assert.equal(restored.assets[0].id,'font-a');assert.equal(restored.published_versions[0].version,1);
  const redone=history.redo(restored);assert.equal(redone.layers.at(-1).font_asset_id,'font-a');assert.equal(redone.assets[0].id,'font-a');assert.equal(redone.revision,4);
});
test('editor construction is inert and controls wait for API readiness',()=>{
  const state=setup();assert.equal(state.calls.length,0);assert.equal(state.view.buttons.create.disabled,true);assert.equal(state.view.buttons.render.disabled,true);assert.equal(state.view.fields.workspace.hidden,true);
});
test('library reads records as text and does not interpret project names as markup',async()=>{
  const project=design();project.name='<img src=x onerror="danger()">';const state=setup({editor_list_projects:async()=>({status:'ok',projects:[project]})});await state.view.refresh();assert.equal(state.view.fields.cards.querySelector('h3').textContent,project.name);assert.equal(state.view.fields.cards.querySelector('img'),null);assert.equal(state.calls.filter(c=>c[0].includes('render')).length,0);
});
test('create form sends chosen ratio and opens template with no render side effects',async()=>{
  const state=setup();await state.view.refresh();state.view.buttons.create.onclick();const form=state.view.element.querySelector('form');form.querySelector('input').value='Monochrome';form.querySelector('select').value='1:1';form.onsubmit({preventDefault(){}});await settle();assert.equal(state.view.getProject().name,'Monochrome');assert.equal(state.view.getProject().canvas.height,1080);assert.equal(state.view.fields.workspace.hidden,false);assert.equal(state.calls.some(c=>c[0]==='editor_start_render'),false);
});
test('subtitle is unique and video visibility stays required',async()=>{
  const state=setup();await open(state);const subtitle=state.view.element.querySelector('[data-tool="subtitle"]');subtitle.onclick();subtitle.onclick();assert.equal(state.view.getProject().layers.filter(l=>l.type==='subtitle').length,1);const videoRow=state.view.fields.layerList.querySelector('[data-layer-id="video"]');assert.equal(videoRow.querySelector('[aria-label="Sembunyikan Sumber video"]').disabled,true);
});
test('autosave keeps live property callbacks valid after an accepted save',async()=>{
  const state=setup();await open(state);state.view.element.querySelector('[data-tool="text"]').onclick();edit(state,'Ukuran font',70);await state.fireTimers(650);assert.equal(state.saved.at(-1).layers.at(-1).font_size,70);edit(state,'Ukuran font',90);await state.fireTimers(650);assert.equal(state.saved.at(-1).layers.at(-1).font_size,90);assert.equal(state.view.getProject().revision,3);
});
test('changes during an in-flight autosave are preserved and saved with new revision',async()=>{
  let resolve;let callCount=0;const state=setup({editor_save_project:project=>{callCount++;if(callCount===1)return new Promise(done=>{resolve=()=>done({status:'ok',project:{...clone(project),revision:2}});});return Promise.resolve({status:'ok',project:{...clone(project),revision:3}});}});await open(state);state.view.element.querySelector('[data-tool="text"]').onclick();edit(state,'Ukuran font',70);await state.fireTimers(650);edit(state,'Ukuran font',95);resolve();await settle();assert.equal(state.view.getProject().layers.at(-1).font_size,95);await state.fireTimers(650);assert.equal(state.calls.filter(c=>c[0]==='editor_save_project').at(-1)[1].revision,2);assert.equal(state.view.getProject().revision,3);
});
test('save failure keeps draft, exposes retry, and does not spin in automatic retry loop',async()=>{
  const state=setup({editor_save_project:async()=>({status:'error',message:'Disk penuh'})});await open(state);state.view.element.querySelector('[data-tool="text"]').onclick();await state.fireTimers(650);assert.equal(state.view.getProject().layers.length,2);assert.equal(state.view.fields.saveState.textContent,'Gagal menyimpan');assert.match(state.view.fields.message.textContent,/Disk penuh/);assert.equal([...state.timers.values()].filter(t=>t.delay===650).length,0);
});
test('revision conflict blocks mutation and keeps reload action available',async()=>{
  const state=setup({editor_save_project:async()=>({status:'error',message:'Revisi berubah',conflict:true})});await open(state);state.view.element.querySelector('[data-tool="text"]').onclick();state.view.buttons.save.onclick();await settle();assert.ok(byText(state.view,'Muat ulang draft'));assert.equal(state.view.fields.saveState.textContent,'Konflik penyimpanan');state.view.element.querySelector('[data-tool="rect"]').onclick();assert.equal(state.view.getProject().layers.length,2);
});
test('publishing flushes dirty design and notifies campaign catalog without assigning campaigns',async()=>{
  const state=setup();let event=null;state.window.addEventListener('editor-template-published',e=>event=e.detail);await open(state);state.view.element.querySelector('[data-tool="text"]').onclick();state.view.buttons.publish.onclick();await settle();const methods=state.calls.map(c=>c[0]);assert.ok(methods.indexOf('editor_save_project')<methods.indexOf('editor_publish_project'));assert.equal(event.preset.id,'design:fixture');assert.equal(methods.some(name=>name.includes('campaign')),false);
});
test('render polling uses backend percent, pauses offscreen, and completed result remains playable',async()=>{
  let polls=0;const state=setup({editor_start_render:async()=>({status:'ok',render:{id:'render-test',status:'queued',progress:0}}),editor_get_render:async()=>{polls++;return {status:'ok',render:{id:'render-test',status:polls===1?'rendering':'completed',progress:polls===1?1:100,url:'http://127.0.0.1:5555/preview.mp4'}};}});await open(state);state.view.buttons.render.onclick();await settle();assert.equal(state.view.element.querySelector('progress').value,1);assert.equal(state.view.buttons.render.disabled,true);state.view.pause();await state.fireTimers(1000);assert.equal(polls,1);await state.view.refresh();assert.equal(polls,2);const media=state.view.element.querySelector('.te-render-video');assert.equal(media.hidden,false);assert.equal(media.src,'http://127.0.0.1:5555/preview.mp4');
});
test('font family change clears incompatible frozen asset binding',async()=>{
  const project=design();project.assets=[{id:'font-a',kind:'font',font_family:'Arial',font_style:'bold',system_font:true}];project.layers.push(M.layer('text',project.canvas,{id:'title',font_asset_id:'font-a'}));const state=setup({editor_get_project:async()=>({status:'ok',project})});await open(state);state.view.fields.layerList.querySelector('[data-layer-id="title"] .te-layer-name').onclick();edit(state,'Font','Georgia');assert.equal(state.view.getProject().layers.at(-1).font_asset_id,undefined);
});
test('back to library cancels active render before losing its cancellation control',async()=>{
  let cancelled=false;
  const state=setup({editor_start_render:async()=>({status:'ok',render:{id:'active-test',status:'queued'}}),editor_cancel_render:async()=>{cancelled=true;return {status:'ok'};},editor_get_render:async()=>({status:'ok',render:{id:'active-test',status:cancelled?'cancelled':'rendering',progress:12}})});
  await open(state);state.view.buttons.render.onclick();await settle();state.view.buttons.back.onclick();await settle();assert.equal(cancelled,true);assert.equal(state.view.fields.library.hidden,false);assert.equal(state.view.getProject(),null);assert.match(state.view.fields.message.textContent,/dibatalkan saat berpindah project/);
});
test('completed render warns when draft changes and is not silently replaced by old result',async()=>{
  const state=setup({editor_start_render:async()=>({status:'ok',render:{id:'done-test'}}),editor_get_render:async()=>({status:'ok',render:{id:'done-test',status:'completed',progress:100,url:'http://127.0.0.1:5555/done.mp4'}})});
  await open(state);state.view.buttons.render.onclick();await settle();state.view.element.querySelector('[data-tool="text"]').onclick();assert.match(state.view.element.querySelector('.te-render-status').textContent,/Desain berubah/);assert.equal(state.view.element.querySelector('.te-render-video').hidden,false);
});
