window.Components = window.Components || {};

window.Components.CampaignEditView = function () {
  const section = document.createElement('section');
  section.className = 'view entrance';
  section.dataset.view = 'campaign-edit';

  const headerRow = document.createElement('div');
  headerRow.style.cssText = 'display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:28px;flex-wrap:wrap;gap:16px;';
  
  const headerLeft = document.createElement('div');
  headerLeft.innerHTML = `
    <h1 class="page-title">Edit Campaign</h1>
    <p class="page-subtitle" style="margin-bottom:0;">Satu brief, aturan editing, dan audiens untuk setiap produksi berikutnya.</p>
  `;
  
  const headerRight = document.createElement('div');
  headerRight.style.cssText = 'display:flex;gap:12px;';
  const backBtn = document.createElement('button');
  backBtn.className = 'btn btn-outline';
  backBtn.textContent = 'Back';
  const saveBtn = document.createElement('button');
  saveBtn.className = 'btn btn-lime';
  saveBtn.textContent = 'Save Campaign';
  
  headerRight.appendChild(backBtn);
  headerRight.appendChild(saveBtn);

  headerRow.appendChild(headerLeft);
  headerRow.appendChild(headerRight);
  section.appendChild(headerRow);

  const grid = document.createElement('div');
  grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:24px;';

  // --- Left Column ---
  const leftCol = document.createElement('div');
  leftCol.style.cssText = 'display:flex;flex-direction:column;gap:16px;';
  
  const briefCard = document.createElement('div');
  briefCard.className = 'card';
  briefCard.style.cssText = 'padding:24px;display:flex;flex-direction:column;gap:16px;';

  const nameGroup = document.createElement('div');
  nameGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Campaign Name</label>`;
  const nameInput = document.createElement('input');
  nameInput.className = 'input';
  nameInput.type = 'text';
  nameGroup.appendChild(nameInput);
  briefCard.appendChild(nameGroup);

  const workspaceFields = {};
  function workspaceField(parent, key, label, options = {}) {
    const group = document.createElement('label');
    group.style.cssText = 'display:flex;flex-direction:column;gap:7px;font-size:13px;font-weight:600;';
    const title = document.createElement('span');
    title.textContent = label;
    const input = document.createElement(options.choices ? 'select' : 'input');
    input.className = options.choices ? 'select' : 'input';
    if (options.choices) {
      options.choices.forEach(([value, text]) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = text;
        input.appendChild(option);
      });
    } else {
      input.type = options.type || 'text';
      if (options.min !== undefined) input.min = options.min;
      if (options.max !== undefined) input.max = options.max;
      if (options.step !== undefined) input.step = options.step;
      input.placeholder = options.placeholder || '';
    }
    if (options.type === 'checkbox') {
      group.style.flexDirection = 'row';
      group.style.alignItems = 'center';
      input.className = '';
      group.append(input, title);
    } else group.append(title, input);
    parent.appendChild(group);
    workspaceFields[key] = input;
    return input;
  }
  workspaceField(briefCard, 'sourcePlatformInput', 'Platform asal campaign', {placeholder: 'Clippo, platform lain, atau campaign langsung'});
  workspaceField(briefCard, 'audienceInput', 'Genre / lingkup audiens', {placeholder: 'Contoh: Film keluarga Indonesia'});
  workspaceField(briefCard, 'languageInput', 'Bahasa konten', {placeholder: 'id'});
  workspaceField(briefCard, 'platformsInput', 'Platform publikasi', {placeholder: 'tiktok, instagram, youtube (kosong = semua)'});

  const statusGroup = document.createElement('div');
  statusGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Status</label>`;
  const statusSelect = document.createElement('select');
  statusSelect.className = 'select';
  statusSelect.innerHTML = `
    <option value="draft">Draft</option>
    <option value="active">Active</option>
    <option value="archived">Archived</option>
  `;
  statusGroup.appendChild(statusSelect);
  briefCard.appendChild(statusGroup);

  const durasiGroup = document.createElement('div');
  durasiGroup.style.cssText = 'display:flex; gap:16px;';
  durasiGroup.innerHTML = `
    <div style="flex:1;">
      <label class="field-label" style="display:block;margin-bottom:6px;">Durasi Min (detik)</label>
      <input type="number" id="campaignDurasiMin" class="input" value="15">
    </div>
    <div style="flex:1;">
      <label class="field-label" style="display:block;margin-bottom:6px;">Durasi Max (detik)</label>
      <input type="number" id="campaignDurasiMax" class="input" value="180">
    </div>
  `;
  briefCard.appendChild(durasiGroup);

  const hashtagsGroup = document.createElement('div');
  hashtagsGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Hashtags (Enter to add)</label>`;
  const hashtagsInputContainer = document.createElement('div');
  hashtagsInputContainer.className = 'chip-container input';
  hashtagsInputContainer.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;padding:8px;min-height:42px;align-items:center;';
  const hashtagsRealInput = document.createElement('input');
  hashtagsRealInput.type = 'text';
  hashtagsRealInput.style.cssText = 'border:none;outline:none;flex:1;min-width:100px;background:transparent;';
  hashtagsRealInput.placeholder = "e.g. #fyp";
  hashtagsInputContainer.appendChild(hashtagsRealInput);
  hashtagsGroup.appendChild(hashtagsInputContainer);
  briefCard.appendChild(hashtagsGroup);

  const taggedAccountsGroup = document.createElement('div');
  taggedAccountsGroup.innerHTML = `<span class="field-label" style="display:block;margin-bottom:6px;">Tag akun</span>`;
  const taggedAccountsPlatform = document.createElement('select');
  taggedAccountsPlatform.className = 'select';
  taggedAccountsPlatform.setAttribute('aria-label', 'Sosmed tag akun');
  for (const [value, text] of [['tiktok', 'TikTok'], ['instagram', 'Instagram']]) {
    const option = document.createElement('option'); option.value = value; option.textContent = text; taggedAccountsPlatform.append(option);
  }
  taggedAccountsPlatform.value = 'tiktok';
  const taggedAccountsInput = document.createElement('input');
  taggedAccountsInput.className = 'input';
  taggedAccountsInput.type = 'text';
  taggedAccountsInput.placeholder = "@akun1, @akun2";
  taggedAccountsInput.setAttribute('aria-label', 'Tag akun TikTok (pisahkan dengan koma)');
  const taggedControls = document.createElement('div'); taggedControls.className = 'wf-account-tags';
  taggedControls.append(taggedAccountsPlatform, taggedAccountsInput);
  const taggedHelp = document.createElement('small'); taggedHelp.className = 'wf-template-intro';
  taggedHelp.textContent = 'Pilih sosmed, lalu isi tag akun dipisahkan dengan koma. Tag TikTok dan Instagram disimpan terpisah.';
  let taggedPlatform = 'tiktok', tagsByPlatform = {tiktok: [], instagram: []};
  const readTags = () => taggedAccountsInput.value.split(',').map(value => value.trim()).filter(Boolean);
  const showTags = () => {
    taggedAccountsInput.value = tagsByPlatform[taggedPlatform].join(', ');
    taggedAccountsInput.setAttribute('aria-label', 'Tag akun '+(taggedPlatform === 'tiktok' ? 'TikTok' : 'Instagram')+' (pisahkan dengan koma)');
  };
  taggedAccountsPlatform.onchange = () => {
    tagsByPlatform[taggedPlatform] = readTags(); taggedPlatform = taggedAccountsPlatform.value; showTags();
  };
  const setTaggedAccounts = (brief = {}) => {
    const tags = brief.tagged_accounts_by_platform || {tiktok: brief.tagged_accounts || [], instagram: brief.tagged_accounts || []};
    tagsByPlatform = {tiktok: [...(tags.tiktok || [])], instagram: [...(tags.instagram || [])]};
    taggedPlatform = 'tiktok'; taggedAccountsPlatform.value = taggedPlatform; showTags();
  };
  const getTaggedAccounts = () => {
    tagsByPlatform[taggedPlatform] = readTags(); return structuredClone(tagsByPlatform);
  };
  taggedAccountsGroup.append(taggedControls, taggedHelp);
  briefCard.appendChild(taggedAccountsGroup);

  const hooksGroup = document.createElement('div');
  const hooksHeader = document.createElement('div');
  hooksHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;';
  hooksHeader.innerHTML = `<label class="field-label" style="margin:0;">Hooks List</label>`;
  const addHookBtn = document.createElement('button');
  addHookBtn.className = 'btn btn-outline';
  addHookBtn.style.padding = '4px 8px';
  addHookBtn.style.fontSize = '12px';
  addHookBtn.textContent = '+ tambah hook';
  hooksHeader.appendChild(addHookBtn);
  hooksGroup.appendChild(hooksHeader);
  const hooksList = document.createElement('div');
  hooksList.style.cssText = 'display:flex;flex-direction:column;gap:8px;';
  hooksGroup.appendChild(hooksList);
  briefCard.appendChild(hooksGroup);

  const catatanGroup = document.createElement('div');
  catatanGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Catatan Campaign</label>`;
  const catatanArea = document.createElement('textarea');
  catatanArea.className = 'input';
  catatanArea.style.cssText = 'height:80px;resize:vertical;padding:12px;';
  catatanGroup.appendChild(catatanArea);
  briefCard.appendChild(catatanGroup);

  const anglesGroup = document.createElement('div');
  anglesGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Angles (Enter to add)</label>`;
  const anglesInputContainer = document.createElement('div');
  anglesInputContainer.className = 'chip-container input';
  anglesInputContainer.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;padding:8px;min-height:42px;align-items:center;';
  const anglesRealInput = document.createElement('input');
  anglesRealInput.type = 'text';
  anglesRealInput.style.cssText = 'border:none;outline:none;flex:1;min-width:100px;background:transparent;';
  anglesInputContainer.appendChild(anglesRealInput);
  anglesGroup.appendChild(anglesInputContainer);
  briefCard.appendChild(anglesGroup);

  const personaGroup = document.createElement('div');
  personaGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Persona</label>`;
  const personaArea = document.createElement('textarea');
  personaArea.className = 'input';
  personaArea.style.cssText = 'height:60px;resize:vertical;padding:12px;';
  personaGroup.appendChild(personaArea);
  briefCard.appendChild(personaGroup);

  const goalsGroup = document.createElement('div');
  goalsGroup.style.cssText = 'display:flex; gap:16px;';
  goalsGroup.innerHTML = `
    <div style="flex:1;">
      <label class="field-label" style="display:block;margin-bottom:6px;">Tujuan</label>
      <input type="text" id="campaignTujuan" class="input">
    </div>
    <div style="flex:1;">
      <label class="field-label" style="display:block;margin-bottom:6px;">CTA</label>
      <input type="text" id="campaignCta" class="input">
    </div>
  `;
  briefCard.appendChild(goalsGroup);

  const accountPickerGroup = document.createElement('div');
  accountPickerGroup.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;"><label class="field-label" style="margin:0;">Hubungkan Akun</label><span id="campaignAccountCounter" style="font-size:12px;color:var(--text-muted);">0/0 akun dipilih</span></div>`;
  const accountPickerList = document.createElement('div');
  accountPickerList.style.cssText = 'max-height:420px;overflow-y:auto;border:1px solid var(--border,#ced4da);border-radius:8px;padding:12px;display:flex;flex-direction:column;gap:12px;';
  accountPickerGroup.appendChild(accountPickerList);
  briefCard.appendChild(accountPickerGroup);

  leftCol.appendChild(briefCard);

  const highlightProfileHost = document.createElement('div');
  highlightProfileHost.className = 'card';
  leftCol.appendChild(highlightProfileHost);

  const rulesCard = document.createElement('div');
  rulesCard.className = 'card';
  rulesCard.style.cssText = 'padding:24px;display:flex;flex-direction:column;gap:16px;';
  rulesCard.innerHTML = `<h3 style="margin:0;font-size:16px;">Aturan dan Larangan</h3>`;

  const doGroup = document.createElement('div');
  const doHeader = document.createElement('div');
  doHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;';
  doHeader.innerHTML = `<label class="field-label" style="margin:0;">Do (Aturan Boleh)</label>`;
  const addDoBtn = document.createElement('button');
  addDoBtn.className = 'btn btn-outline';
  addDoBtn.style.padding = '4px 8px';
  addDoBtn.style.fontSize = '12px';
  addDoBtn.textContent = '+ tambah';
  doHeader.appendChild(addDoBtn);
  doGroup.appendChild(doHeader);
  const doRulesList = document.createElement('div');
  doRulesList.style.cssText = 'display:flex;flex-direction:column;gap:8px;';
  doGroup.appendChild(doRulesList);
  rulesCard.appendChild(doGroup);

  const dontGroup = document.createElement('div');
  const dontHeader = document.createElement('div');
  dontHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;';
  dontHeader.innerHTML = `<label class="field-label" style="margin:0;">Don't (Larangan)</label>`;
  const addDontBtn = document.createElement('button');
  addDontBtn.className = 'btn btn-outline';
  addDontBtn.style.padding = '4px 8px';
  addDontBtn.style.fontSize = '12px';
  addDontBtn.textContent = '+ tambah';
  dontHeader.appendChild(addDontBtn);
  dontGroup.appendChild(dontHeader);
  const dontRulesList = document.createElement('div');
  dontRulesList.style.cssText = 'display:flex;flex-direction:column;gap:8px;';
  dontGroup.appendChild(dontRulesList);
  rulesCard.appendChild(dontGroup);

  const aturanUmumGroup = document.createElement('div');
  const aturanUmumHeader = document.createElement('div');
  aturanUmumHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;';
  aturanUmumHeader.innerHTML = `<label class="field-label" style="margin:0;">Aturan Umum</label>`;
  const addAturanUmumBtn = document.createElement('button');
  addAturanUmumBtn.className = 'btn btn-outline';
  addAturanUmumBtn.style.padding = '4px 8px';
  addAturanUmumBtn.style.fontSize = '12px';
  addAturanUmumBtn.textContent = '+ tambah aturan';
  aturanUmumHeader.appendChild(addAturanUmumBtn);
  aturanUmumGroup.appendChild(aturanUmumHeader);
  const aturanUmumList = document.createElement('div');
  aturanUmumList.style.cssText = 'display:flex;flex-direction:column;gap:8px;';
  aturanUmumGroup.appendChild(aturanUmumList);
  rulesCard.appendChild(aturanUmumGroup);

  leftCol.appendChild(rulesCard);
  grid.appendChild(leftCol);

  // --- Right Column ---
  const rightCol = document.createElement('div');
  rightCol.style.cssText = 'display:flex;flex-direction:column;gap:16px;';

  const bannerCard = document.createElement('div');
  bannerCard.className = 'card';
  bannerCard.style.cssText = 'padding:24px;text-align:center;';
  bannerCard.innerHTML = `<label class="field-label" style="display:block;margin-bottom:12px;text-align:left;">Campaign Banner</label>`;

  const bannerPreview = document.createElement('div');
  bannerPreview.style.cssText = 'width:100%;aspect-ratio:3/2;background:#e9ecef;border-radius:8px;display:flex;align-items:center;justify-content:center;margin-bottom:16px;cursor:pointer;background-size:cover;background-position:center;border:2px dashed #ced4da;position:relative;';
  
  const bannerText = document.createElement('span');
  bannerText.textContent = 'Click to upload banner (3:2)';
  bannerText.style.color = '#6c757d';
  bannerPreview.appendChild(bannerText);
  
  const bannerInput = document.createElement('input');
  bannerInput.type = 'file';
  bannerInput.accept = 'image/*';
  bannerInput.style.display = 'none';

  const statsDiv = document.createElement('div');
  statsDiv.style.cssText = 'margin-top:16px;text-align:left;font-size:14px;color:var(--text-muted);display:none;';
  
  const cardBtnsDiv = document.createElement('div');
  cardBtnsDiv.style.cssText = 'display:none;gap:8px;margin-top:16px;';
  const stokBtn = document.createElement('button');
  stokBtn.className = 'btn btn-outline';
  stokBtn.style.flex = '1';
  stokBtn.textContent = 'Stok';
  const uploadBtn = document.createElement('button');
  uploadBtn.className = 'btn btn-lime';
  uploadBtn.style.flex = '1';
  uploadBtn.textContent = 'Upload';
  cardBtnsDiv.appendChild(stokBtn);
  cardBtnsDiv.appendChild(uploadBtn);
  
  bannerCard.appendChild(bannerInput);
  bannerCard.appendChild(bannerPreview);
  bannerCard.appendChild(statsDiv);
  bannerCard.appendChild(cardBtnsDiv);
  rightCol.appendChild(bannerCard);
  
  const aiQuickCard = document.createElement('div');
  aiQuickCard.className = 'card';
  aiQuickCard.style.cssText = 'padding:24px;background:#F2FCE2;border:1px dashed #8DC63F;display:flex;flex-direction:column;gap:12px;';
  aiQuickCard.innerHTML = `<h3 style="margin:0;font-size:16px;color:#137333;">Brief &amp; aset campaign</h3><p style="margin:0;font-size:13px;line-height:1.5;color:#365534;">Tambahkan beberapa dokumen, gambar, video, atau musik. AI membaca file dengan peran Brief dan menampilkan perbedaan aturan untuk kamu periksa.</p>`;

  const campaignLinkLabel = document.createElement('label');
  campaignLinkLabel.className = 'wf-field';
  campaignLinkLabel.textContent = 'Link campaign Clippo';
  const campaignLinkRow = document.createElement('div');
  campaignLinkRow.className = 'wf-campaign-link';
  const campaignUrlInput = document.createElement('input');
  campaignUrlInput.type = 'url';
  campaignUrlInput.className = 'input';
  campaignUrlInput.placeholder = 'https://app.clippo.id/campaigns/…';
  campaignUrlInput.autocomplete = 'off';
  campaignUrlInput.setAttribute('aria-label', 'Link campaign Clippo');
  const importLinkBtn = document.createElement('button');
  importLinkBtn.type = 'button';
  importLinkBtn.className = 'btn btn-outline';
  importLinkBtn.textContent = 'Muat ulang link';
  campaignLinkRow.append(campaignUrlInput, importLinkBtn);
  campaignLinkLabel.append(campaignLinkRow);
  const campaignLinkHint = document.createElement('p');
  campaignLinkHint.className = 'wf-template-intro';
  campaignLinkHint.textContent = 'Tempel link untuk mengisi brief otomatis. Materi wajib tetap perlu dipilih sebagai file lokal sebelum produksi.';
  const sourceLinkList = document.createElement('div');
  sourceLinkList.className = 'wf-source-links';
  aiQuickCard.append(campaignLinkLabel, campaignLinkHint, sourceLinkList);
  
  const contextArea = document.createElement('textarea');
  contextArea.className = 'input';
  contextArea.style.cssText = 'height:100px;resize:vertical;padding:12px;background:white;';
  contextArea.placeholder = 'Paste brief text here...';
  
  const extractRow = document.createElement('div');
  extractRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;gap:12px;';
  
  const docFile = document.createElement('input');
  docFile.type = 'file';
  docFile.accept = '.txt,.md,.srt,.pdf,.docx,.png,.jpg,.jpeg,.webp,.mp4,.mov,.mkv,.webm,.mp3,.wav,.m4a,.aac,.flac,.ogg';
  docFile.multiple = true;
  docFile.style.display = 'none';
  const docLabel = document.createElement('label');
  docLabel.className = 'btn btn-outline';
  docLabel.style.background = 'white';
  docLabel.textContent = '+ Tambahkan file';
  docLabel.tabIndex = 0;
  docLabel.setAttribute('role', 'button');
  docLabel.appendChild(docFile);
  
  const extractBtn = document.createElement('button');
  extractBtn.className = 'btn btn-lime';
  extractBtn.textContent = 'Baca brief dengan AI';
  
  extractRow.appendChild(docLabel);
  extractRow.appendChild(extractBtn);
  
  aiQuickCard.appendChild(contextArea);
  aiQuickCard.appendChild(extractRow);
  const assetList = document.createElement('div');
  assetList.style.cssText = 'display:flex;flex-direction:column;gap:10px;';
  const extractionStatus = document.createElement('div');
  extractionStatus.setAttribute('role', 'status');
  extractionStatus.style.cssText = 'font-size:13px;line-height:1.6;';
  const extractionDetails = document.createElement('div');
  extractionDetails.style.cssText = 'display:flex;flex-direction:column;gap:10px;font-size:13px;';
  aiQuickCard.append(assetList, extractionStatus, extractionDetails);
  rightCol.appendChild(aiQuickCard);

  const editingCard = document.createElement('div');
  editingCard.className = 'card';
  editingCard.style.cssText = 'padding:24px;display:flex;flex-direction:column;gap:16px;';
  editingCard.innerHTML = '<h3 style="margin:0;font-size:16px;">Template editing</h3><p class="wf-template-intro">Aktifkan template yang boleh digunakan, lalu atur peluangnya. Setiap clip mendapat satu template secara acak.</p>';
  const editingPresetList = document.createElement('fieldset');
  editingPresetList.className = 'wf-editing-presets';
  const templateLegend = document.createElement('legend');templateLegend.textContent = 'Template yang digunakan';
  editingPresetList.append(templateLegend);
  const editingPresetFeatures = document.createElement('dl');
  editingPresetFeatures.className = 'wf-preset-features';
  editingPresetFeatures.setAttribute('aria-label','Isi template editing');
  const editingPresetNote = document.createElement('p');
  editingPresetNote.className = 'wf-template-intro';editingPresetNote.textContent = 'Memuat template…';
  editingPresetNote.setAttribute('role','status');
  const templatePreviewHost = document.createElement('div');templatePreviewHost.className = 'wf-template-preview';
  editingCard.append(editingPresetList,editingPresetFeatures,editingPresetNote,templatePreviewHost);
  const editingDetails = document.createElement('details');editingDetails.className = 'wf-campaign-editing-details';
  const detailsTitle = document.createElement('summary');detailsTitle.textContent = 'Musik, framing, dan aturan produksi';
  const editingOptions = document.createElement('div');editingOptions.className = 'wf-campaign-editing-options';
  editingDetails.append(detailsTitle,editingOptions);editingCard.append(editingDetails);
  workspaceField(editingOptions, 'framingSelect', 'Framing', {choices: [['speaker','Ikuti pembicara'],['fit','Tampilkan seluruh frame'],['center','Crop tengah']]});
  workspaceField(editingOptions, 'sourceRoleSelect', 'Video yang dimasukkan saat produksi', {choices: [['external','Materi luar campaign'],['campaign','Materi resmi campaign']]});
  workspaceField(editingOptions, 'musicPolicySelect', 'Musik untuk semua clip', {choices: [['auto','Pilih musik otomatis'],['local','Gunakan file campaign']]});
  workspaceField(editingOptions, 'musicCatalogSelect', 'Katalog musik otomatis', {choices: [['jamendo','Jamendo · instrumental'],['repliz','TikTok · Repliz']]});
  workspaceField(editingOptions, 'musicReferenceSelect', 'Nuansa rujukan', {choices: [['reference_clips','Reflektif / Action'],['now_or_never','YoaClips · edit self-growth'],['adaptive','Ikuti isi clip']]});
  workspaceField(editingOptions, 'musicStyleInput', 'Arahan musik', {placeholder: 'Contoh: beat tegas, dialog tetap dominan, naik saat penutup'});
  workspaceFields.musicStyleInput.maxLength=1000;
  workspaceField(editingOptions, 'musicAssetSelect', 'File musik', {choices: [['','Pilih dari aset campaign']]});
  const musicNote=document.createElement('p');musicNote.className='wf-template-intro';musicNote.textContent='Musik wajib terpasang sebelum clip dinyatakan selesai. Jika musik otomatis gagal, periksa koneksi atau pilih file musik sebelum membuat job baru.';editingOptions.append(musicNote);
  workspaceField(editingOptions, 'musicMixOverrideCheck', 'Gunakan mixing khusus campaign', {type:'checkbox'});
  const mixingNote=document.createElement('p');mixingNote.className='wf-template-intro';mixingNote.textContent='Jika tidak dipilih, volume, ducking, dan fade mengikuti template Editor. Musik tetap wajib untuk semua clip.';editingOptions.append(mixingNote);
  workspaceField(editingOptions, 'musicVolumeInput', 'Volume musik (1–100%)', {type:'number',min:1,max:100,step:1});
  workspaceField(editingOptions, 'musicStartInput', 'Mulai lagu dari detik', {type:'number',min:0,max:86400,step:0.1});
  workspaceField(editingOptions, 'musicDuckCheck', 'Turunkan musik saat ada dialog', {type:'checkbox'});
  workspaceField(editingOptions, 'endcardAssetSelect', 'Penutup campaign', {choices: [['','Tanpa penutup']]});
  workspaceField(editingOptions, 'endcardRequiredCheck', 'Penutup ini wajib', {type:'checkbox'});
  workspaceField(editingOptions, 'endcardDurationInput', 'Durasi penutup (detik)', {type:'number',min:0.1,max:60,step:0.1});
  const endcardNote=document.createElement('p');endcardNote.className='wf-template-intro';
  endcardNote.textContent='CTA/penutup ditambahkan jika aset tersedia. Tanpa aset dan tanpa kewajiban, clip selesai tanpa CTA. Jika penutup diwajibkan campaign, aset harus tersedia sebelum render.';
  editingOptions.append(endcardNote);
  const ruangHookOptions = document.createElement('fieldset');
  ruangHookOptions.innerHTML = '<legend>Kartu hook · template Ruang</legend><p class="wf-template-intro">Judul dan deskripsi kosong akan mengikuti cerita setiap clip. Perubahan diterapkan saat render berikutnya.</p>';
  workspaceField(ruangHookOptions, 'ruangHookTitle', 'Judul kartu (opsional)', {placeholder:'Otomatis dari setiap clip'});
  workspaceField(ruangHookOptions, 'ruangHookDescription', 'Deskripsi kartu (opsional)', {placeholder:'Otomatis dari setiap clip'});
  workspaceFields.ruangHookTitle.maxLength=100;
  workspaceFields.ruangHookDescription.maxLength=220;
  workspaceField(ruangHookOptions, 'ruangHookStrip', 'Teks strip berjalan', {});
  workspaceField(ruangHookOptions, 'ruangHookAccent', 'Warna judul dan strip', {type:'color'});
  workspaceField(ruangHookOptions, 'ruangHookBackground', 'Warna kartu', {type:'color'});
  workspaceField(ruangHookOptions, 'ruangHookTextColor', 'Warna deskripsi', {type:'color'});
  editingOptions.append(ruangHookOptions);
  workspaceField(editingOptions, 'externalRatioInput', 'Batas materi luar campaign (%)', {type:'number',min:0,max:100,step:1});
  workspaceField(editingOptions, 'externalStrictCheck', 'Proporsi harus kurang dari batas (bukan sama dengan)', {type:'checkbox'});
  workspaceField(editingOptions, 'maxWorkersInput', 'Clip diproses bersamaan', {type:'number',min:1,max:8,step:1});
  workspaceField(editingOptions, 'reviewModeSelect', 'Persetujuan hasil', {choices: [['manual','Review manual sebelum upload'],['automatic','Otomatis setelah semua pemeriksaan lolos']]});
  rightCol.prepend(editingCard);
  const additionalHost = document.createElement('div');
  additionalHost.className = 'card wf-additional-card';
  editingCard.after(additionalHost);
  const readinessStatus = document.createElement('div');
  readinessStatus.setAttribute('role','status');
  readinessStatus.style.cssText = 'font-size:13px;line-height:1.6;padding:16px;border:1px solid var(--border);border-radius:8px;white-space:pre-line;';
  rightCol.appendChild(readinessStatus);

  grid.appendChild(rightCol);
  section.appendChild(grid);

  return {
    element: section,
    fields: {
      ...workspaceFields,
      editingPresetList,
      editingPresetFeatures,
      editingPresetNote,
      templatePreviewHost,
      additionalHost,
      highlightProfileHost,
      assetList,
      campaignUrlInput,
      importLinkBtn,
      sourceLinkList,
      extractionStatus,
      extractionDetails,
      readinessStatus,
      backBtn,
      saveBtn,
      nameInput,
      statusSelect,
      
      durasiMinInput: durasiGroup.querySelector('#campaignDurasiMin'),
      durasiMaxInput: durasiGroup.querySelector('#campaignDurasiMax'),
      hashtagsInput: hashtagsInputContainer,
      hashtagsRealInput,
      taggedAccountsInput,
      taggedAccountsPlatform,
      setTaggedAccounts,
      getTaggedAccounts,
      hooksList,
      addHookBtn,
      catatanArea,
      anglesInput: anglesInputContainer,
      anglesRealInput,
      personaArea,
      tujuanInput: goalsGroup.querySelector('#campaignTujuan'),
      ctaInput: goalsGroup.querySelector('#campaignCta'),
      
      doRulesList,
      addDoBtn,
      dontRulesList,
      addDontBtn,
      aturanUmumList,
      addAturanUmumBtn,
      
      accountPickerList,
      accountCounter: accountPickerGroup.querySelector('#campaignAccountCounter'),

      bannerInput,
      bannerPreview,
      bannerText,
      statsDiv,
      cardBtnsDiv,
      stokBtn,
      uploadBtn,
      
      contextArea,
      docFile,
      extractBtn
    }
  };
};
