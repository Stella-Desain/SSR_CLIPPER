// Code-only DOM tests: no desktop window, browser, network, or production API.
// Requires linkedom on NODE_PATH (it may be installed into a temporary prefix).
// Run: node --test tests/frontend_workflow.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {parseHTML} = require('linkedom');
const root = path.resolve(__dirname, '..');

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}

function setup(api = {}) {
  const {window} = parseHTML('<html><body></body></html>');
  // linkedom intentionally omits form state and media playback APIs. Model only
  // native form behavior needed here; media is never loaded or played.
  Object.defineProperty(window.HTMLSelectElement.prototype, 'value', {
    configurable: true,
    get() { return this._selectedValue ?? this.querySelector('option')?.value ?? ''; },
    set(value) { this._selectedValue = String(value); },
  });
  window.HTMLSelectElement.prototype.add = function(option) { this.append(option); };
  const oldCreate = window.document.createElement.bind(window.document);
  window.document.createElement = tag => {
    const element = oldCreate(tag);
    if (tag === 'video') {element.pause = () => {};element.load = () => {};}
    return element;
  };
  window.Components = {};
  window.pywebview = {api};
  const context = vm.createContext({
    window, document: window.document, Event: window.Event,
    CustomEvent: window.CustomEvent, structuredClone, console,
    setTimeout, clearTimeout, setInterval: () => 1, clearInterval: () => {},
    navigator: {clipboard: {readText: async () => ''}},
    Option: function(text, value) {
      const option = window.document.createElement('option');
      option.textContent = text; option.value = value; return option;
    },
    alert: message => { throw new Error('Unexpected alert: ' + message); },
    setActiveView: name => {window.lastNavigatedView = name;},
  });
  function load(file) { vm.runInContext(fs.readFileSync(path.join(root, file), 'utf8'), context, {filename:file}); }
  load('web/time.js');
  load('web/components/home.js');
  load('web/components/campaign-edit.js');
  load('web/components/campaign-additional.js');
  load('web/components/campaign-highlight-profile.js');
  vm.runInContext(`
    const homeView = window.Components.HomeView();
    const campaignEditView = window.Components.CampaignEditView();
    const campaignListView = {fields: {grid: document.createElement('div'), createBtn: document.createElement('button')}};
    const stockClipView = {refresh: () => {}};
    document.body.append(homeView.element, campaignEditView.element);
    window.testViews = {homeView, campaignEditView};
  `, context);
  return {window, context, load, ...window.testViews};
}

const preset = {id:'standard', version:1, name:'Standar', subtitle_template_id:'clean', subtitle_name:'Clean', format_label:'Vertikal 9:16',
  features:{highlight_finder:true, add_captions:true, add_hook:false, yt_title_maker:true, portrait:true}};
const squarePreset = {id:'podcast_square', version:1, name:'Podcast Kotak', subtitle_template_id:'podcast_square', subtitle_name:'Kata per kata', format_label:'Kotak 1:1',
  description:'Sudut membulat, subtitle putih kapital yang tampil kata per kata.',
  features:{highlight_finder:true, add_captions:true, add_hook:false, yt_title_maker:true, portrait:false}};
const readiness = {production_ready:true, publication_ready:false, production_blockers:[], publication_blockers:['Pilih akun']};
function campaign(id, name) {
  return {id, name, status:'active', audience_scope:'Motivasi', language:'id', account_ids:[],
    brief:{durasi_min:15,durasi_max:60,max_clips_per_day:2}, editing:{preset_id:'standard',preset_name:'Standar'}, assets:[]};
}
function campaignApi(records) {
  return {
    get_campaigns: async () => structuredClone(records),
    get_campaign_stats: async () => ({}),
    get_campaign_workspace: async id => ({status:'ok',campaign:structuredClone(records.find(c=>c.id===id)),readiness}),
    get_campaign_editing_presets: async () => ({status:'ok',presets:structuredClone([preset,squarePreset])}),
    get_repliz_accounts: async () => ({status:'ok',accounts:[]}),
    get_account_profiles: async () => ({status:'ok',profiles:[]}),
  };
}

test('Create dropdown explains draft campaigns, hides archived ones and refreshes activation', async () => {
  const active = campaign('active', 'Timothy Ronald');
  const draft = {...campaign('draft', 'BEVAN PRAMUDITO'), status:'draft'};
  const archived = {...campaign('archived', 'Archived campaign'), status:'archived'};
  const legacy = campaign('legacy', 'Legacy campaign');
  delete legacy.status;
  const records = [active, draft, archived, legacy];
  const env = setup(campaignApi(records));
  env.load('web/campaigns.js');
  const select = env.homeView.fields.campaign;
  select.value = active.id;
  await vm.runInContext('refreshCampaignList()', env.context);
  assert.equal(select.value, active.id);
  assert.equal(select.querySelector('option[value="archived"]'), null);
  assert.equal(select.querySelector('option[value="legacy"]').disabled, false);
  const draftOption = select.querySelector('option[value="draft"]');
  assert.match(draftOption.textContent, /BEVAN PRAMUDITO.*Draft.*aktifkan di Campaign/);
  assert.equal(draftOption.disabled, true);
  assert.match(vm.runInContext('campaignListView.fields.grid.textContent', env.context), /Draft · belum aktif/);
  select.value = draft.id;
  await vm.runInContext('refreshCampaignList()', env.context);
  assert.equal(select.value, '');
  draft.status = 'active';
  await vm.runInContext('refreshCampaignList()', env.context);
  assert.equal(select.querySelector('option[value="draft"]').disabled, false);
  assert.equal(select.querySelector('option[value="draft"]').textContent, draft.name);
});

test('Create form has four input categories and no editing feature fields', () => {
  const {homeView} = setup();
  const titles = [...homeView.element.querySelectorAll('.create-clip-group > .field-label')].map(el=>el.textContent);
  assert.deepEqual(titles, ['Sumber video','Campaign','Jumlah clip','Cookie']);
  for(const name of ['captions','hook','portrait','subtitle','subtitleStyle','highlightFinder','ytTitleMaker']) {
    assert.equal(homeView.fields[name], undefined, name + ' must be campaign-owned');
  }
});

test('Additional restores uploaded assets, scopes by final ratio and saves layout without brief scenes', async () => {
  const records=[campaign('a','Additional campaign')], api=campaignApi(records);
  const hash='a'.repeat(64), image={path:'durable/logo.png',name:'Logo.png',sha256:hash};
  records[0].editing.additional=[{id:'logo',type:'watermark',enabled:true,ratios:['16:9'],image,layout:{x:.9,y:.1,width:.2,opacity:.8}}];
  api.get_additional_image_preview=async () => ({status:'ok',sha256:hash,width:200,height:100,preview_url:'data:image/png;base64,fixture'});
  let saved;
  api.save_campaign_workspace=async (id,payload)=>{saved=structuredClone(payload);return {status:'ok',campaign:{...payload,id},readiness};};
  const view=setup(api);view.load('web/campaigns.js');view.load('web/campaign-workspace.js');
  await vm.runInContext("openCampaignEdit('a')",view.context);
  const host=view.campaignEditView.fields.additionalHost;
  assert.equal(host.querySelector('h3').textContent,'Additional');
  const row=host.querySelector('[data-additional-id="logo"]');
  assert.equal(row.querySelector('input[value="16:9"]').checked,true);
  assert.equal(row.querySelector('[data-layout]'),null);
  assert.equal(row.querySelector('input[type="number"]'),null);
  assert.equal(row.querySelector('.wf-watermark-guide').getAttribute('src'),'assets/tiktok-safe-area.png');
  const box=row.querySelector('.wf-watermark-box');
  box.onkeydown({key:'ArrowLeft',shiftKey:true,preventDefault(){}});
  box.onkeydown({key:'+',shiftKey:true,preventDefault(){}});
  const ig=row.querySelector('[data-platform="instagram"]');ig.checked=false;ig.onchange();
  const scope=row.querySelector('[aria-label="Penggunaan Additional pada template"]');scope.value='include';scope.onchange();
  const template=row.querySelector('[data-template-id="standard"]');template.checked=true;template.onchange();
  const wide=row.querySelector('input[value="16:9"]');wide.checked=false;wide.onchange();
  const square=row.querySelector('input[value="1:1"]');square.checked=true;square.onchange();
  await view.campaignEditView.fields.saveBtn.onclick();
  assert.deepEqual(saved.editing.additional[0].ratios,['1:1']);
  assert.ok(saved.editing.additional[0].images[0].layout.width>.2);
  assert.equal(saved.editing.additional[0].images[0].layout.opacity,1);
  assert.deepEqual(saved.editing.additional[0].platforms,['tiktok']);
  assert.equal(saved.editing.additional[0].template_scope,'include');
  assert.deepEqual(saved.editing.additional[0].template_ids,['standard']);
  assert.deepEqual(saved.assets,[]);
  const buttons=[...host.querySelectorAll('button')];buttons.find(button=>button.textContent==='Tambah').click();
  host.querySelector('[data-additional-type="face_filter"]').click();
  const face=host.querySelector('.wf-additional-item:last-child');
  assert.match(face.textContent,/satu wajah/);
  assert.equal(face.querySelector('[data-layout]'),null);
  [...face.querySelectorAll('button')].find(button=>button.textContent==='Hapus').click();
  assert.equal(host.querySelectorAll('.wf-additional-item').length,1);
});

test('Additional rejects failed uploads, blocks save while checking and ignores late campaign responses', async () => {
  const records=[campaign('a','A'),campaign('b','B')], api=campaignApi(records), pending=deferred();
  let uploads=0, saves=0;
  api.browse_additional_image=()=>{uploads++;return pending.promise;};
  api.save_campaign_workspace=async(id,payload)=>{saves++;return {status:'ok',campaign:{...payload,id},readiness};};
  const view=setup(api);view.load('web/campaigns.js');view.load('web/campaign-workspace.js');
  await vm.runInContext("openCampaignEdit('a')",view.context);
  const host=view.campaignEditView.fields.additionalHost;
  host.querySelector('[data-additional-type="face_filter"]').click();
  const upload=[...host.querySelectorAll('button')].find(button=>button.textContent==='Unggah gambar');
  const waiting=upload.onclick();
  await upload.onclick();assert.equal(uploads,1);
  await view.campaignEditView.fields.saveBtn.onclick();
  assert.equal(saves,0);assert.match(view.campaignEditView.fields.extractionStatus.textContent,/Tunggu pemeriksaan/);
  await view.campaignEditView.fields.extractBtn.onclick();
  assert.equal(view.campaignEditView.fields.extractBtn.disabled,false);
  assert.match(view.campaignEditView.fields.extractionStatus.textContent,/Tunggu pemeriksaan/);
  await vm.runInContext("openCampaignEdit('b')",view.context);
  pending.resolve({status:'ok',image:{path:'wrong-campaign.png',sha256:'b'.repeat(64),name:'Wrong'},sha256:'b'.repeat(64),width:100,height:100,preview_url:'data:image/png;base64,fixture'});
  await waiting;
  assert.equal(host.querySelectorAll('.wf-additional-item').length,0);
  host.querySelector('[data-additional-type="face_filter"]').click();
  api.browse_additional_image=async()=>({status:'error',message:'Foto target harus menampilkan tepat satu wajah'});
  await [...host.querySelectorAll('button')].find(button=>button.textContent==='Unggah gambar').onclick();
  assert.match(host.textContent,/tepat satu wajah/);
  assert.equal(host.querySelector('.wf-additional-photo').hidden,true);
});

test('Watermark pointer drag and corner resize keep geometry inside the canvas', async () => {
  const records=[campaign('a','A')],api=campaignApi(records),hash='f'.repeat(64);
  records[0].editing.additional=[{id:'logo',type:'watermark',enabled:true,ratios:['9:16'],platforms:['tiktok'],template_scope:'exclude',template_ids:['podcast_square'],image:{path:'logo.png',sha256:hash,name:'Logo'},layout:{x:.7,y:.2,width:.2,opacity:.3}}];
  api.get_additional_image_preview=async()=>({status:'ok',sha256:hash,width:200,height:100,preview_url:'data:image/png;base64,fixture'});
  let saved;api.save_campaign_workspace=async(id,payload)=>{saved=structuredClone(payload);return {status:'ok',campaign:{...payload,id},readiness};};
  const view=setup(api);view.load('web/campaigns.js');view.load('web/campaign-workspace.js');await vm.runInContext("openCampaignEdit('a')",view.context);
  const host=view.campaignEditView.fields.additionalHost,canvas=host.querySelector('.wf-watermark-canvas'),box=host.querySelector('.wf-watermark-box'),handle=host.querySelector('.wf-watermark-resize');
  canvas.getBoundingClientRect=()=>({width:360,height:640,left:0,top:0});
  const event=(x,y)=>({clientX:x,clientY:y,pointerId:1,button:0,preventDefault(){},stopPropagation(){}});
  box.onpointerdown(event(200,200));box.onpointermove(event(100,150));box.onpointerup();
  handle.onpointerdown(event(200,200));box.onpointermove(event(250,250));box.onpointerup();
  await view.campaignEditView.fields.saveBtn.onclick();
  const layout=saved.editing.additional[0].images[0].layout;
  assert.ok(layout.x<.7);assert.ok(layout.y<.2);assert.ok(layout.width>.2);assert.equal(layout.opacity,1);
  assert.equal(saved.editing.additional[0].template_scope,'exclude');
  // Extreme drags stay inside the actual output and switching ratios retains layout.
  const current=view.campaignEditView.fields.additionalHost.querySelector('.wf-watermark-box');
  const currentCanvas=view.campaignEditView.fields.additionalHost.querySelector('.wf-watermark-canvas');currentCanvas.getBoundingClientRect=canvas.getBoundingClientRect;
  current.onpointerdown(event(0,0));current.onpointermove(event(5000,-5000));current.onpointerup();
  await view.campaignEditView.fields.saveBtn.onclick();
  assert.equal(saved.editing.additional[0].images[0].layout.x,1);assert.equal(saved.editing.additional[0].images[0].layout.y,0);
  const ratio=host.querySelector('[aria-label="Rasio preview watermark"]');ratio.value='1:1';ratio.onchange();
  assert.equal(host.querySelector('.wf-watermark-guide').hidden,true);
});

test('Multiple watermark uploads keep separate layouts and trash removes one image at a time', async () => {
  const view=setup(),host=view.window.document.createElement('div');view.window.document.body.append(host);
  const selection=(name,hash)=>({status:'ok',image:{path:'durable/'+name,name,sha256:hash,width:200,height:100},sha256:hash,width:200,height:100,preview_url:'data:image/png;base64,'+name});
  const api={browse_additional_images:async()=>({status:'ok',images:[selection('one.png','1'.repeat(64)),selection('two.png','2'.repeat(64))],errors:[]})};
  const editor=view.window.Components.CampaignAdditionalEditor(host,()=>api);editor.setValue([], [preset]);
  host.querySelector('[data-additional-type="watermark"]').click();
  await [...host.querySelectorAll('button')].find(button=>button.textContent==='Tambah gambar').onclick();
  assert.equal(host.querySelectorAll('.wf-watermark-box').length,2);
  const before=editor.getValue()[0].images,first=host.querySelector('.wf-watermark-box');
  first.onkeydown({key:'ArrowLeft',shiftKey:true,preventDefault(){}});first.onkeydown({key:'+',shiftKey:true,preventDefault(){}});
  const moved=editor.getValue()[0].images;
  assert.ok(moved[0].layout.x<before[0].layout.x);assert.ok(moved[0].layout.width>before[0].layout.width);
  assert.deepEqual(moved[1],before[1]);assert.notEqual(moved[0].id,moved[1].id);
  const trash=first.querySelector('.wf-watermark-delete');assert.match(trash.getAttribute('aria-label'),/one.png/);
  let stopped=false;trash.onpointerdown({stopPropagation(){stopped=true;}});assert.equal(stopped,true);
  trash.click();assert.equal(host.querySelectorAll('.wf-watermark-box').length,1);
  assert.deepEqual(editor.getValue()[0].images,[before[1]]);
  const saved=editor.getValue();editor.setValue(saved,[preset]);
  assert.equal(host.querySelector('.wf-watermark-box').dataset.watermarkImage,before[1].id);
  host.querySelector('.wf-watermark-delete').click();
  assert.equal(host.querySelectorAll('.wf-watermark-box').length,0);
  assert.deepEqual(editor.getValue()[0].images,[]);assert.equal(editor.getValue()[0].image,undefined);
  assert.match(host.textContent,/0\/24 gambar/);
});

test('Multi-image pending upload is isolated from campaign changes and late previews cannot restore deleted images', async () => {
  const view=setup(),host=view.window.document.createElement('div'),upload=deferred(),preview=deferred();view.window.document.body.append(host);
  const api={browse_additional_images:()=>upload.promise,get_additional_image_preview:()=>preview.promise};
  const editor=view.window.Components.CampaignAdditionalEditor(host,()=>api);editor.setValue([], [preset]);
  host.querySelector('[data-additional-type="watermark"]').click();
  const waiting=[...host.querySelectorAll('button')].find(button=>button.textContent==='Tambah gambar').onclick();
  assert.throws(()=>editor.getValue(),/Tunggu pemeriksaan/);
  editor.setValue([], [preset]);upload.resolve({status:'ok',images:[{image:{path:'old.png'},sha256:'3'.repeat(64),preview_url:'data:image/png;base64,old'}]});await waiting;
  assert.deepEqual(editor.getValue(),[]);assert.equal(host.querySelectorAll('.wf-watermark-box').length,0);
  editor.setValue([{id:'old',type:'watermark',enabled:true,ratios:['9:16'],image:{path:'old.png',name:'Old',sha256:'4'.repeat(64)}}],[preset]);
  host.querySelector('.wf-watermark-file-delete').click();
  preview.resolve({status:'error',message:'Late preview must be ignored'});await new Promise(resolve=>setTimeout(resolve,0));
  assert.deepEqual(editor.getValue()[0].images,[]);assert.doesNotMatch(host.textContent,/Late preview/);
});

test('Partial multi-image failures preserve existing images and report rejected selections', async () => {
  const view=setup(),host=view.window.document.createElement('div'),hash='5'.repeat(64);view.window.document.body.append(host);
  const picture={status:'ok',image:{path:'good.png',name:'Good',sha256:hash,width:100,height:100},sha256:hash,width:100,height:100,preview_url:'data:image/png;base64,good'};
  const api={browse_additional_images:async()=>({status:'ok',images:[picture],errors:[{name:'bad.png',message:'Invalid image'}],message:'bad.png: Invalid image'})};
  const editor=view.window.Components.CampaignAdditionalEditor(host,()=>api);editor.setValue([], [preset]);host.querySelector('[data-additional-type="watermark"]').click();
  await [...host.querySelectorAll('button')].find(button=>button.textContent==='Tambah gambar').onclick();
  const kept=editor.getValue()[0].images[0];assert.match(host.querySelector('.wf-additional-status').textContent,/bad.png/);
  api.browse_additional_images=async()=>({status:'error',message:'No valid images'});
  await [...host.querySelectorAll('button')].find(button=>button.textContent==='Tambah gambar').onclick();
  assert.deepEqual(editor.getValue()[0].images,[kept]);assert.match(host.textContent,/No valid images/);
});

test('Campaign tag selector keeps TikTok and Instagram values separate through switching and saving', async () => {
  const records=[campaign('a','A'),campaign('b','B')],api=campaignApi(records);
  records[0].brief.tagged_accounts_by_platform={tiktok:['@tt_saved'],instagram:['@ig_saved']};
  let saved;api.save_campaign_workspace=async(id,payload)=>{saved=structuredClone(payload);return {status:'ok',campaign:{...payload,id},readiness};};
  const view=setup(api);view.load('web/campaigns.js');view.load('web/campaign-workspace.js');await vm.runInContext("openCampaignEdit('a')",view.context);
  const f=view.campaignEditView.fields;
  assert.equal(f.taggedAccountsPlatform.value,'tiktok');assert.equal(f.taggedAccountsInput.value,'@tt_saved');
  f.taggedAccountsInput.value='@tt_new, @second';f.taggedAccountsPlatform.value='instagram';f.taggedAccountsPlatform.onchange();
  assert.equal(f.taggedAccountsInput.value,'@ig_saved');assert.match(f.taggedAccountsInput.getAttribute('aria-label'),/Instagram/);
  f.taggedAccountsInput.value='@ig_new';f.taggedAccountsPlatform.value='tiktok';f.taggedAccountsPlatform.onchange();
  assert.equal(f.taggedAccountsInput.value,'@tt_new, @second');await f.saveBtn.onclick();
  assert.deepEqual(saved.brief.tagged_accounts_by_platform,{tiktok:['@tt_new','@second'],instagram:['@ig_new']});assert.deepEqual(saved.brief.tagged_accounts,[]);
  await vm.runInContext("openCampaignEdit('b')",view.context);assert.equal(f.taggedAccountsInput.value,'');
  f.taggedAccountsPlatform.value='instagram';f.taggedAccountsPlatform.onchange();assert.equal(f.taggedAccountsInput.value,'');
});

test('Legacy account mentions remain editable on both social platforms', async () => {
  const view=setup(),f=view.campaignEditView.fields;
  f.setTaggedAccounts({tagged_accounts:['@old']});assert.equal(f.taggedAccountsInput.value,'@old');
  f.taggedAccountsPlatform.value='instagram';f.taggedAccountsPlatform.onchange();assert.equal(f.taggedAccountsInput.value,'@old');
  f.taggedAccountsInput.value='';assert.deepEqual(f.getTaggedAccounts(),{tiktok:['@old'],instagram:[]});
});

test('Review switches the actual platform video preview and explains unavailable platforms', async () => {
  const api={get_stock_clips:async()=>[{id:'clip',title:'Video',duration:'3s',review_status:'pending'}],get_review_clip:async()=>({status:'ok',clip:{id:'clip',title:'Video',caption:'Video',default_platform:'instagram',platform_eligibility:{tiktok:false,instagram:true},warnings:[],blockers:[]},preview_url:'http://local/master',preview_urls:{instagram:'http://local/ig',default:'http://local/base'}})};
  const view=setup(api);view.load('web/components/workflow-review.js');
  const stock=vm.runInContext('window.Components.StockClipView()',view.context);view.window.document.body.append(stock.element);
  await stock.refresh();await [...stock.element.querySelectorAll('button')].find(button=>button.textContent==='Review').onclick();
  const select=stock.element.querySelector('[aria-label="Versi video untuk sosmed"]'),video=stock.element.querySelector('video');
  assert.equal(video.src,'http://local/ig');select.value='default';select.onchange();assert.equal(video.src,'http://local/base');
  assert.match(stock.element.textContent,/Tidak digunakan pada TikTok/);
});

test('Campaign keeps legacy choice active and saves a pool with non-editable features', async () => {
  const records = [campaign('a','Campaign A')];
  const api = campaignApi(records);
  let saved;
  api.save_campaign_workspace = async (id, payload) => {
    saved = structuredClone(payload);
    return {status:'ok',campaign:{...payload,id},readiness};
  };
  const env = setup(api);
  env.load('web/campaigns.js'); env.load('web/campaign-workspace.js');
  await vm.runInContext("openCampaignEdit('a')", env.context);
  const fields = env.campaignEditView.fields;
  assert.equal(fields.saveBtn.disabled, false);
  assert.equal(fields.editingPresetList.querySelectorAll('input[type="checkbox"]').length, 2);
  assert.equal(fields.editingPresetList.querySelector('input').value, 'standard');
  assert.equal(fields.editingPresetList.querySelector('input[value="standard"]').checked,true);
  assert.equal(fields.editingPresetList.querySelector('input[value="podcast_square"]').checked,false);
  assert.equal(fields.editingPresetFeatures.querySelectorAll('input, select, button').length, 0);
  const featureText = fields.editingPresetFeatures.textContent;
  assert.match(featureText, /Highlight FinderAktif/);
  assert.match(featureText, /Caption MakerAktif/);
  assert.match(featureText, /Subtitle StyleClean/);
  assert.match(featureText, /Hook MakerNonaktif/);
  assert.match(featureText, /YT Title MakerAktif/);
  await fields.saveBtn.onclick();
  assert.equal(saved.editing.preset_id, 'standard');
  assert.equal(saved.editing.selection_mode,'weighted_random');
  assert.deepEqual(saved.editing.template_pool.map(p=>p.enabled),[true,false]);
  assert.equal(saved.name, 'Campaign A');
  assert.equal(saved.editing.music.required,true);
  assert.equal(saved.editing.music.policy,'auto');
  assert.deepEqual([...fields.musicPolicySelect.options].map(o=>o.value),['auto','local']);
  assert.equal(fields.musicRequiredCheck,undefined);
});

test('Music catalogue and per-clip reference direction survive saving and reopening', async () => {
  const records=[campaign('a','Campaign A')],api=campaignApi(records);let saved;
  api.save_campaign_workspace=async(id,payload)=>{saved=structuredClone(payload);records[0]={...saved,id};return {status:'ok',campaign:records[0],readiness};};
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');
  await vm.runInContext("openCampaignEdit('a')",env.context);
  const f=env.campaignEditView.fields;
  assert.equal(f.musicAssetSelect.disabled,true);assert.equal(f.musicStartInput.disabled,true);
  f.musicCatalogSelect.value='repliz';f.musicReferenceSelect.value='now_or_never';f.musicStyleInput.value='Beat tegas untuk pesan tegas, reflektif untuk cerita tenang';
  await f.saveBtn.onclick();
  assert.equal(saved.editing.music.catalog,'repliz');assert.equal(saved.editing.music.reference_style,'now_or_never');assert.match(saved.editing.music.style_brief,/reflektif/);
  await vm.runInContext("openCampaignEdit('a')",env.context);
  assert.equal(f.musicCatalogSelect.value,'repliz');assert.match(f.musicStyleInput.value,/reflektif/);
  f.musicPolicySelect.value='local';f.musicPolicySelect.onchange();
  assert.equal(f.musicCatalogSelect.disabled,true);assert.equal(f.musicAssetSelect.disabled,false);assert.equal(f.musicStartInput.disabled,false);
});

test('Review shows chosen music and failed AI ranking without changing the revision catalogue', async () => {
  let revision;
  const clip={id:'clip',title:'Pesan',caption:'Pesan',revision_id:'revision',review_status:'pending',
    campaign_snapshot:{editing:{music:{catalog:'repliz',reference_style:'now_or_never',style_brief:'Tenang'}}},
    music:{path:'cache.mp3',attribution:{name:'Lagu terpilih',artist:'Artis'},selection:{reason:'Mendukung pesan',fallback:true,
      criteria:{mood:'Reflektif',arc:'steady'},audio_window:{start:12,loop_needed:false},alternatives:[{id:'one',name:'Lagu terpilih',score:82,reason:'Audio terukur'}]}}};
  const env=setup({get_stock_clips:async()=>[clip],get_review_clip:async()=>({status:'ok',clip,preview_url:'http://local/video'}),
    rerender_clip:async(id,editing)=>{revision=editing;return {status:'ok'};}});
  env.load('web/components/workflow-review.js');const stock=env.window.Components.StockClipView();env.window.document.body.append(stock.element);
  await stock.refresh();await [...stock.element.querySelectorAll('button')].find(b=>b.textContent==='Review').onclick();
  const music=stock.element.querySelector('.wf-music-selection');assert.match(music.textContent,/Lagu terpilih/);assert.match(music.textContent,/Ranking AI belum tersedia/);assert.match(music.textContent,/12.0 detik/);
  stock.element.querySelectorAll('input').forEach(input=>{if(input.value==='cache.mp3')input.value='';});
  await [...stock.element.querySelectorAll('button')].find(b=>b.textContent==='Render revisi').onclick();
  assert.equal(revision.music.policy,'auto');assert.equal(revision.music.catalog,'repliz');assert.equal(revision.music.style_brief,'Tenang');
});

test('Weighted pool changes probabilities, previews the inspected template, and persists', async () => {
  const records=[campaign('a','Campaign A')];const api=campaignApi(records);
  let previewed;
  api.get_template_preview=async id=>{previewed=id;return {status:'ok',preview_url:'preview-'+id};};
  api.save_campaign_workspace=async(id,payload)=>{
    records[0]=structuredClone({...payload,id});return {status:'ok',campaign:records[0],readiness};
  };
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');
  await vm.runInContext("openCampaignEdit('a')",env.context);
  const fields=env.campaignEditView.fields;
  const checkbox=fields.editingPresetList.querySelector('input[value="podcast_square"]');checkbox.checked=true;checkbox.onchange();
  const standardWeight=fields.editingPresetList.querySelector('input[data-weight-for="standard"]');standardWeight.value=70;standardWeight.oninput();
  const squareWeight=fields.editingPresetList.querySelector('input[data-weight-for="podcast_square"]');squareWeight.value=30;squareWeight.oninput();
  assert.match(fields.editingPresetList.textContent,/70% peluang/);assert.match(fields.editingPresetList.textContent,/30% peluang/);
  fields.editingPresetList.querySelector('[data-preset-id="podcast_square"] button').onclick();
  assert.match(fields.editingPresetFeatures.textContent,/Format videoKotak 1:1/);
  assert.match(fields.editingPresetFeatures.textContent,/Subtitle StyleKata per kata/);
  assert.match(fields.editingPresetFeatures.textContent,/Hook MakerNonaktif/);
  assert.equal(fields.editingPresetFeatures.querySelectorAll('input, select, button').length,0);
  const preview=fields.templatePreviewHost.querySelector('button');
  assert.equal(preview.textContent,'Lihat contoh Podcast Kotak');await preview.onclick();
  assert.equal(previewed,'podcast_square');
  assert.equal(fields.templatePreviewHost.querySelector('video').hidden,false);
  await fields.saveBtn.onclick();assert.equal(records[0].editing.selection_mode,'weighted_random');
  assert.deepEqual(records[0].editing.template_pool.map(p=>p.weight),[70,30]);
  await vm.runInContext("openCampaignEdit('a')",env.context);
  assert.equal(fields.editingPresetList.querySelector('input[value="podcast_square"]').checked,true);
  assert.equal(fields.editingPresetList.querySelector('input[value="standard"]').checked,true);
  assert.equal(fields.templatePreviewHost.querySelector('video').hidden,true);
});

test('Imported MLT template stays opt-in, previews its composition and preserves pool weights',async()=>{
  const records=[campaign('a','Campaign A')];const api=campaignApi(records);
  const original=await api.get_campaign_editing_presets();
  const imported={...original.presets[0],id:'mlt:demo:v1',name:'Demo Kdenlive',external_template:{engine:'mlt'},format_label:'360 × 640'};
  let didImport=false,previewed,saved;
  api.browse_editing_template=async()=>{didImport=true;return {status:'ok',preset:imported};};
  api.get_campaign_editing_presets=async()=>({status:'ok',presets:didImport?[...original.presets,imported]:original.presets});
  api.get_template_preview=async id=>{previewed=id;return {status:'ok',preview_url:'preview'};};
  api.save_campaign_workspace=async(id,payload)=>{saved=structuredClone(payload);return {status:'ok',campaign:{...payload,id},readiness};};
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');
  await vm.runInContext("openCampaignEdit('a')",env.context);
  const fields=env.campaignEditView.fields;
  const weight=fields.editingPresetList.querySelector('input[data-weight-for="standard"]');weight.value=80;weight.oninput();
  await [...fields.templatePreviewHost.querySelectorAll('button')].find(b=>b.textContent==='Impor paket template').onclick();
  const checkbox=fields.editingPresetList.querySelector('input[value="mlt:demo:v1"]');
  assert.equal(checkbox.checked,false);assert.equal(fields.editingPresetList.querySelector('input[data-weight-for="standard"]').value,'80');
  await fields.templatePreviewHost.querySelector('button').onclick();assert.equal(previewed,'mlt:demo:v1');
  checkbox.checked=true;checkbox.onchange();await fields.saveBtn.onclick();
  assert.deepEqual(saved.editing.template_pool.map(p=>[p.preset_id,p.enabled,p.weight]),[['standard',true,80],['podcast_square',false,50],['mlt:demo:v1',true,50]]);
});

test('Campaign opens the template Editor without saving or mutating the campaign',async()=>{
  const records=[campaign('a','Campaign A')];let saves=0;
  const api=campaignApi(records);api.save_campaign_workspace=async()=>{saves++;};
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');
  await vm.runInContext("openCampaignEdit('a')",env.context);
  const original=structuredClone(records);
  const button=[...env.campaignEditView.fields.templatePreviewHost.querySelectorAll('button')].find(b=>b.textContent==='Buat template di Editor');
  button.onclick();
  assert.equal(env.window.lastNavigatedView,'editor');assert.equal(saves,0);assert.deepEqual(records,original);
});

test('Campaign audio inherits Editor defaults unless the operator explicitly overrides mixing',async()=>{
  const records=[campaign('a','Campaign A')];let saved;
  records[0].editing.music={volume:.15,ducking:true,fade_seconds:.6,mixing_overrides:[]};
  const api=campaignApi(records);api.save_campaign_workspace=async(id,payload)=>{saved=structuredClone(payload);return {status:'ok',campaign:{...payload,id},readiness};};
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');
  await vm.runInContext("openCampaignEdit('a')",env.context);
  const f=env.campaignEditView.fields;assert.equal(f.musicMixOverrideCheck.checked,false);assert.equal(f.musicVolumeInput.disabled,true);
  await f.saveBtn.onclick();assert.deepEqual(saved.editing.music.mixing_overrides,[]);assert.equal(saved.editing.music.fade_seconds,.6);
  f.musicMixOverrideCheck.checked=true;f.musicMixOverrideCheck.onchange();f.musicVolumeInput.value=21;
  await f.saveBtn.onclick();assert.deepEqual(saved.editing.music.mixing_overrides,['volume','ducking','fade_seconds']);assert.equal(saved.editing.music.volume,.21);
});

test('Disabled templates show no chance and empty pool cannot be saved',async()=>{
  const api=campaignApi([campaign('a','Campaign A')]);let saved=0;
  api.save_campaign_workspace=async()=>{saved++;throw Error('must not save');};
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');
  await vm.runInContext("openCampaignEdit('a')",env.context);
  const fields=env.campaignEditView.fields;
  const checkbox=fields.editingPresetList.querySelector('input[value="standard"]');checkbox.checked=false;checkbox.onchange();
  assert.equal(fields.editingPresetList.querySelector('input[data-weight-for="standard"]').disabled,true);
  assert.match(fields.editingPresetNote.textContent,/Aktifkan minimal satu/);
  await fields.saveBtn.onclick();assert.equal(saved,0);assert.equal(fields.saveBtn.disabled,false);
  assert.match(fields.extractionStatus.textContent,/Aktifkan minimal satu/);
});

test('New campaigns enable both templates with equal probabilities',async()=>{
  const env=setup(campaignApi([]));env.load('web/campaigns.js');env.load('web/campaign-workspace.js');
  await vm.runInContext('openCampaignEdit()',env.context);
  const list=env.campaignEditView.fields.editingPresetList;
  assert.equal([...list.querySelectorAll('input[type="checkbox"]')].filter(p=>p.checked).length,2);
  assert.equal((list.textContent.match(/50% peluang/g)||[]).length,2);
});

test('Review shows the recorded template and revisions cannot switch a fixed preset', async () => {
  const selectedCampaign=campaign('a','Campaign A');selectedCampaign.editing={preset_id:'podcast_square',preset_name:'Podcast Kotak'};
  const clip={id:'clip1',title:'Podcast test',review_status:'pending',campaign_snapshot:selectedCampaign,
    template:{id:'podcast_square',name:'Podcast Kotak'},clip_plan:{template:{id:'podcast_square'},framing:'speaker'}};
  let revised;
  const env=setup({get_stock_clips:async()=>[clip],get_review_clip:async()=>({status:'ok',clip,preview_url:'preview'}),
    rerender_clip:async(id,options)=>{revised={id,options:structuredClone(options)};return {status:'ok'};}});
  env.load('web/components/workflow-review.js');
  const view=env.window.Components.StockClipView();await view.refresh();
  await [...view.element.querySelectorAll('button')].find(b=>b.textContent==='Review').onclick();
  assert.match(view.element.textContent,/Template Podcast Kotak/);
  assert.doesNotMatch(view.element.textContent,/Template Standar/);
  assert.equal(view.element.querySelector('select[aria-label="Template revisi"]'),null);
  await [...view.element.querySelectorAll('button')].find(b=>b.textContent==='Render revisi').onclick();
  assert.equal(revised.id,'clip1');assert.equal(revised.options.template_id,undefined);
});

test('Late campaign opening response cannot replace newly selected campaign', async () => {
  const records = [campaign('a','Campaign A'),campaign('b','Campaign B')];
  const api = campaignApi(records);
  const first = deferred(); let calls = 0;
  api.get_campaigns = () => ++calls === 1 ? first.promise : Promise.resolve(structuredClone(records));
  let savedId;
  api.save_campaign_workspace = async (id,payload) => { savedId=id;return {status:'ok',campaign:{...payload,id},readiness}; };
  const env = setup(api);
  env.load('web/campaigns.js'); env.load('web/campaign-workspace.js');
  const older = vm.runInContext("openCampaignEdit('a')",env.context);
  await vm.runInContext("openCampaignEdit('b')",env.context);
  first.resolve(structuredClone(records)); await older;
  assert.equal(env.campaignEditView.fields.nameInput.value,'Campaign B');
  await env.campaignEditView.fields.saveBtn.onclick();
  assert.equal(savedId,'b');
});

test('Campaign selection ignores stale summary responses and file input remains source-only', async () => {
  const older=deferred(), newer=deferred();
  const env=setup({get_campaign_workspace:id=>id==='a'?older.promise:newer.promise,
    browse_source_video:async()=>({status:'ok',path:'C:/clips/source.mp4'})});
  env.load('web/workflow-source.js');
  const fields=env.homeView.fields;
  fields.campaign.value='a';fields.campaign.dispatchEvent(new env.window.Event('change'));
  fields.campaign.value='b';fields.campaign.dispatchEvent(new env.window.Event('change'));
  const latestCampaign=campaign('b','B');latestCampaign.editing={preset_id:'podcast_square',preset_name:'Podcast Kotak'};
  newer.resolve({status:'ok',campaign:latestCampaign,readiness:{production_blockers:['B blocker']}});
  await new Promise(resolve=>setImmediate(resolve));
  older.resolve({status:'ok',campaign:campaign('a','A'),readiness:{production_blockers:['A blocker']}});
  await new Promise(resolve=>setImmediate(resolve));
  const summary=env.window.document.getElementById('create-campaign-summary');
  assert.match(summary.textContent,/Template Podcast Kotak/);assert.doesNotMatch(summary.textContent,/Template Standar/);
  assert.match(summary.textContent,/B blocker/);assert.doesNotMatch(summary.textContent,/A blocker/);
  await env.homeView.element.querySelector('.wf-source-actions button').onclick();
  assert.equal(fields.url.value,'C:/clips/source.mp4');
});

function loadJobController(env) {
  const file=fs.readFileSync(path.join(root,'web/app.js'),'utf8');
  const start=file.indexOf('// ── Create Clip: queued jobs and per-source progress ──');
  const end=file.indexOf('// ── Install All Button ──',start);
  assert.ok(start>=0 && end>start,'app job controller boundary');
  vm.runInContext(file.slice(start,end),env.context,{filename:'web/app.js:job-controller'});
}

test('Enqueue unlocks form while an earlier job runs and each source makes its own job', async () => {
  const records=[];const calls=[];
  const api={
    enqueue_sources:async(sources,campaignId,options)=>{
      calls.push({sources:structuredClone(sources),campaignId,options:structuredClone(options)});
      const ids=sources.map(source=>{
        const id='job'+(records.length+1);
        records.push({id,title:source,source,campaign_id:campaignId,options,
          status:records.length?'queued':'running',clips:[],logs:[],progress:0});return id;
      });
      return {status:'started',jobs:ids};
    },
    get_workflow_jobs:async()=>({status:'ok',jobs:structuredClone(records)}),
  };
  const env=setup(api);loadJobController(env);const fields=env.homeView.fields;
  fields.campaign.value='camp';fields.url.value='source-a.mp4';fields.clips.value='3';
  await vm.runInContext('start()',env.context);
  assert.equal(fields.url.disabled,false);assert.equal(fields.start.disabled,false);
  assert.equal(fields.url.value,'');
  fields.url.value='source-b.mp4\nsource-c.mp4';
  await vm.runInContext('start()',env.context);
  assert.equal(records.length,3);assert.equal(records[0].status,'running');
  assert.deepEqual(calls[1].sources,['source-b.mp4','source-c.mp4']);
  assert.deepEqual(calls[1].options,{num_clips:3,clip_mode:'fixed'});
  assert.equal(fields.jobsList.children.length,3);
  assert.equal(fields.progressPanel.hidden,true,'Details open only when a job is selected');
  fields.jobsList.children[1].click();
  assert.equal(fields.progressPanel.hidden,false);
  assert.equal(fields.selectedTitle.textContent,'source-b.mp4');
  assert.equal(fields.waitingList.children.length,0);
  fields.jobsList.children[1].click();
  assert.equal(fields.progressPanel.hidden,true,'Clicking the selected job collapses details');
});

test('Selected job progress, logs, errors and clip queues never borrow another job state', async () => {
  const records=[
    {id:'old',title:'Earlier video',status:'partial',campaign_id:'campaign-a',progress:.4,
      clips:[{index:1,title:'Old failed clip',status:'error',error:'Old issue'}],logs:[{message:'Old log'}]},
    {id:'new',title:'Running video',status:'running',campaign_id:'campaign-b',progress:.8,
      clips:[{index:1,title:'New clip',status:'running',step:'Rendering',step_progress:.7},
        {index:2,title:'Next clip',status:'waiting'}],logs:[{message:'New log'}]},
  ];
  const env=setup({get_workflow_jobs:async()=>({status:'ok',jobs:structuredClone(records)})});
  loadJobController(env);const fields=env.homeView.fields;
  await vm.runInContext('refreshCreateJobs()',env.context);
  vm.runInContext("selectCreateJob('old')",env.context);
  assert.equal(fields.selectedTitle.textContent,'Earlier video');
  assert.equal(fields.bar.style.width,'40%');
  assert.equal(fields.terminal.textContent,'Old log');
  assert.match(fields.errorLogBox.textContent,/Old issue/);
  assert.equal(fields.inProgressList.children.length,0);
  records[1].progress=.95;records[1].logs.push({message:'New later log'});
  await vm.runInContext('refreshCreateJobs()',env.context);
  assert.equal(fields.terminal.textContent,'Old log');
  assert.equal(fields.bar.style.width,'40%');
  vm.runInContext("selectCreateJob('new')",env.context);
  assert.equal(fields.selectedTitle.textContent,'Running video');
  assert.equal(fields.bar.style.width,'95%');
  assert.equal(fields.errorLogBox.children.length,0);
  assert.equal(fields.inProgressList.children.length,1);
  assert.equal(fields.waitingList.children.length,1);
  assert.match(fields.terminal.textContent,/New later log/);
  assert.doesNotMatch(fields.terminal.textContent,/Old log/);
});

test('Two clicks while enqueue is pending submit only once and preserve form on error', async () => {
  const pending=deferred();let calls=0;
  const env=setup({enqueue_sources:()=>{calls++;return pending.promise;},
    get_workflow_jobs:async()=>({status:'ok',jobs:[]})});
  loadJobController(env);const fields=env.homeView.fields;
  fields.campaign.value='a';fields.url.value='source.mp4';
  const first=vm.runInContext('start()',env.context);
  await vm.runInContext('start()',env.context);
  assert.equal(calls,1);assert.equal(fields.url.disabled,true);
  pending.resolve({status:'error',message:'Missing mandatory campaign asset'});await first;
  assert.equal(fields.url.value,'source.mp4');assert.equal(fields.url.disabled,false);
  assert.match(fields.formError.textContent,/Missing mandatory campaign asset/);
});

const button = (el,text) => [...el.querySelectorAll('button')].find(b=>b.textContent===text);

test('Global time defaults to WITA and explicit AM/PM handles midnight and noon',()=>{
  const {window}=setup();const time=window.SSRTime;
  assert.equal(time.format('2027-01-01T16:00:00Z'),'02/01/2027, 12:00 AM WITA');
  assert.equal(time.format('2027-01-01T04:30:00Z'),'01/01/2027, 12:30 PM WITA');
  const input=time.clockInput('00:05');assert.equal(input.inputs[0].value,'12');assert.equal(input.inputs[2].value,'AM');
  assert.equal(input.get(),'00:05');input.set('12:05');assert.equal(input.get(),'12:05');assert.equal(input.inputs[2].value,'PM');
  time.configure('Asia/Jakarta');assert.equal(time.format('2027-01-01T04:30:00Z'),'01/01/2027, 11:30 AM WIB');
});

test('Timezone is configurable only from Settings and account controls are daily times and limit',async()=>{
  const record=campaign('a','Film');record.account_ids=['account'];const api=campaignApi([record]);let saved;
  api.get_repliz_accounts=async()=>({status:'ok',accounts:[{_id:'account',name:'Akun Film',type:'tiktok',isConnected:true}]});
  api.get_account_profiles=async()=>({status:'ok',timezone:'Asia/Makassar',profiles:[{account_id:'account',audience_scope:'Motivasi',language:'id',daily_limit:2,upload_times:['09:00','14:30']}]});
  api.save_account_profile=async(id,payload)=>{saved=structuredClone({id,payload});return {status:'ok',profile:{...payload,account_id:id,audience_scope:'Motivasi',language:'id'}};};
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');
  await vm.runInContext("openCampaignEdit('a')",env.context);
  const accounts=env.campaignEditView.fields.accountPickerList;
  assert.equal(accounts.querySelectorAll('fieldset').length,1);
  assert.equal(accounts.querySelectorAll('input[type="number"]').length,1);
  assert.equal(accounts.querySelectorAll('input[type="text"]').length,0);
  assert.equal(accounts.querySelectorAll('select[aria-label*="Zona"]').length,0);
  assert.match(accounts.textContent,/WITA.*AM\/PM/);
  assert.equal(env.campaignEditView.element.querySelector('#campaignMaxClipsPerDay'),null);
  const clocks=accounts.querySelectorAll('.wf-clock-input');
  assert.equal(clocks[1].querySelectorAll('select')[0].value,'2');
  assert.equal(clocks[1].querySelectorAll('select')[2].value,'PM');
  accounts.querySelector('input[type="number"]').value='5';
  await button(accounts,'Simpan jadwal akun').onclick();
  assert.deepEqual(saved,{id:'account',payload:{campaign_id:'a',upload_times:['09:00','14:30'],daily_limit:5,name:'Akun Film',platform:'tiktok'}});
  saved=null;accounts.querySelector('input[type="number"]').value='';
  await button(accounts,'Simpan jadwal akun').onclick();assert.equal(saved,null);assert.match(accounts.textContent,/angka bulat 1–100/);
  accounts.querySelector('input[type="number"]').value='5';env.campaignEditView.fields.audienceInput.value='Audiens belum disimpan';
  await button(accounts,'Simpan jadwal akun').onclick();assert.equal(saved,null);assert.match(accounts.textContent,/Simpan perubahan audiens atau bahasa campaign/);
  env.load('web/components/ai-settings.js');
  const settings=env.window.Components.AiSettingsView();
  assert.equal(settings.fields.timezoneSelect.value,'Asia/Makassar');
  assert.equal(settings.element.querySelectorAll('[aria-label="Zona waktu global"]').length,1);
});

async function distributionView(update) {
  const clip={id:'clip',title:'Cerita lengkap',duration:'01:00',review_status:'approved'};
  const row={id:'pub',clip_id:'clip',clip_title:clip.title,account_name:'Akun',platform:'tiktok',scheduled_at:'2027-01-01T01:00:00Z',caption:'Caption'};
  const calls=[];
  const env=setup({get_stock_clips:async()=>[clip],
    preview_distribution:async()=>({status:'ok',preview_id:'preview',timezone:'Asia/Makassar',assignments:[row]}),
    update_distribution_schedule:update,
    confirm_distribution:async id=>{calls.push(id);return {status:'error',message:'Offline test'};}});
  env.load('web/components/workflow-review.js');const view=env.window.Components.StockClipView();await view.refresh();
  const checkbox=view.element.querySelector('input[type="checkbox"]');checkbox.checked=true;checkbox.onchange();
  await button(view.element,'Preview distribusi').onclick();
  return {...env,view,row,calls};
}

test('Inline schedule sends local wall time, locks pending edits, and gates upload until saved',async()=>{
  const pending=deferred();let sent;
  const env=await distributionView((...args)=>{sent=args;return pending.promise;});const el=env.view.element;
  const upload=button(el,'Upload paket ini'),save=button(el,'Simpan jadwal'),date=el.querySelector('input[type="date"]');
  assert.equal(!!upload.disabled,false);date.value='2027-01-02';date.oninput();
  const clock=[...el.querySelectorAll('.wf-clock-input select')];clock[0].value='9';clock[1].value='17';clock[2].value='PM';clock[2].onchange();
  assert.equal(upload.disabled,true);
  const saving=save.onclick();assert.equal(date.disabled,true);assert.ok(clock.every(input=>input.disabled));
  assert.deepEqual(sent,['preview','pub','2027-01-02T21:17']);
  assert.equal(upload.disabled,true);
  pending.resolve({status:'ok',preview_id:'preview',timezone:'Asia/Makassar',assignments:[{...env.row,scheduled_at:'2027-01-02T13:17:00Z'}]});await saving;
  assert.equal(date.disabled,false);assert.equal(upload.disabled,false);assert.match(el.textContent,/Tersimpan.*09:17 PM WITA/);
  await upload.onclick();assert.deepEqual(env.calls,['preview']);
});

test('Rejected inline schedule retains the edit and blocks confirmation until corrected',async()=>{
  const env=await distributionView(async()=>({status:'error',message:'Batas harian terlampaui'}));const el=env.view.element;
  const date=el.querySelector('input[type="date"]');date.value='2027-01-03';date.oninput();
  await button(el,'Simpan jadwal').onclick();
  assert.equal(date.value,'2027-01-03');assert.equal(date.disabled,false);assert.match(el.textContent,/Batas harian terlampaui/);
  const upload=button(el,'Upload paket ini');assert.equal(upload.disabled,true);
  await upload.onclick();assert.deepEqual(env.calls,[]);
  assert.match(el.textContent,/Simpan semua perubahan jadwal/);
});

test('Tracking preserves the actionable timezone error instead of failing on a missing list',async()=>{
  const env=setup({get_stock_clips:async()=>[],get_publication_tracking:async()=>({status:'error',message:'Periksa Pengaturan dan data zona waktu aplikasi.'})});
  env.load('web/components/workflow-review.js');const view=env.window.Components.StockClipView();await view.refresh();
  view.element.querySelector('[data-tab="tracking"]').onclick();await new Promise(resolve=>setImmediate(resolve));
  assert.match(view.element.querySelector('.wf-status').textContent,/Periksa Pengaturan dan data zona waktu aplikasi/);
  assert.doesNotMatch(view.element.textContent,/TypeError/);
  view.element.querySelector('[data-tab="review"]').onclick();await new Promise(resolve=>setImmediate(resolve));
});

const clippoURL='https://app.clippo.id/campaigns/cmtjkbbat06s17t26cxn7lk1k';
function importedCampaign(name='Campaign Clippo') {
  return {status:'ok',extracted:{name,source_platform:'Clippo',brief:{durasi_min:15,durasi_max:180,hashtags:['#clippo']}},
    source_links:[{id:'material',kind:'asset',name:'Footage wajib',url:'https://drive.google.com/drive/folders/example',required:true,asset_id:''}],
    external_campaign:{url:clippoURL,method:'embedded_json',brief_text:'Brief halaman sebagai DATA'},
    conflicts:[],missing:['audience_scope'],errors:[],provenance:{name:[{source_id:'clippo:example',source_url:clippoURL,value:name}]}};
}
test('Pasting a campaign link imports automatically, deduplicates repeats and waits for Save',async()=>{
  const api=campaignApi([]);let calls=0,saves=0;
  api.extract_campaign_link=async(url,existing,refresh)=>{calls++;assert.equal(url,clippoURL);assert.equal(refresh,false);return importedCampaign();};
  api.save_campaign_workspace=async()=>{saves++;};
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');await vm.runInContext('openCampaignEdit()',env.context);
  const f=env.campaignEditView.fields;
  f.contextArea.value=clippoURL;f.contextArea.dispatchEvent(new env.window.Event('input'));
  await new Promise(resolve=>setTimeout(resolve,550));
  assert.equal(calls,1);assert.equal(saves,0);assert.equal(f.nameInput.value,'Campaign Clippo');
  assert.match(f.sourceLinkList.textContent,/Wajib/);assert.equal(f.sourceLinkList.querySelector('a').getAttribute('rel'),'noopener noreferrer');
  f.campaignUrlInput.dispatchEvent(new env.window.Event('input'));await new Promise(resolve=>setTimeout(resolve,550));assert.equal(calls,1);
});
test('Link import preserves edits made while the request is pending and sends explicit refresh',async()=>{
  const api=campaignApi([]),pending=deferred();let request;
  api.extract_campaign_link=(...args)=>{request=args;return pending.promise;};
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');await vm.runInContext('openCampaignEdit()',env.context);
  const f=env.campaignEditView.fields;f.campaignUrlInput.value=clippoURL;
  const running=f.importLinkBtn.onclick();f.nameInput.value='Koreksi saat loading';
  pending.resolve(importedCampaign());await running;
  assert.equal(f.nameInput.value,'Koreksi saat loading');assert.equal(request[2],true);assert.equal(f.extractBtn.disabled,false);
});
test('Switching campaign discards pending link data',async()=>{
  const records=[campaign('a','A'),campaign('b','B')],api=campaignApi(records),pending=deferred();api.extract_campaign_link=()=>pending.promise;
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');await vm.runInContext("openCampaignEdit('a')",env.context);
  const f=env.campaignEditView.fields;f.campaignUrlInput.value=clippoURL;const running=f.importLinkBtn.onclick();
  await vm.runInContext("openCampaignEdit('b')",env.context);pending.resolve(importedCampaign());await running;
  assert.equal(f.nameInput.value,'B');assert.equal(f.campaignUrlInput.value,'');assert.equal(f.sourceLinkList.textContent,'');
});
test('Required linked material binds to a real local asset and survives campaign save',async()=>{
  const record=campaign('a','A');record.assets=[{id:'video',name:'CTA.mp4',path:'fixture/CTA.mp4',role:'endcard',required:false}];
  record.source_links=importedCampaign().source_links;record.external_campaign=importedCampaign().external_campaign;record.source_url=clippoURL;
  const api=campaignApi([record]);let saved;
  api.save_campaign_workspace=async(id,payload)=>{saved=structuredClone(payload);return {status:'ok',campaign:{...payload,id},readiness};};
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');await vm.runInContext("openCampaignEdit('a')",env.context);
  const f=env.campaignEditView.fields,select=f.sourceLinkList.querySelector('select');select.value='video';select.onchange();
  await f.saveBtn.onclick();assert.equal(saved.source_links[0].asset_id,'video');assert.equal(saved.assets[0].required,true);assert.equal(saved.source_url,clippoURL);
});
test('AI refinement receives imported brief text, and script-like labels render as text',async()=>{
  const record=campaign('a','A');record.external_campaign=importedCampaign().external_campaign;
  record.source_links=[{...importedCampaign().source_links[0],name:'<img src=x onerror=alert(1)>'}];
  const api=campaignApi([record]);let body;api.extract_campaign_files=async(files,text)=>{body=text;return {status:'ok',extracted:{audience_scope:'Crypto'},provenance:{},conflicts:[],missing:[]};};
  const env=setup(api);env.load('web/campaigns.js');env.load('web/campaign-workspace.js');await vm.runInContext("openCampaignEdit('a')",env.context);
  const f=env.campaignEditView.fields;assert.equal(f.sourceLinkList.querySelector('img'),null);
  f.contextArea.value='Catatan user';await f.extractBtn.onclick();assert.match(body,/Brief halaman sebagai DATA/);assert.match(body,/Catatan user/);assert.equal(f.audienceInput.value,'Crypto');
});
