window.Components = window.Components || {};

window.Components.AiSettingsView = function () {
  const section = document.createElement('section');
  section.className = 'view entrance';
  section.dataset.view = 'settings';

  // Page header + deps
  const headerRow = document.createElement('div');
  headerRow.style.cssText = 'display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:28px;flex-wrap:wrap;gap:16px;';

  const headerLeft = document.createElement('div');
  headerLeft.innerHTML = `<h1 class="page-title">Settings</h1><p class="page-subtitle" style="margin-bottom:0;">An any way to manage sales with care and precision.</p>`;

  const headerRight = document.createElement('div');
  headerRight.style.cssText = 'display:flex;align-items:center;gap:16px;flex-wrap:wrap;';
  headerRight.innerHTML = `
    <div class="dep-status">
      <div class="dep-item"><span class="dep-dot err"></span> yt-dlp</div>
      <div class="dep-item"><span class="dep-dot err"></span> ffmpeg</div>
      <div class="dep-item"><span class="dep-dot err"></span> deno</div>
      <div class="dep-item"><span class="dep-dot err"></span> whisper</div>
    </div>
  `;

  const providerRow = document.createElement('div');
  providerRow.style.cssText = 'display:flex;gap:8px;align-items:center;';

  const largeV3Btn = document.createElement('button');
  largeV3Btn.className = 'btn btn-outline';
  largeV3Btn.style.cssText = 'border-color:var(--border-light);color:var(--text);';
  largeV3Btn.innerHTML = 'Large V3 Turbo <span style="font-size:10px;margin-left:4px;">&gt;</span>';
  providerRow.appendChild(largeV3Btn);

  const installBtn = document.createElement('button');
  installBtn.className = 'btn btn-lime';
  installBtn.textContent = 'Install All';
  providerRow.appendChild(installBtn);

  headerRight.appendChild(providerRow);
  headerRow.appendChild(headerLeft);
  headerRow.appendChild(headerRight);
  section.appendChild(headerRow);

  // Main grid: 2/3 API config + 1/3 Repliz
  const mainGrid = document.createElement('div');
  mainGrid.style.cssText = 'display:grid;grid-template-columns:2fr 1fr;gap:20px;margin-bottom:20px;';

  // ── API Configuration Card ──
  const apiCard = document.createElement('div');
  apiCard.className = 'card';

  const apiHeader = document.createElement('div');
  apiHeader.className = 'card-header';
  apiHeader.innerHTML = `
    <h2 class="card-title">API Configuration</h2>
    <button class="btn btn-outline" id="reload-model-btn">
      <svg style="width:12px;height:12px;" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" stroke-linecap="round" stroke-linejoin="round"></path></svg>
      Reload Model
    </button>
  `;
  apiCard.appendChild(apiHeader);

  const apiBody = document.createElement('div');
  apiBody.className = 'card-body';

  const apiGrid = document.createElement('div');
  apiGrid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:28px 48px;align-items:start;';

  const FIELD_BG = '#EDEDE9';
  const INPUT_H  = '40px';

  function makeApiField(label, placeholder, isSelect) {
    const group = document.createElement('div');
    group.className = 'field-group';
    group.style.cssText = 'margin:0;gap:0;';

    const lbl = document.createElement('label');
    lbl.className = 'field-label';
    lbl.textContent = label;
    group.appendChild(lbl);

    if (isSelect) {
      const sel = document.createElement('select');
      sel.className = 'select';
      sel.style.cssText = `background:${FIELD_BG};border:none;border-radius:6px;height:${INPUT_H};width:100%;font-size:14px;color:var(--text);padding:0 32px 0 12px;cursor:pointer;appearance:none;
        background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236B7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
        background-repeat:no-repeat;background-position:right 12px center;`;
      sel.innerHTML = `<option>${placeholder || 'Select Model'}</option>`;
      group.appendChild(sel);
      return { element: group, input: sel };
    } else {
      const wrapper = document.createElement('div');
      wrapper.style.cssText = 'display:flex;gap:8px;align-items:stretch;';

      const inp = document.createElement('input');
      inp.className = 'input';
      inp.style.cssText = `background:${FIELD_BG};border:none;border-radius:6px;flex:1;height:${INPUT_H};font-size:14px;color:var(--text);padding:0 12px;outline:none;`;
      inp.placeholder = placeholder || '(Opsional) API Key';
      inp.type = 'password';

      const testBtn = document.createElement('button');
      testBtn.style.cssText = `background:${FIELD_BG};border:none;border-radius:6px;padding:0 18px;font-weight:500;font-size:13px;cursor:pointer;height:${INPUT_H};white-space:nowrap;color:var(--text);font-family:inherit;flex-shrink:0;`;
      testBtn.textContent = 'Test';

      wrapper.appendChild(inp);
      wrapper.appendChild(testBtn);
      group.appendChild(wrapper);
      return { element: group, input: inp, testBtn };
    }
  }

  // Row 1: OpenAI + Highlight Finder
  const openai = makeApiField('Open AI', '(Opsional) API Key');
  const hfModel = makeApiField('Highlight Finder', 'Select Model', true);
  apiGrid.appendChild(openai.element);
  apiGrid.appendChild(hfModel.element);

  // Row 2: Anthropic + Caption Maker
  const anthropic = makeApiField('Anthropic', '(Opsional) API Key');
  const cmModel = makeApiField('Caption Maker', 'Large V3 Turbo', true);
  apiGrid.appendChild(anthropic.element);
  apiGrid.appendChild(cmModel.element);

  // Row 3: Gemini + Hook Maker
  const gemini = makeApiField('Gemini', '(Opsional) API Key');
  const hmModel = makeApiField('Hook Maker', 'Gemini 3.1 pro', true);
  apiGrid.appendChild(gemini.element);
  apiGrid.appendChild(hmModel.element);

  // Row 4: Custom Provider + YT Title Maker
  const customRow = document.createElement('div');
  customRow.className = 'field-group';
  customRow.style.cssText = 'grid-column:1;margin:0;gap:0;';

  const customLbl = document.createElement('label');
  customLbl.className = 'field-label';
  customLbl.textContent = 'Custom Provider';
  customRow.appendChild(customLbl);

  const customInputRow = document.createElement('div');
  customInputRow.style.cssText = 'display:flex;gap:8px;align-items:stretch;';

  const FIELD_BG_C = '#EDEDE9';
  const INPUT_H_C = '40px';

  const custEndpointInput = document.createElement('input');
  custEndpointInput.className = 'input';
  custEndpointInput.style.cssText = `background:${FIELD_BG_C};border:none;border-radius:6px;flex:1;height:${INPUT_H_C};font-size:14px;padding:0 12px;outline:none;`;
  custEndpointInput.placeholder = '(Opsional) End Point';

  const custKeyInput = document.createElement('input');
  custKeyInput.className = 'input';
  custKeyInput.style.cssText = `background:${FIELD_BG_C};border:none;border-radius:6px;flex:1;height:${INPUT_H_C};font-size:14px;padding:0 12px;outline:none;`;
  custKeyInput.placeholder = '(Opsional) API Key';
  custKeyInput.type = 'password';

  const custTestBtn = document.createElement('button');
  custTestBtn.style.cssText = `background:${FIELD_BG_C};border:none;border-radius:6px;padding:0 18px;font-weight:500;font-size:13px;cursor:pointer;height:${INPUT_H_C};white-space:nowrap;color:var(--text);font-family:inherit;flex-shrink:0;`;
  custTestBtn.textContent = 'Test';

  customInputRow.appendChild(custEndpointInput);
  customInputRow.appendChild(custKeyInput);
  customInputRow.appendChild(custTestBtn);
  customRow.appendChild(customInputRow);

  const ytTitle = makeApiField('YT Title Maker', 'Claude Sonnet 5', true);

  apiGrid.appendChild(customRow);
  apiGrid.appendChild(ytTitle.element);

  apiBody.appendChild(apiGrid);
  apiCard.appendChild(apiBody);

  // ── Repliz Panel ──
  const repliz = document.createElement('div');
  repliz.className = 'dark-panel';
  repliz.style.cssText = 'background:#060A08;padding:24px;border-radius:8px;display:flex;flex-direction:column;height:100%;min-height:480px;';

  const replizHeader = document.createElement('div');
  replizHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;';
  replizHeader.innerHTML = `
    <h3 style="font-size:20px;font-weight:700;color:white;margin:0;">Repliz</h3>
    <button class="btn-white-pill" style="font-size:12px;padding:6px 14px;border-radius:20px;">Test Connection</button>
  `;
  repliz.appendChild(replizHeader);

  const replizKeys = document.createElement('div');
  replizKeys.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:24px;';
  replizKeys.innerHTML = `
    <div class="field-group" style="margin:0;">
      <label style="font-size:13px;color:#A1A1AA;margin-bottom:8px;display:block;">Access Key</label>
      <input class="input" style="background:#EAEAEA;color:black;border:none;border-radius:4px;" placeholder="Paste here..." type="text">
    </div>
    <div class="field-group" style="margin:0;">
      <label style="font-size:13px;color:#A1A1AA;margin-bottom:8px;display:block;">Secret Key</label>
      <input class="input" style="background:#EAEAEA;color:black;border:none;border-radius:4px;" placeholder="Paste here..." type="password">
    </div>
  `;
  repliz.appendChild(replizKeys);

  const accountsPanel = document.createElement('div');
  accountsPanel.style.cssText = 'flex:1;background:#111810;border-radius:8px;padding:16px;position:relative;overflow:hidden;display:flex;flex-direction:column;';
  accountsPanel.innerHTML = `
    <h4 style="color:#A1A1AA;font-size:13px;font-weight:500;margin:0 0 16px;">16 Account Connected</h4>
    <div style="flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:14px;padding-bottom:60px;">
      ${Array(6).fill(0).map((_, i) => `
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:14px;color:#FFFFFF;font-weight:500;">Cliper Account ${i + 1}</span>
          <div style="display:flex;gap:5px;">
            <div style="width:14px;height:14px;border-radius:50%;background:#BAFF39;"></div>
            <div style="width:14px;height:14px;border-radius:50%;background:#BAFF39;"></div>
            <div style="width:14px;height:14px;border-radius:50%;background:#BAFF39;"></div>
            <div style="width:14px;height:14px;border-radius:50%;background:#BAFF39;"></div>
          </div>
        </div>
      `).join('')}
    </div>
    <div style="position:absolute;bottom:0;left:0;right:0;padding:12px 16px;background:linear-gradient(to top, #111810 55%, transparent);">
      <button class="btn btn-lime-full" style="font-weight:600;font-size:13px;">Connect More</button>
    </div>
  `;
  repliz.appendChild(accountsPanel);

  mainGrid.appendChild(apiCard);
  mainGrid.appendChild(repliz);
  section.appendChild(mainGrid);

  // Save button
  const saveRow = document.createElement('div');
  const saveBtn = document.createElement('button');
  saveBtn.id = 'save_ai';
  saveBtn.className = 'btn btn-lime-full';
  saveBtn.textContent = 'Save Settings';
  saveRow.appendChild(saveBtn);

  const saveStatus = document.createElement('div');
  saveStatus.id = 'ai_status';
  saveStatus.style.cssText = 'font-size:12px;color:var(--text-muted);margin-top:8px;min-height:16px;text-align:center;';
  saveRow.appendChild(saveStatus);

  section.appendChild(saveRow);

  // Hidden URL fields for API compatibility
  // The main OpenAI key field = hfKey (highlight finder key)
  // We map: openai.input -> hfKey, anthropic.input -> cmKey, gemini.input -> hmKey

  // Eye toggle buttons (create hidden ones for compatibility)
  const hfEye = document.createElement('button');
  hfEye.style.display = 'none';
  const cmEye = document.createElement('button');
  cmEye.style.display = 'none';
  const hmEye = document.createElement('button');
  hmEye.style.display = 'none';

  // Hidden URL inputs for custom mode
  const hfUrlInput = document.createElement('input');
  hfUrlInput.type = 'hidden';
  hfUrlInput.value = 'https://api.openai.com/v1';
  const cmUrlInput = document.createElement('input');
  cmUrlInput.type = 'hidden';
  cmUrlInput.value = 'https://api.openai.com/v1';
  const hmUrlInput = document.createElement('input');
  hmUrlInput.type = 'hidden';
  hmUrlInput.value = 'https://api.openai.com/v1';

  section.appendChild(hfUrlInput);
  section.appendChild(cmUrlInput);
  section.appendChild(hmUrlInput);

  // URL field wrappers for compatibility
  const hfUrlField = document.createElement('div');
  hfUrlField.className = 'url-field hidden';
  const cmUrlField = document.createElement('div');
  cmUrlField.className = 'url-field hidden';
  const hmUrlField = document.createElement('div');
  hmUrlField.className = 'url-field hidden';

  // Dummy elements for removed UI to prevent app.js from crashing
  const dummyBtn = document.createElement('button');
  const dummyStatus = document.createElement('span');

  return {
    element: section,
    fields: {
      providerButtons: [],
      hfUrl: hfUrlInput,
      hfUrlField: hfUrlField,
      hfKey: openai.input,
      hfEye: hfEye,
      hfModel: hfModel.input,
      hfValidateBtn: dummyBtn,
      hfValidateStatus: dummyStatus,
      cmUrl: cmUrlInput,
      cmUrlField: cmUrlField,
      cmKey: anthropic.input,
      cmEye: cmEye,
      cmModel: cmModel.input,
      cmValidateBtn: dummyBtn,
      cmValidateStatus: dummyStatus,
      hmUrl: hmUrlInput,
      hmUrlField: hmUrlField,
      hmKey: gemini.input,
      hmEye: hmEye,
      hmModel: hmModel.input,
      hmValidateBtn: dummyBtn,
      hmValidateStatus: dummyStatus,
      saveBtn: saveBtn,
      status: saveStatus,
    }
  };
};
