/* Reusable campaign files, editing policy and audience profiles. */
(() => {
  const f = campaignEditView.fields;
  let workspace = {assets: [], extraction: {}};
  let baseline = {}, generation = 0, accountsReady=false, profileChecks=[];
  let presets=[], selectedPresetId='standard', templatePool=[];
  let extractionRequest=0, linkTimer=null, lastImportedUrl='';
  let mixingToggleDirty=false;
  const mixingKeys=['volume','ducking','fade_seconds'];
  function savedMixingOverrides(music={}) {return Array.isArray(music.mixing_overrides)?music.mixing_overrides:mixingKeys.filter(key=>Object.hasOwn(music,key));}
  function showMixingControls() {f.musicVolumeInput.disabled=!f.musicMixOverrideCheck.checked;f.musicDuckCheck.disabled=!f.musicMixOverrideCheck.checked;}
  f.musicMixOverrideCheck.onchange=()=>{mixingToggleDirty=true;showMixingControls();};
  function mixingOverrides() {
    if(!f.musicMixOverrideCheck.checked)return [];
    if(mixingToggleDirty)return [...mixingKeys];
    const music=workspace.editing?.music || {}, keys=new Set(savedMixingOverrides(music));
    if(Number(f.musicVolumeInput.value)!==Math.max(1,Math.round((music.volume ?? .15)*100)))keys.add('volume');
    if(f.musicDuckCheck.checked!==(music.ducking!==false))keys.add('ducking');
    return [...keys];
  }
  function flat(value,prefix='',out={}) {for(const [key,v] of Object.entries(value || {})){const path=prefix?prefix+'.'+key:key;if(v&&typeof v==='object'&&!Array.isArray(v))flat(v,path,out);else out[path]=v;}return out;}
  function assign(target,path,value) {const parts=path.split('.');let parent=target;for(const part of parts.slice(0,-1))parent=parent[part] ||= {};parent[parts.at(-1)]=structuredClone(value);}
  function merge(left,right) {const result=structuredClone(left);for(const [path,value] of Object.entries(flat(right)))assign(result,path,value);return result;}
  function changed(current,original) {const out={},before=flat(original);for(const [path,value] of Object.entries(flat(current)))if(JSON.stringify(value)!==JSON.stringify(before[path]))assign(out,path,value);return out;}
  const api = () => window.pywebview.api;
  function showMusicControls(){
    const automatic=f.musicPolicySelect.value==='auto';
    for(const field of ['musicCatalogSelect','musicReferenceSelect','musicStyleInput'])f[field].disabled=!automatic;
    f.musicAssetSelect.disabled=automatic;
    f.musicStartInput.disabled=automatic;
  }
  f.musicPolicySelect.onchange=showMusicControls;
  const additional = window.Components.CampaignAdditionalEditor(f.additionalHost, api);
  const highlight = window.Components.CampaignHighlightProfileEditor(f.highlightProfileHost, api, {
    getDraft: () => data(),
    onReferenceAssets: references => {workspace.assets=[...workspace.assets.filter(asset=>asset.role!=='reference_highlight'),...references];showAssets();},
  });
  const normalizedScope = value => String(value || '').trim().toLocaleLowerCase().replace(/\s+/g,' ');
  for(const field of [f.audienceInput,f.languageInput])field.addEventListener('input',()=>profileChecks.forEach(check=>check()));
  const previewButton=document.createElement('button');previewButton.className='btn btn-outline';previewButton.textContent='Lihat contoh template';previewButton.disabled=true;
  const previewVideo=document.createElement('video');previewVideo.controls=true;previewVideo.hidden=true;previewVideo.style.cssText='width:100%;max-height:340px;border-radius:8px';
  f.templatePreviewHost.append(previewButton,previewVideo);
  previewButton.onclick=async()=>{const version=generation,preset=presets.find(p=>p.id===selectedPresetId);if(!preset)return;previewButton.disabled=true;try{const result=await api().get_template_preview(preset.external_template?preset.id:preset.subtitle_template_id);if(version!==generation||preset.id!==selectedPresetId)return;if(result.status!=='ok')throw Error(result.message);previewVideo.src=result.preview_url;previewVideo.hidden=false;}catch(e){if(version===generation)status(String(e),true);}finally{if(version===generation)previewButton.disabled=false;}};
  const status = (text, error=false) => { f.extractionStatus.textContent = text; f.extractionStatus.style.color = error ? 'var(--error)' : 'var(--text-secondary)'; };
  const importTemplateButton=document.createElement('button');importTemplateButton.type='button';importTemplateButton.className='btn btn-outline';importTemplateButton.textContent='Impor paket template';
  const createTemplateButton=document.createElement('button');createTemplateButton.type='button';createTemplateButton.className='btn btn-outline';createTemplateButton.textContent='Buat template di Editor';
  createTemplateButton.onclick=()=>setActiveView('editor');
  f.templatePreviewHost.append(createTemplateButton);
  f.templatePreviewHost.append(importTemplateButton);
  importTemplateButton.onclick=async()=>{
    const version=generation;importTemplateButton.disabled=true;
    try{
      const result=await api().browse_editing_template();if(version!==generation)return;
      if(result.status==='cancelled')return;if(result.status!=='ok')throw Error(result.message);
      const fresh=await api().get_campaign_editing_presets(currentCampaignId);if(version!==generation)return;if(fresh.status!=='ok')throw Error(fresh.message);
      presets=fresh.presets;
      additional.setPresets(presets);
      templatePool=presets.map(p=>templatePool.find(item=>item.preset_id===p.id)||{preset_id:p.id,enabled:false,weight:50});
      selectedPresetId=result.preset.id;showPreset();showPresetFeatures();previewVideo.hidden=true;
      status('Template diimpor. Aktifkan template dan atur bobotnya, lalu simpan campaign.');
    }catch(e){if(version===generation)status(String(e),true);}finally{if(version===generation)importTemplateButton.disabled=false;}
  };
  function node(tag, text, cls) { const el=document.createElement(tag); if(text !== undefined) el.textContent=text; if(cls) el.className=cls; return el; }
  function showPreset() {
    f.editingPresetList.querySelectorAll('.wf-editing-preset').forEach(card=>card.remove());
    for(const preset of presets){
      const entry=templatePool.find(p=>p.preset_id===preset.id);
      const card=node('div',undefined,'wf-editing-preset wf-template-choice');card.dataset.presetId=preset.id;
      const label=node('label'),check=node('input');check.type='checkbox';check.value=preset.id;check.checked=entry.enabled;
      check.setAttribute('aria-label','Gunakan '+preset.name);
      const info=node('span');info.append(node('strong',preset.name),node('small',(preset.description || 'Template editing · setelan tetap')+(preset.archived?' · Diarsipkan, masih dipakai campaign ini':'')));
      label.append(check,info);
      const controls=node('div',undefined,'wf-template-weight');
      const weightLabel=node('label','Bobot peluang'),weight=node('input',undefined,'input');
      weight.type='number';weight.min=1;weight.max=100;weight.step='any';weight.value=entry.weight;weight.disabled=!entry.enabled;
      weight.dataset.weightFor=preset.id;weight.setAttribute('aria-label','Bobot '+preset.name);weightLabel.append(weight);
      const chance=node('span',undefined,'wf-template-chance');chance.setAttribute('role','status');
      const inspect=node('button','Lihat template','btn btn-outline');inspect.type='button';
      inspect.onclick=()=>{selectedPresetId=preset.id;previewVideo.pause();previewVideo.removeAttribute('src');previewVideo.hidden=true;showPresetFeatures();};
      check.onchange=()=>{entry.enabled=check.checked;weight.disabled=!entry.enabled;updateChances();};
      weight.oninput=()=>{entry.weight=Number(weight.value);updateChances();};
      controls.append(weightLabel,chance,inspect);card.append(label,controls);f.editingPresetList.append(card);
    }
    showPresetFeatures();updateChances();
  }
  function updateChances() {
    const enabled=templatePool.filter(p=>p.enabled),total=enabled.reduce((sum,p)=>sum+(Number.isFinite(p.weight)&&p.weight>0?p.weight:0),0);
    for(const card of f.editingPresetList.querySelectorAll('.wf-template-choice')){
      const entry=templatePool.find(p=>p.preset_id===card.dataset.presetId);
      card.querySelector('.wf-template-chance').textContent=entry.enabled&&total>0&&entry.weight>0?`${Math.round(entry.weight/total*1000)/10}% peluang`:'Tidak digunakan';
    }
    f.editingPresetNote.textContent=!enabled.length?'Aktifkan minimal satu template.':enabled.length===1?'Satu template aktif: semua clip memakai template ini.':'Template diacak untuk setiap clip. Bobot menentukan peluang, bukan jumlah hasil yang pasti.';
  }
  function showPresetFeatures() {
    const preset=presets.find(p=>p.id===selectedPresetId);
    f.editingPresetFeatures.replaceChildren();previewButton.disabled=!preset;
    if(!preset){f.editingPresetNote.textContent=presets.length?'Pilih template editing.':'Memuat template…';return;}
    const rows=[['Format video',preset.format_label || (preset.features.portrait?'Vertikal 9:16':'Sesuai sumber')],['Highlight Finder',preset.features.highlight_finder],['Caption Maker',preset.features.add_captions],['Subtitle Style',preset.subtitle_name || preset.subtitle_template_id],['Hook Maker',preset.features.add_hook],['YT Title Maker',preset.features.yt_title_maker]];
    for(const [title,value] of rows){
      const row=node('div',undefined,'wf-preset-feature'),state=node('dd');
      if(typeof value==='boolean'){
        const indicator=node('span',undefined,'wf-preset-indicator'+(value?' is-on':''));indicator.setAttribute('aria-hidden','true');
        state.append(node('span',value?'Aktif':'Nonaktif'),indicator);
      }else state.append(node('span',value,'wf-preset-style'));
      row.append(node('dt',title),state);f.editingPresetFeatures.append(row);
    }
    previewButton.textContent='Lihat contoh '+preset.name;
  }
  function assetChoices(select, roles, selected) {
    select.replaceChildren(new Option('Pilih aset / tanpa aset', ''));
    workspace.assets.filter(a=>roles.includes(a.role)).forEach(a=>select.add(new Option(a.name, a.path)));
    select.value=selected || '';
  }
  function showAssets() {
    const music=f.musicAssetSelect.value, endcard=f.endcardAssetSelect.value;
    f.assetList.replaceChildren();
    workspace.assets.forEach((asset,index)=>{
      if(asset.role==='reference_highlight'){asset.required=false;return;}
      const row=node('div',undefined,'wf-asset');
      const label=node('span',asset.name); label.title=asset.path;
      const role=node('select',undefined,'select'); role.setAttribute('aria-label','Peran '+asset.name);
      [['brief','Brief'],['video','Video campaign'],['music','Musik'],['endcard','Penutup'],['image','Gambar'],['broll','B-roll (template sinematik)']].forEach(([v,t])=>role.add(new Option(t,v)));
      role.value=asset.role; role.onchange=()=>{asset.role=role.value;showAssets();};
      const required=node('label'); const check=node('input'); check.type='checkbox';check.checked=asset.role==='broll'?false:!!asset.required;check.disabled=asset.role==='broll';
      check.onchange=()=>asset.required=check.checked; required.append(check,document.createTextNode(' Wajib'));
      const remove=node('button','Hapus','btn btn-outline');remove.onclick=()=>{workspace.assets.splice(index,1);showAssets();};
      row.append(label,role,required,remove);f.assetList.append(row);
    });
    assetChoices(f.musicAssetSelect,['music'],music);
    assetChoices(f.endcardAssetSelect,['endcard','image','video'],endcard);
    showSourceLinks();
  }
  function showSourceLinks() {
    f.sourceLinkList.replaceChildren();
    const links=workspace.source_links || [];
    if(!links.length)return;
    const details=node('details');details.open=links.some(link=>link.required&&!link.asset_id);
    details.append(node('summary',`${links.length} tautan materi, produk & referensi`));
    const labels={asset:'Materi',guide:'Panduan',product:'Produk',reference:'Contoh relevan',avoid_reference:'Contoh yang dihindari',tutorial:'Tutorial'};
    for(const link of links){
      const row=node('div',undefined,'wf-source-link');row.append(node('strong',(labels[link.kind] || 'Tautan')+(link.required?' · Wajib':'')));
      const anchor=node('a',link.name || link.url);anchor.href=link.url;anchor.target='_blank';anchor.rel='noopener noreferrer';row.append(anchor);
      if(link.required){
        const label=node('label','File lokal yang memenuhi materi wajib ini');
        const select=node('select',undefined,'select');select.setAttribute('aria-label','File untuk '+link.name);
        select.add(new Option('Belum diunduh / belum dipilih',''));
        for(const asset of workspace.assets.filter(a=>['video','endcard','image','music'].includes(a.role)))select.add(new Option(asset.name,asset.id));
        select.value=link.asset_id || '';
        select.onchange=()=>{link.asset_id=select.value;const asset=workspace.assets.find(a=>a.id===link.asset_id);if(asset)asset.required=true;showAssets();};
        label.append(select);row.append(label);
      }
      details.append(row);
    }
    f.sourceLinkList.append(details);
  }
  function fill(data={}) {
    workspace={...data,assets:data.assets || [],extraction:data.extraction || {}};
    f.campaignUrlInput.value=data.source_url || data.external_campaign?.url || '';
    const imageUrl=data.external_campaign?.image_url;
    if(!data.banner_path&&/^https?:\/\//.test(imageUrl || '')){f.bannerPreview.style.backgroundImage=`url(${JSON.stringify(imageUrl)})`;f.bannerText.style.display='none';}
    f.sourcePlatformInput.value=data.source_platform || '';f.audienceInput.value=data.audience_scope || '';f.languageInput.value=data.language || 'id';
    f.platformsInput.value=(data.brief?.platforms || []).join(', ');
    f.setTaggedAccounts(data.brief || {});
    highlight.setValue(data.highlight_profile || {},workspace.assets,{audience:data.audience_scope,objective:data.brief?.tujuan});
    const edit=data.editing || {}, music=edit.music || {}, endcard=edit.endcard || {}, rules=data.rules || {};
    additional.setValue(edit.additional || [], presets);
    templatePool=presets.map(p=>{
      const saved=edit.template_pool?.find(item=>item.preset_id===p.id);
      return {preset_id:p.id,enabled:saved?saved.enabled:edit.template_pool?false:edit.preset_id?p.id===edit.preset_id:p.default_enabled!==false,weight:saved?.weight ?? 50};
    });
    selectedPresetId=templatePool.find(p=>p.enabled)?.preset_id || presets[0]?.id || 'standard';showPreset();f.framingSelect.value=edit.framing || 'speaker';f.sourceRoleSelect.value=edit.source_role || 'external';
    f.musicPolicySelect.value=music.policy==='local'?'local':'auto';f.musicVolumeInput.value=Math.max(1,Math.round((music.volume ?? .15)*100));
    f.musicCatalogSelect.value=music.catalog || 'jamendo';f.musicReferenceSelect.value=music.reference_style || 'reference_clips';f.musicStyleInput.value=music.style_brief || '';
    showMusicControls();
    f.musicStartInput.value=music.start_seconds || 0;f.musicDuckCheck.checked=music.ducking!==false;
    f.musicMixOverrideCheck.checked=savedMixingOverrides(music).length>0;mixingToggleDirty=false;showMixingControls();
    f.endcardRequiredCheck.checked=!!endcard.required;f.endcardDurationInput.value=endcard.duration_seconds || 3;
    const ruang=edit.reference_style || {};
    f.ruangHookTitle.value=ruang.hook_title || '';f.ruangHookDescription.value=ruang.hook_description || '';
    f.ruangHookStrip.value=ruang.hook_strip ?? 'LIKE, COMMENT & FOLLOW';
    f.ruangHookAccent.value=ruang.hook_accent || '#cf003b';f.ruangHookBackground.value=ruang.hook_background || '#ffffff';f.ruangHookTextColor.value=ruang.hook_text_color || '#111111';
    f.externalRatioInput.value=Math.round((rules.max_external_ratio ?? 1)*100);f.externalStrictCheck.checked=!!rules.max_external_ratio_strict;
    f.maxWorkersInput.value=edit.max_workers || 2;f.reviewModeSelect.value=edit.review_mode || 'manual';
    showAssets();f.musicAssetSelect.value=music.path || '';f.endcardAssetSelect.value=endcard.path || '';
    showExtraction();profileChecks.forEach(check=>check());
  }
  function data() {
    return {...workspace,name:f.nameInput.value.trim(),status:f.statusSelect.value,source_platform:f.sourcePlatformInput.value.trim(),
      audience_scope:f.audienceInput.value.trim(),language:f.languageInput.value.trim(),account_ids:accountsReady?getCheckedAccountIds():(workspace.account_ids || []),
      highlight_profile:highlight.getValue(),
      brief:{...(workspace.brief || {}),platforms:f.platformsInput.value.split(',').map(x=>x.trim().toLowerCase()).filter(Boolean),durasi_min:Number(f.durasiMinInput.value),durasi_max:Number(f.durasiMaxInput.value),
        hashtags:getChipValues(f.hashtagsInput),tagged_accounts:[],tagged_accounts_by_platform:f.getTaggedAccounts(),hooks:getHooksListValues(f.hooksList),
        catatan:f.catatanArea.value,angles:getChipValues(f.anglesInput),persona:f.personaArea.value,tujuan:f.tujuanInput.value,cta:f.ctaInput.value},
      do_rules:getRuleListValues(f.doRulesList),dont_rules:getRuleListValues(f.dontRulesList),aturan_umum:getAturanUmumValues(f.aturanUmumList),
      editing:{...(workspace.editing || {}),selection_mode:'weighted_random',template_pool:structuredClone(templatePool),framing:f.framingSelect.value,source_role:f.sourceRoleSelect.value,max_workers:Number(f.maxWorkersInput.value),review_mode:f.reviewModeSelect.value,
        additional:additional.getValue(),
        reference_style:{...(workspace.editing?.reference_style || {}),hook_title:f.ruangHookTitle.value.trim(),hook_description:f.ruangHookDescription.value.trim(),hook_strip:f.ruangHookStrip.value.trim(),hook_accent:f.ruangHookAccent.value,hook_background:f.ruangHookBackground.value,hook_text_color:f.ruangHookTextColor.value},
        music:{...(workspace.editing?.music || {}),policy:f.musicPolicySelect.value,catalog:f.musicCatalogSelect.value,reference_style:f.musicReferenceSelect.value,style_brief:f.musicStyleInput.value.trim(),path:f.musicPolicySelect.value==='local'?f.musicAssetSelect.value:'',required:true,volume:Number(f.musicVolumeInput.value)/100,start_seconds:Number(f.musicStartInput.value),ducking:f.musicDuckCheck.checked,fade_seconds:workspace.editing?.music?.fade_seconds ?? 1,mixing_overrides:mixingOverrides()},
        endcard:{path:f.endcardAssetSelect.value,required:f.endcardRequiredCheck.checked,duration_seconds:Number(f.endcardDurationInput.value)}},
      rules:{...(workspace.rules || {}),max_external_ratio:Number(f.externalRatioInput.value)/100,max_external_ratio_strict:f.externalStrictCheck.checked,
        music_required:true,endcard_required:f.endcardRequiredCheck.checked}};
  }
  function showExtraction() {
    f.extractionDetails.replaceChildren();
    const extraction=workspace.extraction || {};
    for(const warning of workspace.external_campaign?.warnings || [])f.extractionDetails.append(node('p',warning,'wf-error'));
    if(workspace.external_campaign?.unmapped_platforms?.length)f.extractionDetails.append(node('p','Sebagian platform campaign belum dikenali. Periksa platform publikasi secara manual.','wf-error'));
    (extraction.errors || []).forEach(error=>f.extractionDetails.append(node('p',`${error.source_name}: ${error.message}`,'wf-error')));
    if(extraction.missing?.length)f.extractionDetails.append(node('p','Belum ditemukan dalam brief: '+extraction.missing.join(', ')));
    (extraction.conflicts || []).forEach(conflict=>{
      const row=node('div',undefined,'wf-conflict');const info=node('span',`${conflict.field}: ${JSON.stringify(conflict.current)} / ${JSON.stringify(conflict.suggested)} (${conflict.source_name})`);
      row.append(info);
      if(conflict.resolved)row.append(node('strong','Diselesaikan'));
      else for(const [label,suggested] of [['Gunakan nilai form',false],['Gunakan usulan',true]]){
        const button=node('button',label,'btn btn-outline');button.onclick=()=>{const next=data();if(suggested)assign(next,conflict.field,conflict.suggested);conflict.resolved=true;next.extraction=workspace.extraction;applyExtractedBrief({status:'ok',extracted:next});fill(next);};row.append(button);
      }
      f.extractionDetails.append(row);
    });
    if(extraction.provenance) { const details=node('details');details.append(node('summary','Sumber hasil pengisian AI'));
      const pre=node('pre',JSON.stringify(extraction.provenance,null,2));pre.className='wf-provenance';details.append(pre);f.extractionDetails.append(details); }
  }
  async function profiles(ids,version) {
    const [accountsResult, profileResult]=await Promise.all([api().get_repliz_accounts(),api().get_account_profiles()]);
    if(version!==generation)return;
    profileChecks=[];
    f.accountPickerList.replaceChildren();
    if(accountsResult.status!=='ok'||profileResult.status!=='ok') {f.accountPickerList.append(node('p',(accountsResult.message || profileResult.message || 'Akun belum dapat dimuat.')+' Penugasan sebelumnya tetap disimpan.'));f.accountCounter.textContent=`${ids.length} akun tersimpan`;return;}
    if(profileResult.timezone)window.SSRTime.configure(profileResult.timezone);
    f.accountPickerList.append(node('p',`Semua jam memakai ${window.SSRTime.label()} · AM/PM. Zona waktu hanya diubah di Pengaturan.`,'wf-template-intro'));
    f.accountPickerList.append(node('p','Pilih akun sosmed tujuan campaign ini. Akun TikTok dan Instagram dapat memakai campaign berbeda meskipun login Google-nya sama.','wf-template-intro'));
    for(const account of accountsResult.accounts || []) {
      const p=(profileResult.profiles || []).find(x=>x.account_id===account._id) || {};
      const row=node('div',undefined,'wf-account');const label=node('label');const cb=node('input');cb.type='checkbox';cb.value=account._id;cb.checked=ids.includes(account._id);cb.onchange=updateAccountCounter;
      label.append(cb,document.createTextNode(' '+account.name+' · '+account.type));row.append(label);
      const controls=node('div',undefined,'wf-account-schedule');
      const timesField=node('fieldset',undefined,'wf-upload-times');timesField.append(node('legend','Jadwal jam upload'));
      const timesList=node('div',undefined,'wf-upload-time-list');const clocks=[];
      const save=node('button','Simpan jadwal akun','btn btn-outline');const msg=node('span');msg.setAttribute('role','status');
      function addTime(value='09:00'){
        const item=node('div',undefined,'wf-upload-time');const clock=window.SSRTime.clockInput(value,'Upload '+account.name);
        const remove=node('button','Hapus jam','btn btn-outline');remove.type='button';
        remove.onclick=()=>{clocks.splice(clocks.indexOf(clock),1);item.remove();msg.textContent='Jadwal belum disimpan.';};
        for(const input of clock.inputs)input.onchange=()=>{msg.textContent='Jadwal belum disimpan.';};
        clocks.push(clock);item.append(clock.element,remove);timesList.append(item);
      }
      (p.upload_times?.length?p.upload_times:['09:00','14:30']).forEach(addTime);
      const add=node('button','Tambah jam','btn btn-outline');add.type='button';add.onclick=()=>{addTime('18:00');msg.textContent='Jadwal belum disimpan.';};
      timesField.append(timesList,add);
      const limitLabel=node('label','Maks upload per hari','wf-field');const limit=node('input',undefined,'input');limit.type='number';limit.min=1;limit.max=100;limit.value=p.daily_limit || 2;
      limit.setAttribute('aria-label','Maks upload per hari '+account.name);limitLabel.append(limit);limit.oninput=()=>{msg.textContent='Jadwal belum disimpan.';};
      controls.append(timesField,limitLabel);
      const match=node('p');match.setAttribute('role','status');
      let savedProfile=p;
      const checkMatch=()=>{
        const expected=normalizedScope(f.audienceInput.value),actual=normalizedScope(savedProfile.audience_scope);
        const languageMismatch=normalizedScope(f.languageInput.value)&&normalizedScope(savedProfile.language)&&normalizedScope(f.languageInput.value)!==normalizedScope(savedProfile.language);
        const ready=!!expected&&expected===actual&&!languageMismatch&&account.isConnected!==false;
        match.className=ready?'':'wf-error';
        match.textContent=account.isConnected===false?'Koneksi akun terputus. Hubungkan kembali di Repliz.':!expected?'Isi lingkup audiens campaign terlebih dahulu.':!actual?'Simpan jadwal akun untuk menggunakan audiens dan bahasa campaign.':actual!==expected?`Audiens akun tersimpan: ${savedProfile.audience_scope}. Campaign: ${f.audienceInput.value.trim()}.`:languageMismatch?'Bahasa akun tersimpan berbeda dari campaign.':'Profil audiens dan bahasa akun sesuai campaign.';
      };
      profileChecks.push(checkMatch);checkMatch();
      save.onclick=async()=>{save.disabled=true;const inputs=[...controls.querySelectorAll('input,select,button')];inputs.forEach(input=>input.disabled=true);try{
        if(!currentCampaignId)throw Error('Simpan campaign terlebih dahulu, lalu simpan jadwal akun.');
        if(normalizedScope(f.audienceInput.value)!==normalizedScope(workspace.audience_scope)||normalizedScope(f.languageInput.value)!==normalizedScope(workspace.language || 'id'))throw Error('Simpan perubahan audiens atau bahasa campaign terlebih dahulu.');
        if(!clocks.length)throw Error('Tambahkan minimal satu jam upload.');
        if(!Number.isInteger(Number(limit.value))||Number(limit.value)<1||Number(limit.value)>100)throw Error('Maks upload per hari harus berupa angka bulat 1–100.');
        const result=await api().save_account_profile(account._id,{campaign_id:currentCampaignId,upload_times:clocks.map(clock=>clock.get()),daily_limit:Number(limit.value),name:account.name,platform:account.type});
        if(version!==generation)return;
        msg.textContent=result.status==='ok'?'Jadwal akun tersimpan':result.message;
        if(result.status==='ok'){savedProfile=result.profile;checkMatch();}
      }catch(e){if(version===generation)msg.textContent=String(e);}finally{inputs.forEach(input=>input.disabled=false);save.disabled=false;}};
      row.append(match,controls,save,msg);f.accountPickerList.append(row);
    }
    const available=new Set((accountsResult.accounts || []).map(a=>a._id));
    for(const id of ids.filter(id=>!available.has(id))){const label=node('label');const check=node('input');check.type='checkbox';check.value=id;check.checked=true;check.onchange=updateAccountCounter;label.append(check,document.createTextNode(' Akun belum tersedia: '+id));f.accountPickerList.append(label);}
    accountsReady=true;updateAccountCounter();
  }
  const previousOpen=openCampaignEdit;
  openCampaignEdit=async(id=null)=>{
    const version=++generation;accountsReady=false;profileChecks=[];
    ++extractionRequest;clearTimeout(linkTimer);lastImportedUrl='';f.importLinkBtn.disabled=true;
    additional.invalidate();
    highlight.invalidate();
    f.saveBtn.disabled=true;f.extractBtn.disabled=true;
    previewVideo.pause();previewVideo.removeAttribute('src');previewVideo.hidden=true;
    try{
      await previousOpen(id);if(version!==generation)return;
      const [result,presetResult]=await Promise.all([id ? api().get_campaign_workspace(id) : Promise.resolve({status:'ok',campaign:{},readiness:{}}),api().get_campaign_editing_presets(id)]);
      if(version!==generation)return;if(result.status!=='ok')throw Error(result.message || 'Campaign belum dapat dimuat.');
      if(presetResult.status!=='ok'||!presetResult.presets?.length)throw Error(presetResult.message || 'Template editing belum dapat dimuat. Buka campaign kembali.');
      presets=presetResult.presets;
      fill(result.campaign || {});f.readinessStatus.textContent='';status('');
      try{await profiles(result.campaign?.account_ids || [],version);}catch(e){if(version===generation)status('Akun belum dapat dimuat. Penugasan sebelumnya tetap disimpan.',true);}
      if(version!==generation)return;
      baseline=structuredClone(data());f.saveBtn.disabled=false;f.extractBtn.disabled=false;f.importLinkBtn.disabled=false;
      lastImportedUrl=f.campaignUrlInput.value;
    }catch(e){if(version===generation)status(String(e),true);}
  };
  // Replace the old listener to ensure there is one save and one extraction path.
  function replaceButton(field) {const old=f[field], fresh=old.cloneNode(true);old.replaceWith(fresh);f[field]=fresh;return fresh;}
  replaceButton('saveBtn').onclick=async()=>{
    const version=generation;
    f.saveBtn.disabled=true;
    try {
      if(!templatePool.some(p=>p.enabled))throw Error('Aktifkan minimal satu template.');
      if(templatePool.some(p=>!Number.isFinite(p.weight)||p.weight<1||p.weight>100))throw Error('Bobot template harus berupa angka 1–100.');
      const result=await api().save_campaign_workspace(currentCampaignId,data());if(version!==generation)return;if(result.status!=='ok')throw Error(result.message);
      currentCampaignId=result.campaign.id;fill(result.campaign);baseline=structuredClone(data());const r=result.readiness;
      f.readinessStatus.textContent=[r.production_ready?'Siap produksi':r.production_blockers.join(' · '),r.publication_ready?'Siap distribusi':r.publication_blockers.join(' · ')].join('\n');
      status('Campaign tersimpan.');await refreshCampaignList();
    }catch(e){if(version===generation)status(String(e),true);}finally{if(version===generation)f.saveBtn.disabled=false;}
  };
  const fileLabel=f.docFile.parentElement;const newLabel=fileLabel.cloneNode(true);fileLabel.replaceWith(newLabel);
  newLabel.onclick=async(event)=>{event.preventDefault();const version=generation;try{const result=await api().browse_campaign_files();if(version!==generation)return;if(result.status==='ok'){
    result.files.forEach(asset=>{if(!workspace.assets.some(a=>a.id===asset.id&&a.role===asset.role))workspace.assets.push(asset);});highlight.setAssets(workspace.assets);showAssets();status(`${workspace.assets.length} file ditambahkan. Pilih peran setiap file.`);
  }else if(result.status==='error')status(result.message,true);}catch(e){status(String(e),true);}};
  newLabel.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();newLabel.click();}};
  function applyProposal(result,before) {
    const during=changed(data(),before);
    let combined=merge(merge(before,result.extracted),during);
    for(const key of ['music','endcard'])if(typeof result.extracted.rules?.[key+'_required']==='boolean'&&!during.editing?.[key])combined.editing[key].required=result.extracted.rules[key+'_required'];
    if(result.external_campaign){
      combined.external_campaign=result.external_campaign;combined.source_url=result.external_campaign.url;
      const oldLinks=combined.source_links || [];
      combined.source_links=(result.source_links || []).map(link=>({...link,asset_id:oldLinks.find(old=>old.id===link.id)?.asset_id || ''}));
    }
    const previous=combined.extraction || {},provenance={...previous.provenance};
    for(const [field,entries] of Object.entries(result.provenance || {})){
      provenance[field]=[...(provenance[field] || []).filter(old=>!entries.some(entry=>entry.source_id===old.source_id)),...entries];
    }
    const conflicts=[...(previous.conflicts || []),...(result.conflicts || [])];
    combined.extraction={provenance,conflicts:conflicts.filter((c,i)=>conflicts.findIndex(other=>other.field===c.field&&JSON.stringify(other.suggested)===JSON.stringify(c.suggested)&&JSON.stringify(other.current)===JSON.stringify(c.current))===i),errors:result.errors || [],missing:result.missing || []};
    applyExtractedBrief({status:'ok',extracted:combined});fill(combined);
    status(combined.extraction.conflicts.some(c=>!c.resolved)?'Ada aturan berbeda. Pilih nilai yang akan digunakan.':'Data terisi. Periksa hasil sebelum menyimpan.');
  }
  async function importCampaignLink(refresh=false) {
    const url=f.campaignUrlInput.value.trim();if(!url)return;
    const version=generation,request=++extractionRequest,before=data();
    f.extractBtn.disabled=true;status('Mengambil data campaign…');
    try{
      const protectedValues=currentCampaignId?before:changed(before,baseline);
      const result=await api().extract_campaign_link(url,protectedValues,refresh);
      if(version!==generation||request!==extractionRequest)return;
      if(result.status!=='ok')throw Error(result.message);
      applyProposal(result,before);lastImportedUrl=f.campaignUrlInput.value;
      if(result.external_campaign?.partial)status('Sebagian data dibaca dari teks halaman. Periksa brief dan tambahkan tautan materi secara manual.');
    }catch(e){if(version===generation&&request===extractionRequest)status(String(e),true);}
    finally{if(version===generation&&request===extractionRequest)f.extractBtn.disabled=false;}
  }
  function scheduleLinkImport() {
    clearTimeout(linkTimer);++extractionRequest;f.extractBtn.disabled=false;
    const url=f.campaignUrlInput.value.trim();
    if(/^https:\/\/(app\.)?clippo\.id\/campaigns\/[A-Za-z0-9_-]{8,100}\/?(?:[?#].*)?$/.test(url)&&url!==lastImportedUrl)linkTimer=setTimeout(()=>importCampaignLink(),450);
  }
  f.campaignUrlInput.addEventListener('input',scheduleLinkImport);
  f.campaignUrlInput.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();clearTimeout(linkTimer);importCampaignLink();}});
  f.importLinkBtn.onclick=()=>{clearTimeout(linkTimer);return importCampaignLink(true);};
  f.contextArea.addEventListener('input',()=>{
    const value=f.contextArea.value.trim();
    if(/^https:\/\/(app\.)?clippo\.id\/campaigns\/\S+$/.test(value)){f.campaignUrlInput.value=value;scheduleLinkImport();}
  });
  replaceButton('extractBtn').onclick=async()=>{
    f.extractBtn.disabled=true;status('Membaca brief…');
    const version=generation,request=++extractionRequest;clearTimeout(linkTimer);
    try {const before=data(),protectedValues=currentCampaignId?before:changed(before,baseline);
      const text=[workspace.external_campaign?.brief_text,f.contextArea.value].filter(Boolean).join('\n\n');
      const result=await api().extract_campaign_files(workspace.assets,text,protectedValues);if(version!==generation||request!==extractionRequest)return;if(result.status!=='ok')throw Error(result.message);
      applyProposal(result,before);
    }catch(e){if(version===generation&&request===extractionRequest)status(String(e),true);}finally{if(version===generation&&request===extractionRequest)f.extractBtn.disabled=false;}
  };
  fill();
  baseline=structuredClone(data());
})();
