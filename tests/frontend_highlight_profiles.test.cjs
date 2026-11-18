// DOM-only checks with mocked APIs. Never opens a browser, file picker, or provider.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const root=path.resolve(__dirname,'..');
function deferred(){let resolve;const promise=new Promise(yes=>resolve=yes);return {promise,resolve};}
function setup(api={}){
  const {window}=parseHTML('<html><body></body></html>');
  Object.defineProperty(window.HTMLSelectElement.prototype,'value',{configurable:true,get(){return this._value ?? this.querySelector('option')?.value ?? '';},set(value){this._value=String(value);}});
  window.HTMLSelectElement.prototype.add=function(option){this.append(option);};
  const create=window.document.createElement.bind(window.document);window.document.createElement=tag=>{const el=create(tag);if(tag==='video'){el.pause=()=>{};el.load=()=>{};}return el;};
  window.Components={};window.pywebview={api};
  const context=vm.createContext({window,document:window.document,structuredClone,setTimeout,clearTimeout,setInterval:()=>1,clearInterval:()=>{},console,Event:window.Event,CustomEvent:window.CustomEvent,navigator:{clipboard:{readText:async()=>''}},Option:function(text,value){const el=create('option');el.textContent=text;el.value=value;return el;},setActiveView:()=>{},alert:message=>{throw Error(message);}});
  const load=file=>vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),context,{filename:file});
  load('web/time.js');load('web/components/campaign-highlight-profile.js');
  return {window,context,load};
}
const profile={schema_version:1,audience:'Laki-laki yang ingin maju',objective:'Tanggung jawab dan ambisi',topics:['Tanggung jawab'],preferred_angles:['Alasan lalu tindakan'],hook_patterns:['Tantangan personal'],avoid:['Filler'],required_context:['Penjelasan klaim'],weights:{audience_fit:35,message_strength:25,hook_strength:20,completeness:20},min_score:60,reference_analyses:[]};
const ref=(id='one')=>({id,sha256:id.padEnd(64,'a'),name:id+'.mp4',path:'fixture/'+id+'.mp4',role:'reference_highlight',required:true});
function editorFixture(api={}){const view=setup(api),host=view.window.document.createElement('div');view.window.document.body.append(host);let assets=[],name='Campaign A';let editor;editor=view.window.Components.CampaignHighlightProfileEditor(host,()=>api,{getDraft:()=>({name,highlight_profile:editor.getValue(),assets:structuredClone(assets)}),onReferenceAssets:next=>assets=next});editor.setValue(profile,assets);return {...view,host,editor,getAssets:()=>assets,setName:value=>name=value};}

test('Reference videos are optional, multiple, non-required, and rendered as safe text',async()=>{
  let calls=0;const one=ref(),two=ref('two');two.name='<img src=x onerror=alert(1)>.mp4';
  const view=editorFixture({browse_highlight_references:async()=>{calls++;return {status:'ok',files:[one,two]};}});
  assert.equal(calls,0);assert.match(view.host.textContent,/Belum ada referensi/);
  await view.editor.buttons.add.onclick();assert.equal(calls,1);assert.equal(view.getAssets().length,2);assert.ok(view.getAssets().every(asset=>asset.required===false));assert.equal(view.host.querySelector('img'),null);assert.ok(view.host.textContent.includes(two.name));
  view.host.querySelector('[data-reference-id="one"] button').onclick();assert.equal(view.getAssets().length,1);assert.equal(view.getAssets()[0].id,'two');assert.equal(view.editor.getValue().audience,profile.audience);
});

test('Suggestion is explicit, previewed, and only Apply changes the profile',async()=>{
  let calls=0;const suggested={...profile,audience:'Usulan baru',reference_analyses:[]};
  const view=editorFixture({suggest_highlight_profile:async payload=>{calls++;assert.equal(payload.campaign.highlight_profile.audience,profile.audience);return {status:'ok',profile:suggested,references:[],warnings:['Periksa konteks sumber.']};}});
  assert.equal(calls,0);await view.editor.buttons.suggest.onclick();assert.equal(calls,1);assert.equal(view.editor.getValue().audience,profile.audience);assert.equal(view.host.querySelector('.wf-highlight-proposal').hidden,false);
  const apply=[...view.host.querySelectorAll('button')].find(button=>button.textContent==='Terapkan usulan ke form');apply.onclick();assert.equal(view.editor.getValue().audience,'Usulan baru');assert.match(view.host.textContent,/Usulan diterapkan ke form/);
});

test('Manual edits during analysis and after preview cannot be overwritten by Apply',async()=>{
  const pending=deferred();const view=editorFixture({suggest_highlight_profile:()=>pending.promise});
  const running=view.editor.buttons.suggest.onclick();view.editor.fields.audience.value='Koreksi manual';pending.resolve({status:'ok',profile:{...profile,audience:'AI'}});await running;
  assert.equal(view.editor.getValue().audience,'Koreksi manual');assert.equal(view.host.querySelector('.wf-highlight-proposal').hidden,true);assert.match(view.host.textContent,/berubah saat analisis/);
  view.window.pywebview.api.suggest_highlight_profile=async()=>({status:'ok',profile:{...profile,audience:'AI'}});
  await view.editor.buttons.suggest.onclick();view.editor.fields.objective.value='Tujuan manual';
  [...view.host.querySelectorAll('button')].find(button=>button.textContent==='Terapkan usulan ke form').onclick();assert.equal(view.editor.getValue().objective,'Tujuan manual');assert.equal(view.editor.getValue().audience,'Koreksi manual');assert.match(view.host.textContent,/Buat usulan baru/);
});

test('Campaign switches and reference removals discard stale pending results',async()=>{
  const browse=deferred(),suggestion=deferred();const view=editorFixture({browse_highlight_references:()=>browse.promise,suggest_highlight_profile:()=>suggestion.promise});
  view.editor.setValue(profile,[ref()]);const adding=view.editor.buttons.add.onclick();view.host.querySelector('[data-reference-id="one"] button').onclick();browse.resolve({status:'ok',files:[ref('late')]});await adding;assert.equal(view.getAssets().length,0);assert.match(view.host.textContent,/Daftar referensi berubah/);
  const proposing=view.editor.buttons.suggest.onclick();view.editor.invalidate();view.setName('Campaign B');view.editor.setValue({...profile,audience:'Audiens B'},[]);suggestion.resolve({status:'ok',profile:{...profile,audience:'Audiens A'}});await proposing;assert.equal(view.editor.getValue().audience,'Audiens B');assert.equal(view.host.querySelector('.wf-highlight-proposal').hidden,true);assert.equal(view.editor.buttons.suggest.disabled,false);
});

test('Reference removal drops its analysis and validation preserves actionable weight errors',()=>{
  const view=editorFixture();const asset=ref();view.editor.setValue({...profile,reference_analyses:[{asset_id:asset.id,sha256:asset.sha256,summary:'Gagasan jelas'}]},[asset]);assert.equal(view.editor.getValue().reference_analyses.length,1);
  view.host.querySelector('[data-reference-id="one"] button').onclick();assert.equal(view.editor.getValue().reference_analyses.length,0);
  view.host.querySelector('[data-highlight-weight="audience_fit"]').value='Infinity';assert.throws(()=>view.editor.getValue(),/Bobot highlight/);
});

test('Campaign integration saves profile and isolates reference assets from music, endcard, and timeline roles',async()=>{
  const preset={id:'standard',name:'Standar',subtitle_template_id:'clean',features:{highlight_finder:true,add_captions:true,portrait:true}},record={id:'a',name:'A',audience_scope:'Motivasi',language:'id',status:'active',account_ids:[],brief:{durasi_min:15,durasi_max:70},assets:[],editing:{preset_id:'standard'},highlight_profile:profile};let saved;
  const api={get_campaigns:async()=>[record],get_campaign_stats:async()=>({}),get_campaign_workspace:async()=>({status:'ok',campaign:record}),get_campaign_editing_presets:async()=>({status:'ok',presets:[preset]}),get_repliz_accounts:async()=>({status:'ok',accounts:[]}),get_account_profiles:async()=>({status:'ok',profiles:[]}),browse_highlight_references:async()=>({status:'ok',files:[ref()]}),save_campaign_workspace:async(id,payload)=>{saved=structuredClone(payload);return {status:'ok',campaign:{...payload,id},readiness:{production_ready:true,publication_ready:false,production_blockers:[],publication_blockers:[]}};}};
  const view=setup(api);view.load('web/components/campaign-edit.js');view.load('web/components/campaign-additional.js');
  vm.runInContext("const campaignEditView=window.Components.CampaignEditView();const campaignListView={fields:{grid:document.createElement('div'),createBtn:document.createElement('button')}};const stockClipView={refresh:()=>{}};const homeView={fields:{}};document.body.append(campaignEditView.element);window.editView=campaignEditView;",view.context);
  view.load('web/campaigns.js');view.load('web/campaign-workspace.js');await vm.runInContext("openCampaignEdit('a')",view.context);
  const fields=view.window.editView.fields,host=fields.highlightProfileHost;await [...host.querySelectorAll('button')].find(button=>button.textContent==='Tambah video referensi').onclick();
  assert.equal(fields.assetList.querySelectorAll('.wf-asset').length,0);assert.equal(fields.musicAssetSelect.querySelectorAll('option').length,1);assert.equal(fields.endcardAssetSelect.querySelectorAll('option').length,1);
  host.querySelector('[data-highlight-field="topics"]').value='Tanggung jawab\nAmbisi';await fields.saveBtn.onclick();assert.deepEqual(saved.highlight_profile.topics,['Tanggung jawab','Ambisi']);assert.equal(saved.assets[0].role,'reference_highlight');assert.equal(saved.assets[0].required,false);assert.equal(saved.editing.segments,undefined);
});

test('Review explains source-backed selection and feedback binds revision without approving or publishing',async()=>{
  let payload,reviewCalls=0;const api={get_stock_clips:async()=>[{id:'clip',title:'Judul',review_status:'pending',duration:'25s'}],get_review_clip:async()=>({status:'ok',preview_url:'fixture.mp4',clip:{id:'clip',title:'Judul',caption:'',revision_id:'rev-one',review_status:'pending',campaign_version_id:'camp-v1',selection:{version:1,profile_hash:'a'.repeat(64),weighted_score:88,scores:{audience_fit:90,message_strength:88,hook_strength:85,completeness:89},reason:'<img src=x> satu gagasan utuh',matched_patterns:['Tantangan personal'],evidence:[{part:'payoff',start_time:'00:00:20,000',end_time:'00:00:24,700',quote:'<script>bad()</script>'}]}}}),record_highlight_feedback:async(id,data)=>{payload={id,...data};return {status:'ok',feedback:data};},review_clip:async()=>{reviewCalls++;}};
  const view=setup(api);view.load('web/components/workflow-review.js');const review=view.window.Components.StockClipView();view.window.document.body.append(review.element);await review.refresh();await [...review.element.querySelectorAll('button')].find(button=>button.textContent==='Review').onclick();
  const selection=review.element.querySelector('.wf-highlight-selection');assert.ok(selection.textContent.includes('88/100'));assert.match(selection.textContent,/00:00:20,000/);assert.ok(selection.textContent.includes('<script>bad()</script>'));assert.equal(selection.querySelector('script'),null);assert.equal(selection.querySelector('img'),null);
  const feedback=review.element.querySelector('.wf-highlight-feedback');feedback.querySelector('[data-highlight-feedback="needs_context"]').checked=true;feedback.querySelector('textarea').value='Jelaskan maksud pembuka.';await [...feedback.querySelectorAll('button')].find(button=>button.textContent==='Simpan penilaian').onclick();assert.equal(payload.revision_id,'rev-one');assert.deepEqual([...payload.labels],['needs_context']);assert.equal(payload.note,'Jelaskan maksud pembuka.');assert.equal(reviewCalls,0);assert.match(feedback.textContent,/Penilaian tersimpan/);
});

test('Feedback failure retains edits and late clip response cannot replace another review',async()=>{
  const late=deferred();let next=false;const api={get_stock_clips:async()=>[{id:'a',title:'A',review_status:'pending'},{id:'b',title:'B',review_status:'pending'}],get_review_clip:id=>id==='a'&&!next?late.promise:Promise.resolve({status:'ok',preview_url:'fixture.mp4',clip:{id,title:id,revision_id:'rev-'+id,review_status:'pending'}}),record_highlight_feedback:async()=>({status:'error',message:'Revisi sudah berubah. Buka ulang clip.'})};
  const view=setup(api);view.load('web/components/workflow-review.js');const review=view.window.Components.StockClipView();view.window.document.body.append(review.element);await review.refresh();const buttons=[...review.element.querySelectorAll('button')].filter(button=>button.textContent==='Review');const first=buttons[0].onclick();await buttons[1].onclick();late.resolve({status:'ok',preview_url:'old.mp4',clip:{id:'a',title:'a',review_status:'pending'}});await first;assert.equal(review.element.querySelector('.wf-review-detail input').value,'b');
  const feedback=review.element.querySelector('.wf-highlight-feedback');feedback.querySelector('textarea').value='Manual note';await feedback.querySelector('button').onclick();assert.equal(feedback.querySelector('textarea').value,'Manual note');assert.match(feedback.textContent,/Revisi sudah berubah/);assert.equal(feedback.querySelector('button').disabled,false);
});

test('Reference templates stay opt-in, support 4:3 Additional, and save B-roll as supporting footage',async()=>{
  const preset=(id,extra={})=>({id,name:id,subtitle_template_id:id==='standard'?'clean':id,features:{highlight_finder:true,add_captions:true,portrait:id==='standard'},...extra});
  const presets=[preset('standard',{canvas:{width:1080,height:1920}}),preset('podcast_square',{canvas:{width:720,height:720}}),preset('timothy_focus',{default_enabled:false,canvas:{width:1440,height:1080}}),preset('timothy_cinematic',{default_enabled:false,canvas:{width:1920,height:1080}})];
  const record={id:'a',name:'A',audience_scope:'Motivasi',language:'id',account_ids:[],brief:{durasi_min:15,durasi_max:70},assets:[{id:'broll',name:'Pendukung.mp4',path:'fixture/broll.mp4',role:'broll',required:false}],editing:{preset_id:'standard'},highlight_profile:profile};let saved;
  const api={get_campaigns:async()=>[record],get_campaign_stats:async()=>({}),get_campaign_workspace:async()=>({status:'ok',campaign:record}),get_campaign_editing_presets:async()=>({status:'ok',presets}),get_repliz_accounts:async()=>({status:'ok',accounts:[]}),get_account_profiles:async()=>({status:'ok',profiles:[]}),save_campaign_workspace:async(id,payload)=>{saved=structuredClone(payload);return {status:'ok',campaign:{...payload,id},readiness:{production_ready:true,publication_ready:false,production_blockers:[],publication_blockers:[]}};}};
  const view=setup(api);view.load('web/components/campaign-edit.js');view.load('web/components/campaign-additional.js');
  vm.runInContext("const campaignEditView=window.Components.CampaignEditView();const campaignListView={fields:{grid:document.createElement('div'),createBtn:document.createElement('button')}};const stockClipView={refresh:()=>{}};const homeView={fields:{}};document.body.append(campaignEditView.element);window.editView=campaignEditView;",view.context);
  view.load('web/campaigns.js');view.load('web/campaign-workspace.js');await vm.runInContext("openCampaignEdit('a')",view.context);
  const f=view.window.editView.fields;
  for(const id of ['timothy_focus','timothy_cinematic'])assert.equal(f.editingPresetList.querySelector(`[data-preset-id="${id}"] input[type="checkbox"]`).checked,false);
  const broll=f.assetList.querySelector('.wf-asset');assert.equal(broll.querySelector('select').value,'broll');assert.equal(broll.querySelector('input').disabled,true);assert.equal(f.endcardAssetSelect.querySelectorAll('option').length,1);
  const focus=f.editingPresetList.querySelector('[data-preset-id="timothy_focus"] input[type="checkbox"]');focus.checked=true;focus.onchange();
  [...f.additionalHost.querySelectorAll('button')].find(b=>b.textContent==='Tambah').onclick();[...f.additionalHost.querySelectorAll('button')].find(b=>b.textContent==='Watermark').onclick();
  assert.ok([...f.additionalHost.querySelectorAll('.wf-additional-ratios input')].some(input=>input.value==='4:3'));
  // Keep this newly added rule inactive until its images are supplied.
  f.additionalHost.querySelector('.wf-additional-card input').checked=false;f.additionalHost.querySelector('.wf-additional-card input').onchange();
  await f.saveBtn.onclick();assert.equal(saved.assets[0].role,'broll');assert.equal(saved.assets[0].required,false);assert.equal(saved.editing.template_pool.find(item=>item.preset_id==='timothy_focus').enabled,true);assert.equal(saved.editing.template_pool.find(item=>item.preset_id==='timothy_cinematic').enabled,false);
  record.editing={};await vm.runInContext("openCampaignEdit('a')",view.context);
  assert.equal(f.editingPresetList.querySelector('[data-preset-id="standard"] input[type="checkbox"]').checked,true);
  for(const id of ['timothy_focus','timothy_cinematic'])assert.equal(f.editingPresetList.querySelector(`[data-preset-id="${id}"] input[type="checkbox"]`).checked,false);
});
