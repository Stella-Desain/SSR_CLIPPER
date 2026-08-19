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
    <p class="page-subtitle" style="margin-bottom:0;">Configure campaign details and extract AI brief.</p>
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
  grid.style.cssText = 'display:grid;grid-template-columns:1.3fr 1fr;gap:24px;';

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

  const statusGroup = document.createElement('div');
  statusGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Status</label>`;
  const statusSelect = document.createElement('select');
  statusSelect.className = 'select';
  statusSelect.innerHTML = `
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

  const maxClipsPerDayGroup = document.createElement('div');
  maxClipsPerDayGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Maks Clip per Akun / Hari</label>
    <input type="number" id="campaignMaxClipsPerDay" class="input" value="2" min="1">`;
  briefCard.appendChild(maxClipsPerDayGroup);

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
  taggedAccountsGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Tagged Accounts (comma-separated)</label>`;
  const taggedAccountsInput = document.createElement('input');
  taggedAccountsInput.className = 'input';
  taggedAccountsInput.type = 'text';
  taggedAccountsInput.placeholder = "@akun1, @akun2";
  taggedAccountsGroup.appendChild(taggedAccountsInput);
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
  accountPickerList.style.cssText = 'max-height:150px;overflow-y:auto;border:1px solid #ced4da;border-radius:6px;padding:8px;display:flex;flex-direction:column;gap:8px;background:#f8f9fa;';
  accountPickerGroup.appendChild(accountPickerList);
  briefCard.appendChild(accountPickerGroup);

  leftCol.appendChild(briefCard);

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

  bannerPreview.addEventListener('click', () => bannerInput.click());

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
  aiQuickCard.innerHTML = `<h3 style="margin:0;font-size:16px;color:#137333;">AI Quick-fill Brief</h3>`;
  
  const contextArea = document.createElement('textarea');
  contextArea.className = 'input';
  contextArea.style.cssText = 'height:100px;resize:vertical;padding:12px;background:white;';
  contextArea.placeholder = 'Paste brief text here...';
  
  const extractRow = document.createElement('div');
  extractRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;gap:12px;';
  
  const docFile = document.createElement('input');
  docFile.type = 'file';
  docFile.accept = '.txt,.pdf,.docx,.png,.jpg,.jpeg,.webp';
  docFile.style.display = 'none';
  const docLabel = document.createElement('label');
  docLabel.className = 'btn btn-outline';
  docLabel.style.background = 'white';
  docLabel.textContent = 'Upload Document';
  docLabel.appendChild(docFile);
  
  const extractBtn = document.createElement('button');
  extractBtn.className = 'btn btn-lime';
  extractBtn.textContent = 'Create brief';
  
  extractRow.appendChild(docLabel);
  extractRow.appendChild(extractBtn);
  
  aiQuickCard.appendChild(contextArea);
  aiQuickCard.appendChild(extractRow);
  rightCol.appendChild(aiQuickCard);

  grid.appendChild(rightCol);
  section.appendChild(grid);

  return {
    element: section,
    fields: {
      backBtn,
      saveBtn,
      nameInput,
      statusSelect,
      
      durasiMinInput: durasiGroup.querySelector('#campaignDurasiMin'),
      durasiMaxInput: durasiGroup.querySelector('#campaignDurasiMax'),
      maxClipsPerDayInput: maxClipsPerDayGroup.querySelector('#campaignMaxClipsPerDay'),
      hashtagsInput: hashtagsInputContainer,
      hashtagsRealInput,
      taggedAccountsInput,
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
