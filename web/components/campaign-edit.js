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
  grid.style.cssText = 'display:grid;grid-template-columns:2fr 1fr;gap:24px;';

  // Left Column
  const leftCol = document.createElement('div');
  leftCol.style.cssText = 'display:flex;flex-direction:column;gap:16px;';
  
  const card = document.createElement('div');
  card.className = 'card';
  card.style.cssText = 'padding:24px;display:flex;flex-direction:column;gap:16px;';

  const nameGroup = document.createElement('div');
  nameGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Campaign Name</label>`;
  const nameInput = document.createElement('input');
  nameInput.className = 'input';
  nameInput.type = 'text';
  nameGroup.appendChild(nameInput);
  card.appendChild(nameGroup);

  const statusGroup = document.createElement('div');
  statusGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Status</label>`;
  const statusSelect = document.createElement('select');
  statusSelect.className = 'select';
  statusSelect.innerHTML = `
    <option value="active">Active</option>
    <option value="archived">Archived</option>
  `;
  statusGroup.appendChild(statusSelect);
  card.appendChild(statusGroup);

  const contextGroup = document.createElement('div');
  contextGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Context / Brief (Paste here or upload document below)</label>`;
  const contextArea = document.createElement('textarea');
  contextArea.className = 'input';
  contextArea.style.cssText = 'height:100px;resize:vertical;padding:12px;';
  contextGroup.appendChild(contextArea);
  
  const extractRow = document.createElement('div');
  extractRow.style.cssText = 'display:flex;justify-content:flex-end;margin-top:8px;align-items:center;gap:12px;';
  const docFile = document.createElement('input');
  docFile.type = 'file';
  docFile.accept = '.txt,.pdf,.docx';
  docFile.style.display = 'none';
  const docLabel = document.createElement('label');
  docLabel.className = 'btn btn-outline';
  docLabel.textContent = 'Upload Document';
  docLabel.appendChild(docFile);
  
  const extractBtn = document.createElement('button');
  extractBtn.className = 'btn btn-outline';
  extractBtn.textContent = 'Extract AI Brief';
  
  extractRow.appendChild(docLabel);
  extractRow.appendChild(extractBtn);
  contextGroup.appendChild(extractRow);
  card.appendChild(contextGroup);

  const hookGroup = document.createElement('div');
  hookGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Extracted Hook Settings (AI Output)</label>`;
  const hookArea = document.createElement('textarea');
  hookArea.className = 'input';
  hookArea.style.cssText = 'height:120px;resize:vertical;padding:12px;background:#f8f9fa;';
  hookArea.placeholder = 'AI extracted brief will appear here...';
  hookArea.readOnly = true;
  hookGroup.appendChild(hookArea);
  card.appendChild(hookGroup);

  leftCol.appendChild(card);
  grid.appendChild(leftCol);

  // Right Column
  const rightCol = document.createElement('div');
  rightCol.style.cssText = 'display:flex;flex-direction:column;gap:16px;';

  const bannerCard = document.createElement('div');
  bannerCard.className = 'card';
  bannerCard.style.cssText = 'padding:24px;text-align:center;';
  bannerCard.innerHTML = `<label class="field-label" style="display:block;margin-bottom:12px;text-align:left;">Campaign Banner</label>`;

  const bannerPreview = document.createElement('div');
  bannerPreview.style.cssText = 'width:100%;aspect-ratio:16/9;background:#e9ecef;border-radius:8px;display:flex;align-items:center;justify-content:center;margin-bottom:16px;cursor:pointer;background-size:cover;background-position:center;border:2px dashed #ced4da;position:relative;';
  
  const bannerText = document.createElement('span');
  bannerText.textContent = 'Click to upload banner (16:9)';
  bannerText.style.color = '#6c757d';
  bannerPreview.appendChild(bannerText);
  
  const bannerInput = document.createElement('input');
  bannerInput.type = 'file';
  bannerInput.accept = 'image/*';
  bannerInput.style.display = 'none';

  bannerPreview.addEventListener('click', () => bannerInput.click());

  const statsDiv = document.createElement('div');
  statsDiv.style.cssText = 'margin-top:24px;text-align:left;font-size:14px;color:var(--text-muted);display:none;';
  
  bannerCard.appendChild(bannerInput);
  bannerCard.appendChild(bannerPreview);
  bannerCard.appendChild(statsDiv);
  rightCol.appendChild(bannerCard);
  
  grid.appendChild(rightCol);
  section.appendChild(grid);

  return {
    element: section,
    fields: {
      backBtn,
      saveBtn,
      nameInput,
      statusSelect,
      contextArea,
      docFile,
      extractBtn,
      hookArea,
      bannerInput,
      bannerPreview,
      bannerText,
      statsDiv
    }
  };
};
