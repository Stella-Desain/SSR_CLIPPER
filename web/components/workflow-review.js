window.Components = window.Components || {};
window.Components.StockClipView = function () {
  const el=document.createElement('section');el.className='view';el.dataset.view='stock-clip';
  el.innerHTML=`<header class="wf-header"><div><h1 class="page-title">Review &amp; Upload</h1><p class="page-subtitle">Periksa video final, caption, dan akun tujuan.</p></div><button class="btn btn-outline" data-action="refresh">Perbarui</button></header>
    <nav class="wf-tabs" aria-label="Workflow"><button class="btn btn-lime" data-tab="review">Review clip</button><button class="btn btn-outline" data-tab="jobs">Pekerjaan</button><button class="btn btn-outline" data-tab="tracking">Tracking</button></nav>
    <p class="wf-status" role="status"></p><div class="wf-body"></div>`;
  const body=el.querySelector('.wf-body'), status=el.querySelector('.wf-status');
  let tab='review', campaignFilter=null, selected=new Set(), busy=false, timer=null, activeClip=null,reviewGeneration=0;
  const api=()=>window.pywebview.api;
  const n=(tag,text,cls)=>{const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x;};
  const message=(text,error=false)=>{status.textContent=text;status.classList.toggle('wf-error',error);};
  const action=(text,fn,primary=false)=>{const b=n('button',text,'btn '+(primary?'btn-lime':'btn-outline'));b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){message(String(e),true);}finally{b.disabled=false;}};return b;};
  const field=(label,value,textarea=false)=>{const wrap=n('label',label,'wf-field');const input=n(textarea?'textarea':'input',undefined,'input');input.value=value || '';wrap.append(input);return [wrap,input];};
  const stateLabels={pending:'Perlu review',approved:'Disetujui',rejected:'Ditolak',queued:'Antrean',running:'Berjalan',completed:'Selesai',partial:'Sebagian gagal',failed:'Gagal',interrupted:'Terhenti',cancelled:'Dibatalkan',paused:'Dijeda',uploading:'Uploading',scheduled:'Terjadwal',publishing:'Sedang diterbitkan',published:'Terbit',needs_attention:'Perlu perhatian'};
  function badge(value){return n('span',stateLabels[value] || value,'wf-badge wf-'+value);}
  function clearVideo(){body.querySelectorAll('video').forEach(v=>{v.pause();v.removeAttribute('src');v.load();});}
  async function reviewList(){
    reviewGeneration++;
    const clips=await api().get_stock_clips();const visible=clips.filter(c=>!campaignFilter||c.campaign_id===campaignFilter);
    clearVideo();body.replaceChildren();activeClip=null;
    const bar=n('div',undefined,'wf-toolbar');const search=n('input',undefined,'input');search.placeholder='Cari clip';search.setAttribute('aria-label','Cari clip');
    const filter=n('select',undefined,'select');filter.setAttribute('aria-label','Status review');[['','Semua status'],['pending','Perlu review'],['approved','Disetujui'],['rejected','Ditolak']].forEach(([v,t])=>filter.add(new Option(t,v)));
    bar.append(search,filter,action('Preview distribusi',previewDistribution,true));
    if(campaignFilter)bar.append(action('Semua campaign',async()=>{campaignFilter=null;await refresh();}));body.append(bar);
    const list=n('div',undefined,'wf-list');body.append(list);
    function draw(){list.replaceChildren();const shown=visible.filter(c=>(!filter.value||c.review_status===filter.value)&&String(c.title).toLowerCase().includes(search.value.toLowerCase()));
      if(!shown.length)list.append(n('p','Belum ada clip untuk ditampilkan. Buat clip dari campaign terlebih dahulu.','wf-empty'));
      shown.forEach(c=>{const row=n('div',undefined,'wf-row');const cb=n('input');cb.type='checkbox';cb.setAttribute('aria-label','Pilih '+c.title);cb.checked=selected.has(c.id);cb.disabled=c.review_status!=='approved';cb.onchange=()=>cb.checked?selected.add(c.id):selected.delete(c.id);
        const info=n('div',undefined,'wf-grow');info.append(n('strong',c.title),n('small',`${c.duration} · ${c.template?.name || 'Legacy'} · ${c.campaign_snapshot?.name || c.campaign_id || 'Tanpa campaign'}`));
        row.append(cb,info,badge(c.review_status),action('Review',()=>openClip(c.id)));list.append(row);
      });}
    search.oninput=draw;filter.onchange=draw;draw();
  }
  async function openClip(id){
    const version=++reviewGeneration;
    const result=await api().get_review_clip(id);if(version!==reviewGeneration)return;if(result.status!=='ok')throw Error(result.message);const c=result.clip;activeClip=id;clearVideo();body.replaceChildren();
    body.append(action('← Daftar clip',reviewList));const grid=n('div',undefined,'wf-review-grid');const video=n('video');video.controls=true;video.preload='metadata';video.src=result.preview_url;video.className='wf-video';
    const detail=n('div',undefined,'wf-review-detail');const [titleWrap,title]=field('Judul',c.title);const [captionWrap,caption]=field('Caption',c.caption,true);caption.rows=8;
    detail.append(badge(c.review_status),titleWrap,captionWrap);
    const selection=c.selection || c.highlight_selection || c.highlight?.selection || c.clip_plan?.selection;
    const explanation=n('details',undefined,'wf-highlight-selection');explanation.append(n('summary','Alasan pemilihan highlight'));explanation.open=!!selection;
    if(selection){
      explanation.append(n('p',selection.reason || 'Gagasan dipilih berdasarkan profil audiens dan aturan campaign.'));
      const score=value=>typeof value==='number'&&Number.isFinite(value)?`${Math.round(value*10)/10}/100`:'Belum tersedia';
      const scores=n('dl',undefined,'wf-selection-scores');scores.append(n('dt','Skor akhir'),n('dd',score(selection.weighted_score)));
      for(const [key,label] of [['audience_fit','Kecocokan audiens'],['message_strength','Kekuatan pesan'],['hook_strength','Daya tarik pembuka'],['completeness','Keutuhan gagasan']])scores.append(n('dt',label),n('dd',score(selection.scores?.[key])));
      explanation.append(scores);
      if(selection.matched_patterns?.length)explanation.append(n('p','Pola yang sesuai: '+selection.matched_patterns.join(' · ')));
      const partLabels={opening:'Pembuka',hook:'Pembuka',message:'Pesan utama',claim:'Pesan utama',reason:'Penjelasan',reasoning:'Penjelasan',context:'Konteks',payoff:'Penutup',ending:'Penutup'};
      for(const evidence of selection.evidence || []){const quote=n('blockquote',undefined,'wf-selection-evidence');quote.append(n('strong',`${partLabels[evidence.part] || evidence.part || 'Bukti sumber'} · ${evidence.start_time || '?'} sampai ${evidence.end_time || '?'}`),n('p',evidence.quote || ''));explanation.append(quote);}
      explanation.append(n('p',`Profil versi ${selection.profile?.schema_version || selection.version || 1}${selection.profile_hash?' · '+String(selection.profile_hash).slice(0,12):''}${c.campaign_version_id?' · campaign '+c.campaign_version_id:''}`,'wf-template-intro'));
    }else explanation.append(n('p','Alasan terstruktur belum tersedia untuk clip ini. Job baru memakai profil pencarian highlight campaign.'));
    detail.append(explanation);
    const feedback=n('details',undefined,'wf-highlight-feedback');feedback.append(n('summary','Beri penilaian hasil highlight'),n('p','Penilaian tersimpan untuk membantu usulan profil berikutnya. Profil, persetujuan clip, dan publikasi berubah melalui tindakan Anda.','wf-template-intro'));
    const labels=n('fieldset',undefined,'wf-highlight-feedback-options');labels.append(n('legend','Penilaian Anda'));const checksFeedback=[];
    for(const [key,label] of [['audience_fit','Cocok dengan audiens'],['off_topic','Topik tidak sesuai'],['needs_context','Perlu konteks tambahan'],['incomplete_ending','Gagasan atau ucapan akhirnya belum selesai']]){const wrap=n('label'),check=n('input');check.type='checkbox';check.value=key;check.checked=(c.highlight_feedback?.labels || []).includes(key);check.dataset.highlightFeedback=key;wrap.append(check,document.createTextNode(label));labels.append(wrap);checksFeedback.push(check);}
    const [noteWrap,note]=field('Catatan penilaian',c.highlight_feedback?.note || '',true);note.rows=3;note.maxLength=2000;
    const feedbackStatus=n('p','','wf-highlight-feedback-status');feedbackStatus.setAttribute('role','status');
    const saveFeedback=n('button','Simpan penilaian','btn btn-outline');saveFeedback.type='button';saveFeedback.onclick=async()=>{
      saveFeedback.disabled=true;feedbackStatus.textContent='Menyimpan penilaian…';feedbackStatus.classList.remove('wf-error');
      try{const payload={labels:checksFeedback.filter(check=>check.checked).map(check=>check.value),note:note.value.trim(),revision_id:c.revision_id};const result=await api().record_highlight_feedback(id,payload);if(version!==reviewGeneration||activeClip!==id)return;if(result.status!=='ok')throw Error(result.message || 'Penilaian belum dapat disimpan.');const unchanged=payload.note===note.value.trim()&&JSON.stringify(payload.labels)===JSON.stringify(checksFeedback.filter(check=>check.checked).map(check=>check.value));feedbackStatus.textContent=unchanged?'Penilaian tersimpan.':'Penilaian sebelumnya tersimpan. Perubahan terbaru belum disimpan.';}
      catch(error){if(version===reviewGeneration&&activeClip===id){feedbackStatus.textContent=String(error);feedbackStatus.classList.add('wf-error');}}
      finally{if(version===reviewGeneration)saveFeedback.disabled=false;}
    };
    feedback.append(labels,noteWrap,saveFeedback,feedbackStatus);detail.append(feedback);
    if(result.preview_urls && Object.keys(result.preview_urls).length){
      const label=n('label','Versi video untuk sosmed','wf-field'),select=n('select',undefined,'select');select.setAttribute('aria-label','Versi video untuk sosmed');
      for(const [platform,url] of Object.entries(result.preview_urls)){select.add(new Option(({tiktok:'TikTok',instagram:'IG',default:'Versi dasar'}[platform] || platform),platform));}
      select.value=result.preview_urls[c.default_platform]?c.default_platform:Object.keys(result.preview_urls)[0];
      video.src=result.preview_urls[select.value];select.onchange=()=>{video.pause();video.src=result.preview_urls[select.value];video.load();};
      label.append(select);detail.append(label,n('p','Periksa setiap versi sebelum menyetujui clip. Distribusi memilih file sesuai sosmed akun tujuan.','wf-template-intro'));
    }
    const unavailable=Object.entries(c.platform_eligibility || {}).filter(([,ok])=>!ok).map(([p])=>({tiktok:'TikTok',instagram:'IG'}[p] || p));
    if(unavailable.length)detail.append(n('p','Tidak digunakan pada '+unavailable.join(', ')+' karena aturan Additional.','wf-template-intro'));
    const checks=n('div',undefined,'wf-checks');[...(c.blockers || []),...(c.warnings || [])].forEach(t=>checks.append(n('p',t)));if(!checks.children.length)checks.append(n('p','Pemeriksaan teknis selesai. Periksa cerita, audio, dan teks pada video.'));detail.append(checks);
    const audio=n('details');audio.append(n('summary','Pengukuran audio final'));
    const measured=c.audio_analysis;
    if(measured?.status==='measured'){
      for(const [key,label,unit] of [['integrated_lufs','Loudness terpadu','LUFS'],['true_peak_dbtp','Puncak nyata','dBTP'],['loudness_range_lu','Rentang loudness','LU']]){
        const value=measured[key];audio.append(n('p',`${label}: ${typeof value==='number'&&Number.isFinite(value)?value.toFixed(1)+' '+unit:'Belum dapat diukur'}`));
      }
      audio.append(n('p','Loudness menunjukkan tingkat suara keseluruhan; puncak nyata membantu memeriksa risiko distorsi. Dengarkan keseimbangan dialog dan musik pada preview.'));
    }else audio.append(n('p',measured?.status==='silent'?'Track audio tidak memiliki sinyal yang terukur.':measured?.status==='no_audio'?'Video ini tidak memiliki track audio.':'Pengukuran belum tersedia untuk clip ini. Clip yang dirender berikutnya akan dianalisis otomatis.'));
    detail.append(audio);
    const musicSelection=c.music?.selection;
    if(musicSelection){
      const music=n('details',undefined,'wf-music-selection');music.append(n('summary','Alasan pemilihan musik'));
      const track=c.music.attribution || {};
      music.append(n('strong',[track.name,track.artist].filter(Boolean).join(' · ')),n('p',musicSelection.reason || musicSelection.criteria?.reason || ''));
      if(musicSelection.criteria)music.append(n('p',`${musicSelection.criteria.mood} · ${musicSelection.criteria.arc==='build'?'Energi naik':musicSelection.criteria.arc==='release'?'Energi menurun':'Energi stabil'}`));
      const passage=musicSelection.audio_window;
      if(passage)music.append(n('p',`Mulai pada ${Number(passage.start).toFixed(1)} detik${passage.loop_needed?' · Lagu diulang untuk memenuhi durasi clip':''}`));
      if(musicSelection.fallback)music.append(n('p','Ranking AI belum tersedia. Pemilihan memakai alur energi audio yang terukur.','wf-template-intro'));
      for(const alternative of musicSelection.alternatives || [])music.append(n('p',`${alternative.name || alternative.id} · ${Number(alternative.score).toFixed(1)}/100 · ${alternative.reason || ''}`));
      detail.append(music);
    }
    const musicPanel=n('details',undefined,'wf-music-review');musicPanel.append(n('summary','Musik: preview A/B dan revisi'));
    const musicState=n('p','','wf-music-feedback');musicState.setAttribute('role','status');
    const candidates=n('select',undefined,'select');candidates.setAttribute('aria-label','Pilihan lagu dan passage');
    candidates.add(new Option('Musik saat ini',''));
    const options=musicSelection?.alternatives || [];
    for(const option of options)candidates.add(new Option(`${option.name || option.id} · ${Number(option.start).toFixed(1)} s · ${Number(option.score).toFixed(0)}/100`,option.candidate_id));
    const [startLabel,start]=field('Mulai lagu (detik)',String(c.music?.start_seconds ?? 0));start.type='number';start.min='0';start.step='.1';
    const gainLabel=n('label',undefined,'wf-field'),gainText=n('span'),gain=n('input');gain.type='range';gain.min='1';gain.max='200';gain.step='1';gain.value=String(Math.round((c.music?.volume ?? .5)*100));gain.setAttribute('aria-label','Level musik');
    const showGain=()=>gainText.textContent=`Level musik: ${gain.value}%`;gain.oninput=showGain;showGain();gainLabel.append(gainText,gain);
    const duckLabel=n('label',undefined,'wf-inline'),duck=n('input');duck.type='checkbox';duck.checked=c.music?.ducking!==false;duckLabel.append(duck,document.createTextNode('Ducking ringan'));
    candidates.onchange=()=>{const chosen=options.find(v=>v.candidate_id===candidates.value);start.value=String(chosen?.start ?? c.music?.start_seconds ?? 0);};
    const musicPayload=()=>({revision_id:c.revision_id,candidate_id:candidates.value,start_seconds:Number(start.value),volume:Number(gain.value)/100,ducking:duck.checked});
    const previewControls=n('div',undefined,'wf-toolbar');
    previewControls.append(action('Preview mix',async()=>{
      musicState.textContent='Menyiapkan preview…';const r=await api().preview_clip_music(id,musicPayload());if(version!==reviewGeneration)return;if(r.status!=='ok')throw Error(r.message);
      const at=video.currentTime;video.pause();video.src=r.preview_url;video.load();video.onloadedmetadata=()=>{video.currentTime=Math.min(at,video.duration || at);video.onloadedmetadata=null;};
      musicState.textContent=[r.balance?.music_to_source_db!=null?`Musik / audio asli: ${r.balance.music_to_source_db} dB`:'',...(r.balance?.warnings || [])].filter(Boolean).join(' · ');
    }),action('Video saat ini',async()=>{const at=video.currentTime;video.pause();video.src=result.preview_url;video.load();video.onloadedmetadata=()=>{video.currentTime=Math.min(at,video.duration || at);video.onloadedmetadata=null;};}),
    action('Simpan revisi musik',async()=>{musicState.textContent='Menyimpan revisi…';const r=await api().apply_clip_music(id,musicPayload());if(version!==reviewGeneration)return;if(r.status!=='ok')throw Error(r.message);message('Revisi musik tersimpan sebagai clip baru yang perlu review.');await openClip(r.clip.id);},true));
    if(!c.dry_master){for(const button of [previewControls.children[0],previewControls.children[2]])button.disabled=true;musicState.textContent='Master tanpa musik belum tersedia. Render ulang dari sumber terlebih dahulu.';}
    musicPanel.append(candidates,startLabel,gainLabel,duckLabel,previewControls,musicState);
    const musicFeedback=n('fieldset',undefined,'wf-music-feedback-options');musicFeedback.append(n('legend','Penilaian musik'));const feedbackInputs=[];
    for(const [key,label] of [['good_fit','Cocok'],['wrong_mood','Salah nuansa'],['too_quiet','Terlalu pelan'],['vocal_clash','Vokal bentrok']]){const wrap=n('label'),input=n('input');input.type='checkbox';input.value=key;input.checked=(c.music_feedback?.labels || []).includes(key);input.onchange=()=>{if(input.checked)for(const other of feedbackInputs)if((key==='good_fit'&&other!==input)||(key!=='good_fit'&&other.value==='good_fit'))other.checked=false;};wrap.append(input,document.createTextNode(label));feedbackInputs.push(input);musicFeedback.append(wrap);}
    const [musicNoteWrap,musicNote]=field('Catatan musik',c.music_feedback?.note || '',true);musicNote.rows=2;musicNote.maxLength=2000;
    musicPanel.append(musicFeedback,musicNoteWrap,action('Simpan penilaian musik',async()=>{const r=await api().record_music_feedback(id,{revision_id:c.revision_id,labels:feedbackInputs.filter(v=>v.checked).map(v=>v.value),note:musicNote.value.trim()});if(version!==reviewGeneration)return;if(r.status!=='ok')throw Error(r.message);musicState.textContent='Penilaian musik tersimpan.';}));
    if(c.music_balance?.warnings?.length)musicPanel.append(n('p',c.music_balance.warnings.join(' '),'wf-template-intro'));
    if(musicSelection?.review_required){musicPanel.open=true;musicPanel.append(n('p','Pilihan otomatis belum cukup meyakinkan. Periksa kandidat musik sebelum menyetujui clip.','wf-error'));}
    detail.append(musicPanel);
    const controls=n('div',undefined,'wf-toolbar');
    for(const [label,kind] of [['Simpan revisi','save'],['Tolak','reject'],['Setujui clip','approve']])controls.append(action(label,async()=>{const r=await api().review_clip(id,{title:title.value,caption:caption.value,action:kind});if(r.status!=='ok')throw Error(r.message);selected.delete(id);message(kind==='approve'?'Clip disetujui. Pilih clip untuk melihat distribusinya.':'Review tersimpan.');await openClip(id);},kind==='approve'));
    detail.append(controls);
    const editing=c.campaign_snapshot?.editing || {}, fixedPreset=!!editing.preset_id || editing.selection_mode==='weighted_random';
    const renderedTemplate=c.template || c.clip_plan?.template || {};
    const presetName=c.editing_template?.name || c.highlight?.editing_template?.name || editing.preset_name || (editing.preset_id==='standard'?'Standar':renderedTemplate.name || editing.preset_id);
    const ruang=['ruang_founder','ruang_witness'].includes(renderedTemplate.id);
    const revise=n('details');revise.append(n('summary',ruang?'Ubah hook, framing, atau musik':fixedPreset?'Ubah framing atau musik':'Ubah template, framing, atau musik'));
    const template=fixedPreset?n('p','Template '+presetName+' · '+(renderedTemplate.description || renderedTemplate.name || editing.template_id)):n('select',undefined,'select');
    if(!fixedPreset){template.setAttribute('aria-label','Template revisi');for(const v of ['clean','social','bold'])template.add(new Option(v,v));template.value=c.clip_plan?.template?.id || 'clean';}
    const framing=n('select',undefined,'select');framing.setAttribute('aria-label','Framing revisi');[['speaker','Ikuti pembicara'],['fit','Seluruh frame'],['center','Crop tengah']].forEach(([v,t])=>framing.add(new Option(t,v)));framing.value=c.clip_plan?.framing || 'speaker';
    const [musicLabel,musicPath]=field('File musik lokal (kosong = pilih otomatis)',c.music?.path || '');
    const hookFields={};
    if(ruang){
      const style=editing.reference_style || {};
      for(const [key,label,value] of [
        ['hook_title','Judul kartu hook',style.hook_title || c.template_render?.hook_title || c.highlight?.hook_title || c.title],
        ['hook_description','Deskripsi kartu hook',style.hook_description || c.template_render?.hook_description || c.highlight?.hook_description || c.title],
        ['hook_strip','Teks strip berjalan',style.hook_strip ?? 'LIKE, COMMENT & FOLLOW'],
        ['hook_accent','Warna judul dan strip',style.hook_accent || '#cf003b'],
        ['hook_background','Warna kartu',style.hook_background || '#ffffff'],
        ['hook_text_color','Warna deskripsi',style.hook_text_color || '#111111']]){
        const [labelNode,input]=field(label,value);if(key.includes('color')||['hook_accent','hook_background'].includes(key))input.type='color';
        hookFields[key]=input;revise.append(labelNode);
      }
    }
    revise.append(template,framing,musicLabel,action('Render revisi',async()=>{const r=await api().rerender_clip(id,{...(!fixedPreset?{template_id:template.value}:{}),
      ...(ruang?{reference_style:{...(editing.reference_style || {}),...Object.fromEntries(Object.entries(hookFields).map(([key,input])=>[key,input.value.trim()]))}}:{}),
      framing:framing.value,music:{...(editing.music || {}),policy:musicPath.value?'local':'auto',path:musicPath.value,required:true,volume:c.music?.volume || .15,ducking:true}});if(r.status!=='ok')throw Error(r.message);message('Revisi masuk antrean. Hasil baru akan muncul sebagai clip yang perlu review.');}));detail.append(revise);
    const plan=n('details');plan.append(n('summary','Rencana editing dan sumber'));plan.append(n('pre',JSON.stringify(c.clip_plan || {},null,2),'wf-provenance'));detail.append(plan);
    grid.append(video,detail);body.append(grid);
  }
  async function previewDistribution(){
    reviewGeneration++;
    if(!selected.size)throw Error('Pilih clip yang sudah disetujui.');
    let result=await api().preview_distribution([...selected]);if(result.status!=='ok')throw Error(result.message);
    if(result.timezone)window.SSRTime.configure(result.timezone);
    clearVideo();body.replaceChildren();body.append(n('h2','Preview distribusi'),n('p',`Jadwal memakai ${window.SSRTime.label()} · AM/PM. Edit langsung pada kolom Jadwal, lalu simpan perubahan sebelum upload.`));
    const dirty=new Set();let pending=0,publishing=false;
    const table=n('table',undefined,'wf-table');const head=n('tr');['Clip','Akun','Platform','Jadwal','Caption'].forEach(t=>head.append(n('th',t)));table.append(head);
    const upload=action('Upload paket ini',async()=>{
      if(dirty.size||pending)throw Error('Simpan semua perubahan jadwal sebelum upload.');
      publishing=true;table.querySelectorAll('input,select,button').forEach(input=>input.disabled=true);
      try{const r=await api().confirm_distribution(result.preview_id);if(r.status!=='ok')throw Error(r.message);selected.clear();tab='tracking';message(r.message);await refresh();}
      finally{publishing=false;table.querySelectorAll('input,select,button').forEach(input=>input.disabled=false);}
    },true);
    const updateUpload=()=>{upload.disabled=publishing||pending>0||dirty.size>0;};
    result.assignments.forEach(a=>{
      const row=n('tr');[a.clip_title,a.account_name,a.platform].forEach(t=>row.append(n('td',t)));
      const schedule=n('td'),editor=n('div',undefined,'wf-schedule-editor'),date=n('input',undefined,'input');date.type='date';date.setAttribute('aria-label','Tanggal upload '+a.clip_title);
      const p=window.SSRTime.parts(a.scheduled_at);date.value=`${p.year}-${p.month}-${p.day}`;
      const clock=window.SSRTime.clockInput(p.hour+':'+p.minute,'Jadwal '+a.clip_title),feedback=n('small',window.SSRTime.format(a.scheduled_at));feedback.setAttribute('role','status');
      const changed=()=>{dirty.add(a.id);feedback.textContent='Perubahan belum disimpan';feedback.classList.remove('wf-error');updateUpload();};
      date.oninput=changed;for(const input of clock.inputs)input.onchange=changed;
      const save=action('Simpan jadwal',async()=>{
        pending++;updateUpload();feedback.textContent='Menyimpan jadwal…';
        const inputs=[date,...clock.inputs];inputs.forEach(input=>input.disabled=true);
        try{
          if(!date.value)throw Error('Pilih tanggal upload.');
          const updated=await api().update_distribution_schedule(result.preview_id,a.id,date.value+'T'+clock.get());
          if(updated.status!=='ok')throw Error(updated.message);
          const saved=updated.assignments.find(item=>item.id===a.id);if(!saved)throw Error('Jadwal tersimpan belum dapat dibaca. Buat preview kembali.');
          result=updated;const parts=window.SSRTime.parts(saved.scheduled_at);date.value=`${parts.year}-${parts.month}-${parts.day}`;clock.set(parts.hour+':'+parts.minute);
          feedback.textContent='Tersimpan · '+window.SSRTime.format(saved.scheduled_at);feedback.classList.remove('wf-error');dirty.delete(a.id);
        }catch(error){dirty.add(a.id);feedback.textContent=String(error);feedback.classList.add('wf-error');}
        finally{inputs.forEach(input=>input.disabled=false);pending--;updateUpload();}
      });
      editor.append(date,clock.element,save,feedback);schedule.append(editor);row.append(schedule);
      const cell=n('td'),caption=n('details');caption.append(n('summary','Lihat caption'),n('p',a.caption || '(Tanpa caption)','wf-publication-caption'));cell.append(caption);row.append(cell);table.append(row);
    });
    const tableWrap=n('div',undefined,'wf-table-wrap');tableWrap.append(table);body.append(tableWrap,action('Kembali',reviewList),upload);
  }
  async function jobs(){
    reviewGeneration++;
    const result=await api().get_workflow_jobs();clearVideo();body.replaceChildren();
    if(result.worker_note)body.append(n('p',result.worker_note));
    if(!result.jobs.length)body.append(n('p','Belum ada pekerjaan. Pilih campaign dan masukkan sumber pada Create Clip.','wf-empty'));
    result.jobs.forEach(job=>{const row=n('div',undefined,'wf-row');const info=n('div',undefined,'wf-grow');info.append(n('strong',job.campaign?.name || job.campaign_id),n('small',job.source),n('small',job.step || job.error || job.attention || ''));
      if(job.clips?.some(c=>c.status==='error')){const details=n('details');details.append(n('summary','Clip yang gagal'));job.clips.filter(c=>c.status==='error').forEach(c=>details.append(n('p',`${c.title || 'Clip '+c.index}: ${c.error || c.step}`)));info.append(details);}
      row.append(info,badge(job.status));
      if(['failed','partial','interrupted','cancelled','paused'].includes(job.status))row.append(action('Lanjutkan',async()=>{const r=await api().control_job(job.id,'resume');if(r.status!=='ok')throw Error(r.message);await refresh();}));
      if(['queued','running'].includes(job.status))row.append(action('Batalkan',async()=>{await api().control_job(job.id,'cancel');await refresh();}));
      if(job.status==='queued')row.append(action('Jeda',async()=>{await api().control_job(job.id,'pause');await refresh();}));body.append(row);
    });
  }
  async function tracking(){
    reviewGeneration++;
    const result=await api().get_publication_tracking();if(result.status!=='ok')throw Error(result.message);clearVideo();body.replaceChildren();
    const tools=n('div',undefined,'wf-toolbar');tools.append(action(result.sync_running?'Sinkronisasi berjalan':'Sinkronkan provider',async()=>{const r=await api().sync_publications();if(r.status==='error')throw Error(r.message);message('Sinkronisasi berjalan di latar.');}),action('Ekspor CSV',async()=>{const r=await api().export_tracking_csv();if(r.status==='error')throw Error(r.message);}));body.append(tools);
    if(result.sync_error)body.append(n('p',result.sync_error,'wf-error'));
    const pubs=result.publications.filter(p=>!campaignFilter||p.campaign_id===campaignFilter);
    if(!pubs.length)body.append(n('p','Publikasi akan muncul setelah paket review dikirim.','wf-empty'));
    if(result.timezone)window.SSRTime.configure(result.timezone);
    pubs.forEach(p=>{const row=n('div',undefined,'wf-row');const info=n('div',undefined,'wf-grow');info.append(n('strong',p.clip_title),n('small',`${p.account_name} · ${p.platform} · ${window.SSRTime.format(p.scheduled_at)}`));
      if(p.post_url&&/^https?:\/\//.test(p.post_url)){const link=n('a','Buka posting');link.href=p.post_url;link.target='_blank';link.rel='noopener';info.append(link);}
      const metrics=p.metrics?.data || p.metrics;if(metrics)info.append(n('small',Object.entries(metrics).filter(([,v])=>typeof v==='number').map(([k,v])=>`${k}: ${v}`).join(' · ') || 'Metrik belum tersedia'));
      else info.append(n('small','Metrik belum tersedia'));
      if(p.metrics_at)info.append(n('small','Metrik diperbarui '+window.SSRTime.format(p.metrics_at)));
      for(const error of [p.error,p.sync_error,p.metrics_error])if(error)info.append(n('small',error,'wf-error'));
      row.append(info,badge(p.status));if(['queued','failed'].includes(p.status)&&!p.schedule_id&&!p.uncertain_submission)row.append(action('Batalkan',async()=>{const r=await api().control_publication(p.id,'cancel');if(r.status!=='ok')throw Error(r.message);await refresh();}));
      if(p.status==='failed'&&!p.uncertain_submission)row.append(action('Coba lagi',async()=>{const r=await api().control_publication(p.id,'retry');if(r.status!=='ok')throw Error(r.message);await refresh();}));body.append(row);
    });
  }
  async function refresh(filter){
    if(typeof filter==='string'){campaignFilter=filter;activeClip=null;tab='review';}if(busy)return;busy=true;clearTimeout(timer);
    try{el.querySelectorAll('[data-tab]').forEach(b=>b.className='btn '+(b.dataset.tab===tab?'btn-lime':'btn-outline'));
      if(tab==='jobs')await jobs();else if(tab==='tracking')await tracking();else if(!activeClip)await reviewList();
    }catch(e){message(String(e),true);}finally{busy=false;if(tab!=='review')timer=setTimeout(()=>{if(el.classList.contains('active'))refresh();},4000);}
  }
  el.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;activeClip=null;message('');refresh();});
  el.querySelector('[data-action="refresh"]').onclick=async()=>{message('');try{if(activeClip)await openClip(activeClip);else await refresh();}catch(e){message(String(e),true);}};
  return {element:el,refresh};
};
