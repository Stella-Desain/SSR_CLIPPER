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

  const whisperModelSelect = document.createElement('select');
  whisperModelSelect.className = 'select';
  whisperModelSelect.style.cssText = 'border-color:var(--border-light);color:var(--text);height:40px;padding:0 32px 0 16px;font-weight:600;font-size:14px;background-color:#FFFFFF;cursor:pointer;';
  whisperModelSelect.innerHTML = `
    <option value="api">API</option>
    <option value="large-v3-turbo">large-v3-turbo - 1.5gb</option>
    <option value="medium">Medium - 1.4gb</option>
  `;
  providerRow.appendChild(whisperModelSelect);

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
      const wrapper = document.createElement('div');
      wrapper.style.cssText = 'display:flex;gap:8px;align-items:stretch;';

      const sel = document.createElement('select');
      sel.className = 'select';
      sel.style.cssText = `background:${FIELD_BG};border:none;border-radius:6px;height:${INPUT_H};flex:1;font-size:14px;color:var(--text);padding:0 32px 0 12px;cursor:pointer;appearance:none;
        background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236B7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
        background-repeat:no-repeat;background-position:right 12px center;`;
      sel.innerHTML = `<option>${placeholder || 'Select Model'}</option>`;

      const testBtn = document.createElement('button');
      testBtn.style.cssText = `background:${FIELD_BG};border:none;border-radius:6px;padding:0 18px;font-weight:500;font-size:13px;cursor:pointer;height:${INPUT_H};white-space:nowrap;color:var(--text);font-family:inherit;flex-shrink:0;`;
      testBtn.textContent = 'Test';

      wrapper.appendChild(sel);
      wrapper.appendChild(testBtn);
      group.appendChild(wrapper);

      const statusSpan = document.createElement('span');
      statusSpan.style.cssText = 'font-size:12px; margin-top:4px; min-height:16px; display:block;';
      group.appendChild(statusSpan);

      return { element: group, input: sel, testBtn, status: statusSpan };
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
      
      const statusSpan = document.createElement('span');
      statusSpan.style.cssText = 'font-size:12px; margin-top:4px; min-height:16px; display:block;';
      group.appendChild(statusSpan);
      
      return { element: group, input: inp, testBtn, status: statusSpan };
    }
  }

  // Row 1: OpenAI + Highlight Finder
  const openai = makeApiField('Open AI', '(Opsional) API Key');
  const hfModel = makeApiField('Highlight Finder', 'Select Model', true);
  apiGrid.appendChild(openai.element);
  apiGrid.appendChild(hfModel.element);

  // Row 2: Gemini + Caption Maker
  const gemini = makeApiField('Gemini', '(Opsional) API Key');
  const cmModel = makeApiField('Caption Maker', 'Select Model', true);
  apiGrid.appendChild(gemini.element);
  apiGrid.appendChild(cmModel.element);

  const FIELD_BG_C = '#EDEDE9';
  const INPUT_H_C = '40px';

  // Row 3: Custom Provider 1 + Hook Maker
  const custom1Row = document.createElement('div');
  custom1Row.className = 'field-group';
  custom1Row.style.cssText = 'grid-column:1;margin:0;gap:0;';

  const custom1Lbl = document.createElement('label');
  custom1Lbl.className = 'field-label';
  custom1Lbl.textContent = 'Custom Provider 1';
  custom1Row.appendChild(custom1Lbl);

  const custom1InputRow = document.createElement('div');
  custom1InputRow.style.cssText = 'display:flex;gap:8px;align-items:stretch;';

  const cust1EndpointInput = document.createElement('input');
  cust1EndpointInput.className = 'input';
  cust1EndpointInput.style.cssText = `background:${FIELD_BG_C};border:none;border-radius:6px;flex:1;height:${INPUT_H_C};font-size:14px;padding:0 12px;outline:none;`;
  cust1EndpointInput.placeholder = '(Opsional) End Point';

  const cust1KeyInput = document.createElement('input');
  cust1KeyInput.className = 'input';
  cust1KeyInput.style.cssText = `background:${FIELD_BG_C};border:none;border-radius:6px;flex:1;height:${INPUT_H_C};font-size:14px;padding:0 12px;outline:none;`;
  cust1KeyInput.placeholder = '(Opsional) API Key';
  cust1KeyInput.type = 'password';

  const cust1TestBtn = document.createElement('button');
  cust1TestBtn.style.cssText = `background:${FIELD_BG_C};border:none;border-radius:6px;padding:0 18px;font-weight:500;font-size:13px;cursor:pointer;height:${INPUT_H_C};white-space:nowrap;color:var(--text);font-family:inherit;flex-shrink:0;`;
  cust1TestBtn.textContent = 'Test';

  custom1InputRow.appendChild(cust1EndpointInput);
  custom1InputRow.appendChild(cust1KeyInput);
  custom1InputRow.appendChild(cust1TestBtn);
  custom1Row.appendChild(custom1InputRow);
  
  const cust1TestStatus = document.createElement('span');
  cust1TestStatus.style.cssText = 'font-size:12px; margin-top:4px; min-height:16px; display:block;';
  custom1Row.appendChild(cust1TestStatus);

  const hmModel = makeApiField('Hook Maker', 'Select Model', true);
  apiGrid.appendChild(custom1Row);
  apiGrid.appendChild(hmModel.element);

  // Row 4: Custom Provider 2 + YT Title Maker
  const custom2Row = document.createElement('div');
  custom2Row.className = 'field-group';
  custom2Row.style.cssText = 'grid-column:1;margin:0;gap:0;';

  const custom2Lbl = document.createElement('label');
  custom2Lbl.className = 'field-label';
  custom2Lbl.textContent = 'Custom Provider 2';
  custom2Row.appendChild(custom2Lbl);

  const custom2InputRow = document.createElement('div');
  custom2InputRow.style.cssText = 'display:flex;gap:8px;align-items:stretch;';

  const cust2EndpointInput = document.createElement('input');
  cust2EndpointInput.className = 'input';
  cust2EndpointInput.style.cssText = `background:${FIELD_BG_C};border:none;border-radius:6px;flex:1;height:${INPUT_H_C};font-size:14px;padding:0 12px;outline:none;`;
  cust2EndpointInput.placeholder = '(Opsional) End Point';

  const cust2KeyInput = document.createElement('input');
  cust2KeyInput.className = 'input';
  cust2KeyInput.style.cssText = `background:${FIELD_BG_C};border:none;border-radius:6px;flex:1;height:${INPUT_H_C};font-size:14px;padding:0 12px;outline:none;`;
  cust2KeyInput.placeholder = '(Opsional) API Key';
  cust2KeyInput.type = 'password';

  const cust2TestBtn = document.createElement('button');
  cust2TestBtn.style.cssText = `background:${FIELD_BG_C};border:none;border-radius:6px;padding:0 18px;font-weight:500;font-size:13px;cursor:pointer;height:${INPUT_H_C};white-space:nowrap;color:var(--text);font-family:inherit;flex-shrink:0;`;
  cust2TestBtn.textContent = 'Test';

  custom2InputRow.appendChild(cust2EndpointInput);
  custom2InputRow.appendChild(cust2KeyInput);
  custom2InputRow.appendChild(cust2TestBtn);
  custom2Row.appendChild(custom2InputRow);
  
  const cust2TestStatus = document.createElement('span');
  cust2TestStatus.style.cssText = 'font-size:12px; margin-top:4px; min-height:16px; display:block;';
  custom2Row.appendChild(cust2TestStatus);

  const ytTitle = makeApiField('YT Title Maker', 'Select Model', true);

  apiGrid.appendChild(custom2Row);
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
  
  const replizAccessKey = document.createElement('input');
  replizAccessKey.className = 'input';
  replizAccessKey.style.cssText = 'background:#EAEAEA;color:black;border:none;border-radius:4px;';
  replizAccessKey.placeholder = 'Paste here...';
  
  const replizSecretKey = document.createElement('input');
  replizSecretKey.className = 'input';
  replizSecretKey.style.cssText = 'background:#EAEAEA;color:black;border:none;border-radius:4px;';
  replizSecretKey.placeholder = 'Paste here...';
  replizSecretKey.type = 'password';

  const replizAccessGroup = document.createElement('div');
  replizAccessGroup.className = 'field-group';
  replizAccessGroup.style.margin = '0';
  replizAccessGroup.innerHTML = '<label style="font-size:13px;color:#A1A1AA;margin-bottom:8px;display:block;">Access Key</label>';
  replizAccessGroup.appendChild(replizAccessKey);
  
  const replizSecretGroup = document.createElement('div');
  replizSecretGroup.className = 'field-group';
  replizSecretGroup.style.margin = '0';
  replizSecretGroup.innerHTML = '<label style="font-size:13px;color:#A1A1AA;margin-bottom:8px;display:block;">Secret Key</label>';
  replizSecretGroup.appendChild(replizSecretKey);
  
  replizKeys.appendChild(replizAccessGroup);
  replizKeys.appendChild(replizSecretGroup);
  
  const replizTestBtn = replizHeader.querySelector('button');
  const replizStatus = document.createElement('span');
  replizStatus.style.cssText = 'font-size:12px; margin-top:4px; min-height:16px; display:block; color:white; margin-bottom:12px;';
  
  repliz.appendChild(replizKeys);
  repliz.appendChild(replizStatus);

  const accountsPanel = document.createElement('div');
  accountsPanel.style.cssText = 'flex:1;background:#111810;border-radius:8px;padding:16px;position:relative;overflow:hidden;display:flex;flex-direction:column;';
  
  const accountsTitle = document.createElement('h4');
  accountsTitle.style.cssText = 'color:#A1A1AA;font-size:13px;font-weight:500;margin:0 0 16px;';
  accountsTitle.textContent = 'Loading Accounts...';
  accountsPanel.appendChild(accountsTitle);
  
  const accountsList = document.createElement('div');
  accountsList.style.cssText = 'flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:14px;padding-bottom:60px;';
  accountsPanel.appendChild(accountsList);
  
  const connectMoreDiv = document.createElement('div');
  connectMoreDiv.style.cssText = 'position:absolute;bottom:0;left:0;right:0;padding:12px 16px;background:linear-gradient(to top, #111810 55%, transparent);';
  connectMoreDiv.innerHTML = '<button class="btn btn-lime-full" style="font-weight:600;font-size:13px;" onclick="window.open(\'https://dashboard.repliz.com\', \'_blank\')">Connect More</button>';
  accountsPanel.appendChild(connectMoreDiv);
  repliz.appendChild(accountsPanel);

  mainGrid.appendChild(apiCard);
  mainGrid.appendChild(repliz);
  section.appendChild(mainGrid);

  // ── Watermark Settings Panel ──
  const wmPanel = document.createElement('div');
  wmPanel.className = 'card';
  wmPanel.style.cssText = 'margin-top:24px; display:flex; flex-direction:column; gap:16px;';

  const wmHeader = document.createElement('div');
  wmHeader.className = 'card-header';
  wmHeader.innerHTML = `<h2 class="card-title">Watermark Settings</h2>`;
  wmPanel.appendChild(wmHeader);

  // Enable Toggle
  const wmEnableRow = document.createElement('div');
  wmEnableRow.style.cssText = 'display:flex; align-items:center; gap:8px;';
  const wmEnableCheck = document.createElement('input');
  wmEnableCheck.type = 'checkbox';
  wmEnableCheck.id = 'wm-enable';
  const wmEnableLabel = document.createElement('label');
  wmEnableLabel.htmlFor = 'wm-enable';
  wmEnableLabel.textContent = 'Enable Watermark';
  wmEnableLabel.style.cssText = 'font-size:14px; font-weight:500; cursor:pointer;';
  wmEnableRow.appendChild(wmEnableCheck);
  wmEnableRow.appendChild(wmEnableLabel);
  wmPanel.appendChild(wmEnableRow);

  // Image Selection
  const wmImageRow = document.createElement('div');
  wmImageRow.style.cssText = 'display:flex; gap:8px; align-items:center;';
  const wmImagePath = document.createElement('input');
  wmImagePath.className = 'input';
  wmImagePath.style.cssText = 'flex:1; background:#EDEDE9; border:none; border-radius:6px; height:40px; padding:0 12px; font-size:14px;';
  wmImagePath.placeholder = 'Select PNG image...';
  wmImagePath.readOnly = true;
  const wmBrowseBtn = document.createElement('button');
  wmBrowseBtn.className = 'btn btn-outline';
  wmBrowseBtn.style.cssText = 'height:40px;';
  wmBrowseBtn.textContent = 'Browse';
  wmImageRow.appendChild(wmImagePath);
  wmImageRow.appendChild(wmBrowseBtn);
  wmPanel.appendChild(wmImageRow);

  // Sliders container
  const wmSliders = document.createElement('div');
  wmSliders.style.cssText = 'display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:8px;';

  function createSlider(label, min, max, step, defaultValue) {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex; flex-direction:column; gap:8px;';
    
    const topRow = document.createElement('div');
    topRow.style.cssText = 'display:flex; justify-content:space-between; align-items:center; font-size:13px; font-weight:500;';
    const titleSpan = document.createElement('span');
    titleSpan.textContent = label;
    const valSpan = document.createElement('span');
    valSpan.textContent = defaultValue;
    valSpan.style.color = 'var(--text-muted)';
    topRow.appendChild(titleSpan);
    topRow.appendChild(valSpan);
    
    const input = document.createElement('input');
    input.type = 'range';
    input.min = min;
    input.max = max;
    input.step = step;
    input.value = defaultValue;
    input.style.width = '100%';
    
    input.addEventListener('input', () => {
      valSpan.textContent = input.value;
    });
    
    wrap.appendChild(topRow);
    wrap.appendChild(input);
    return { wrap, input, valSpan };
  }

  const wmPosX = createSlider('Position X (0-1)', '0', '1', '0.01', '0.85');
  const wmPosY = createSlider('Position Y (0-1)', '0', '1', '0.01', '0.05');
  const wmOpacity = createSlider('Opacity (0-1)', '0', '1', '0.05', '0.8');
  const wmScale = createSlider('Scale (0.05-0.5)', '0.05', '0.5', '0.01', '0.15');

  wmSliders.appendChild(wmPosX.wrap);
  wmSliders.appendChild(wmPosY.wrap);
  wmSliders.appendChild(wmOpacity.wrap);
  wmSliders.appendChild(wmScale.wrap);
  wmPanel.appendChild(wmSliders);
  
  section.appendChild(wmPanel);

  // ── Credit Watermark Settings Panel ──
  const cwPanel = document.createElement('div');
  cwPanel.className = 'card';
  cwPanel.style.cssText = 'margin-top:24px; display:flex; flex-direction:column; gap:16px;';

  const cwHeader = document.createElement('div');
  cwHeader.className = 'card-header';
  cwHeader.innerHTML = `<h2 class="card-title">Credit Watermark</h2>
  <p style="font-size:12px; color:var(--text-muted); margin-top:4px; margin-bottom:0;">Automatically adds channel name as credit text on generated clips</p>`;
  cwPanel.appendChild(cwHeader);

  // Enable Toggle
  const cwEnableRow = document.createElement('div');
  cwEnableRow.style.cssText = 'display:flex; align-items:center; gap:8px;';
  const cwEnableCheck = document.createElement('input');
  cwEnableCheck.type = 'checkbox';
  cwEnableCheck.id = 'cw-enable';
  const cwEnableLabel = document.createElement('label');
  cwEnableLabel.htmlFor = 'cw-enable';
  cwEnableLabel.textContent = 'Enable Credit Watermark';
  cwEnableLabel.style.cssText = 'font-size:14px; font-weight:500; cursor:pointer;';
  cwEnableRow.appendChild(cwEnableCheck);
  cwEnableRow.appendChild(cwEnableLabel);
  cwPanel.appendChild(cwEnableRow);

  // Sliders container
  const cwSliders = document.createElement('div');
  cwSliders.style.cssText = 'display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:8px;';

  const cwPosX = createSlider('Position X (0-1)', '0', '1', '0.01', '0.5');
  const cwPosY = createSlider('Position Y (0-1)', '0', '1', '0.01', '0.95');
  const cwSize = createSlider('Text Size (0.02-0.08)', '0.02', '0.08', '0.01', '0.03');
  const cwOpacity = createSlider('Opacity (0.1-1.0)', '0.1', '1.0', '0.05', '0.7');

  cwSliders.appendChild(cwPosX.wrap);
  cwSliders.appendChild(cwPosY.wrap);
  cwSliders.appendChild(cwSize.wrap);
  cwSliders.appendChild(cwOpacity.wrap);
  cwPanel.appendChild(cwSliders);
  
  section.appendChild(cwPanel);

  // ── Hook Style Settings Panel ──
  const hsPanel = document.createElement('div');
  hsPanel.className = 'card';
  hsPanel.style.cssText = 'margin-top:24px; display:flex; flex-direction:column; gap:16px;';

  const hsHeader = document.createElement('div');
  hsHeader.className = 'card-header';
  hsHeader.innerHTML = `<h2 class="card-title">Hook Style</h2>
  <p style="font-size:12px; color:var(--text-muted); margin-top:4px; margin-bottom:0;">Customize the look of the opening hook scene</p>`;
  hsPanel.appendChild(hsHeader);

  // Colors and Font Row
  const hsRow1 = document.createElement('div');
  hsRow1.style.cssText = 'display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px;';
  
  // Font Dropdown
  const hsFontWrap = document.createElement('div');
  hsFontWrap.style.cssText = 'display:flex; flex-direction:column; gap:6px;';
  hsFontWrap.innerHTML = '<span style="font-size:13px; font-weight:500;">Font Family</span>';
  const hsFontSelect = document.createElement('select');
  hsFontSelect.className = 'input';
  hsFontSelect.style.cssText = 'background:#EDEDE9; border:none; border-radius:6px; height:36px; padding:0 8px; font-size:13px;';
  hsFontWrap.appendChild(hsFontSelect);
  hsRow1.appendChild(hsFontWrap);

  // Font Color
  const hsFontColorWrap = document.createElement('div');
  hsFontColorWrap.style.cssText = 'display:flex; flex-direction:column; gap:6px;';
  hsFontColorWrap.innerHTML = '<span style="font-size:13px; font-weight:500;">Font Color</span>';
  const hsFontColor = document.createElement('input');
  hsFontColor.type = 'color';
  hsFontColor.value = '#FFD700';
  hsFontColor.style.cssText = 'height:36px; width:100%; border:none; border-radius:6px; background:none; cursor:pointer;';
  hsFontColorWrap.appendChild(hsFontColor);
  hsRow1.appendChild(hsFontColorWrap);

  // BG Color
  const hsBgColorWrap = document.createElement('div');
  hsBgColorWrap.style.cssText = 'display:flex; flex-direction:column; gap:6px;';
  hsBgColorWrap.innerHTML = '<span style="font-size:13px; font-weight:500;">Background Color</span>';
  const hsBgColor = document.createElement('input');
  hsBgColor.type = 'color';
  hsBgColor.value = '#FFFFFF';
  hsBgColor.style.cssText = 'height:36px; width:100%; border:none; border-radius:6px; background:none; cursor:pointer;';
  hsBgColorWrap.appendChild(hsBgColor);
  hsRow1.appendChild(hsBgColorWrap);

  hsPanel.appendChild(hsRow1);

  // Sliders container
  const hsSliders = document.createElement('div');
  hsSliders.style.cssText = 'display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:8px;';

  const hsFontSize = createSlider('Font Size', '0.025', '0.10', '0.001', '0.054');
  const hsCorner = createSlider('Corner Radius (px)', '0', '80', '1', '0');
  const hsPosX = createSlider('Position X (0-1)', '0', '1', '0.01', '0.5');
  const hsPosY = createSlider('Position Y (0-1)', '0', '1', '0.01', '0.33');

  hsSliders.appendChild(hsFontSize.wrap);
  hsSliders.appendChild(hsCorner.wrap);
  hsSliders.appendChild(hsPosX.wrap);
  hsSliders.appendChild(hsPosY.wrap);
  hsPanel.appendChild(hsSliders);
  
  section.appendChild(hsPanel);

  // ── Face Tracking + GPU Acceleration Panel ──
  const ftPanel = document.createElement('div');
  ftPanel.className = 'card';
  ftPanel.style.cssText = 'margin-top:24px; display:flex; flex-direction:column; gap:16px;';

  const ftHeader = document.createElement('div');
  ftHeader.className = 'card-header';
  ftHeader.innerHTML = `<h2 class="card-title">Face Tracking & Performance</h2>
  <p style="font-size:12px; color:var(--text-muted); margin-top:4px; margin-bottom:0;">Choose how the video crops to speakers and GPU acceleration</p>`;
  ftPanel.appendChild(ftHeader);

  // Face Tracking Mode
  const ftModeLabel = document.createElement('span');
  ftModeLabel.style.cssText = 'font-size:13px; font-weight:500;';
  ftModeLabel.textContent = 'Face Tracking Mode';
  ftPanel.appendChild(ftModeLabel);

  const ftRadioWrap = document.createElement('div');
  ftRadioWrap.style.cssText = 'display:flex; flex-direction:column; gap:10px;';

  // OpenCV option
  const ftOpencvRow = document.createElement('label');
  ftOpencvRow.style.cssText = 'display:flex; align-items:flex-start; gap:8px; padding:12px; background:var(--bg-tertiary, #f5f5f0); border-radius:8px; cursor:pointer;';
  const ftOpencvRadio = document.createElement('input');
  ftOpencvRadio.type = 'radio';
  ftOpencvRadio.name = 'ft-mode';
  ftOpencvRadio.value = 'opencv';
  ftOpencvRadio.checked = true;
  ftOpencvRadio.style.marginTop = '3px';
  const ftOpencvText = document.createElement('div');
  ftOpencvText.innerHTML = '<strong>OpenCV (Fast)</strong><br><span style="font-size:11px; color:var(--text-muted);">Crop to largest face. Faster processing. Recommended for most users.</span>';
  ftOpencvRow.appendChild(ftOpencvRadio);
  ftOpencvRow.appendChild(ftOpencvText);
  ftRadioWrap.appendChild(ftOpencvRow);

  // MediaPipe option
  const ftMediapipeRow = document.createElement('label');
  ftMediapipeRow.style.cssText = 'display:flex; align-items:flex-start; gap:8px; padding:12px; background:var(--bg-tertiary, #f5f5f0); border-radius:8px; cursor:pointer;';
  const ftMediapipeRadio = document.createElement('input');
  ftMediapipeRadio.type = 'radio';
  ftMediapipeRadio.name = 'ft-mode';
  ftMediapipeRadio.value = 'mediapipe';
  ftMediapipeRadio.style.marginTop = '3px';
  const ftMediapipeText = document.createElement('div');
  ftMediapipeText.innerHTML = '<strong>MediaPipe (Smart)</strong><br><span style="font-size:11px; color:var(--text-muted);">Crop to active speaker (lip movement). More accurate. ⚠ Slower (2-3x).</span>';
  ftMediapipeRow.appendChild(ftMediapipeRadio);
  ftMediapipeRow.appendChild(ftMediapipeText);
  ftRadioWrap.appendChild(ftMediapipeRow);

  ftPanel.appendChild(ftRadioWrap);

  // GPU Acceleration
  const gaSubHeader = document.createElement('span');
  gaSubHeader.style.cssText = 'font-size:13px; font-weight:500; margin-top:8px;';
  gaSubHeader.textContent = 'GPU Acceleration';
  ftPanel.appendChild(gaSubHeader);

  const gaEnableRow = document.createElement('div');
  gaEnableRow.style.cssText = 'display:flex; align-items:center; gap:8px;';
  const gaEnableCheck = document.createElement('input');
  gaEnableCheck.type = 'checkbox';
  gaEnableCheck.id = 'ga-enable';
  const gaEnableLabel = document.createElement('label');
  gaEnableLabel.htmlFor = 'ga-enable';
  gaEnableLabel.textContent = 'Enable GPU Acceleration';
  gaEnableLabel.style.cssText = 'font-size:14px; font-weight:500; cursor:pointer;';
  gaEnableRow.appendChild(gaEnableCheck);
  gaEnableRow.appendChild(gaEnableLabel);
  ftPanel.appendChild(gaEnableRow);

  const gaNote = document.createElement('p');
  gaNote.style.cssText = 'font-size:11px; color:var(--text-muted); margin:0;';
  gaNote.textContent = 'GPU encoding is 3-5x faster than CPU. Requires compatible hardware.';
  ftPanel.appendChild(gaNote);

  // GPU Status display
  const gaStatusBox = document.createElement('div');
  gaStatusBox.style.cssText = 'background:var(--bg-tertiary, #f5f5f0); border-radius:8px; padding:12px; font-size:12px; color:var(--text-muted); min-height:40px;';
  gaStatusBox.textContent = 'Click "Detect GPU" to check hardware.';
  ftPanel.appendChild(gaStatusBox);

  const gaDetectBtn = document.createElement('button');
  gaDetectBtn.className = 'btn';
  gaDetectBtn.style.cssText = 'background:#3B8ED0; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-size:13px;';
  gaDetectBtn.textContent = '🔄 Detect GPU';
  gaDetectBtn.addEventListener('click', async () => {
      gaDetectBtn.disabled = true;
      gaDetectBtn.textContent = 'Detecting...';
      try {
          const res = await window.pywebview.api.detect_gpu();
          if (res && res.status === 'ok') {
              const gpu = res.gpu;
              const rec = res.recommendation;
              if (gpu.available) {
                  const emoji = {nvidia: '🟢', amd: '🔴', intel: '🔵', apple: '⚪'};
                  let txt = (emoji[gpu.type] || '⚪') + ' GPU: ' + gpu.name + '\n';
                  txt += 'Type: ' + (gpu.type || 'unknown').toUpperCase() + '\n';
                  if (rec.available) {
                      txt += 'Encoder: ' + rec.encoder + '\nPreset: ' + (rec.preset || 'N/A') + '\n✓ Ready to use';
                  } else {
                      txt += 'Encoder not available: ' + (rec.reason || 'Unknown');
                  }
                  gaStatusBox.textContent = txt;
                  gaStatusBox.style.color = 'green';
              } else {
                  gaStatusBox.textContent = '⚪ No GPU detected. Using CPU encoding (libx264).';
                  gaStatusBox.style.color = 'var(--text-muted)';
                  gaEnableCheck.checked = false;
              }
          } else {
              gaStatusBox.textContent = '❌ Detection error: ' + (res.message || 'Unknown');
              gaStatusBox.style.color = 'red';
          }
      } catch(e) {
          gaStatusBox.textContent = '❌ Detection failed: ' + e;
          gaStatusBox.style.color = 'red';
      }
      gaDetectBtn.disabled = false;
      gaDetectBtn.textContent = '🔄 Detect GPU';
  });
  ftPanel.appendChild(gaDetectBtn);

  section.appendChild(ftPanel);

  // ── Output Directory Panel ──
  const odPanel = document.createElement('div');
  odPanel.className = 'card';
  odPanel.style.cssText = 'margin-top:24px; display:flex; flex-direction:column; gap:12px;';

  const odHeader = document.createElement('div');
  odHeader.className = 'card-header';
  odHeader.innerHTML = `<h2 class="card-title">Output Folder</h2>
  <p style="font-size:12px; color:var(--text-muted); margin-top:4px; margin-bottom:0;">Folder where video clips will be saved</p>`;
  odPanel.appendChild(odHeader);

  const odPathRow = document.createElement('div');
  odPathRow.style.cssText = 'display:flex; gap:8px; align-items:center;';

  const odPath = document.createElement('input');
  odPath.type = 'text';
  odPath.className = 'input';
  odPath.readOnly = true;
  odPath.placeholder = 'Select output folder...';
  odPath.style.cssText = 'flex:1; height:36px; background:#EDEDE9; border:none; border-radius:6px; padding:0 12px; font-size:13px;';
  odPathRow.appendChild(odPath);

  const odBrowseBtn = document.createElement('button');
  odBrowseBtn.className = 'btn';
  odBrowseBtn.textContent = 'Browse';
  odBrowseBtn.style.cssText = 'padding:8px 16px; border-radius:6px; font-size:13px; cursor:pointer; background:#EDEDE9; border:none;';
  odBrowseBtn.addEventListener('click', async () => {
      odBrowseBtn.disabled = true;
      odBrowseBtn.textContent = '...';
      try {
          const res = await window.pywebview.api.browse_output_dir();
          if (res && res.status === 'ok') {
              odPath.value = res.path;
          }
      } catch(e) {}
      odBrowseBtn.textContent = 'Browse';
      odBrowseBtn.disabled = false;
  });
  odPathRow.appendChild(odBrowseBtn);
  odPanel.appendChild(odPathRow);

  const odOpenBtn = document.createElement('button');
  odOpenBtn.className = 'btn';
  odOpenBtn.style.cssText = 'background:#6c757d; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-size:13px;';
  odOpenBtn.textContent = '📂 Open Output Folder';
  odOpenBtn.addEventListener('click', async () => {
      try {
          const res = await window.pywebview.api.open_output_dir();
          if (res && res.status === 'error') {
              alert(res.message);
          }
      } catch(e) {}
  });
  odPanel.appendChild(odOpenBtn);

  section.appendChild(odPanel);

  // ── YouTube API Panel ──
  const ytPanel = document.createElement('div');
  ytPanel.className = 'card';
  ytPanel.style.cssText = 'margin-top:24px; display:flex; flex-direction:column; gap:12px;';

  const ytHeader = document.createElement('div');
  ytHeader.className = 'card-header';
  ytHeader.innerHTML = `<h2 class="card-title">YouTube API</h2>`;
  ytPanel.appendChild(ytHeader);

  // Status box
  const ytStatusBox = document.createElement('div');
  ytStatusBox.style.cssText = 'background:var(--bg-tertiary, #f5f5f0); border-radius:8px; padding:12px; font-size:12px; color:var(--text-muted); min-height:40px; white-space:pre-line;';
  ytStatusBox.textContent = 'Checking YouTube connection...';
  ytPanel.appendChild(ytStatusBox);

  // Buttons row
  const ytBtnRow = document.createElement('div');
  ytBtnRow.style.cssText = 'display:flex; gap:8px;';

  const ytConnectBtn = document.createElement('button');
  ytConnectBtn.className = 'btn';
  ytConnectBtn.style.cssText = 'background:#c4302b; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-size:13px; flex:1;';
  ytConnectBtn.textContent = 'Connect YouTube';

  const ytDisconnectBtn = document.createElement('button');
  ytDisconnectBtn.className = 'btn';
  ytDisconnectBtn.style.cssText = 'background:#6c757d; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-size:13px; display:none;';
  ytDisconnectBtn.textContent = 'Disconnect';

  ytBtnRow.appendChild(ytConnectBtn);
  ytBtnRow.appendChild(ytDisconnectBtn);
  ytPanel.appendChild(ytBtnRow);

  // Setup instructions
  const ytInfo = document.createElement('div');
  ytInfo.style.cssText = 'font-size:11px; color:var(--text-muted); line-height:1.5;';
  ytInfo.innerHTML = `<strong>Setup:</strong> 1. Set up Google Cloud project. 2. Enable YouTube Data API v3. 3. Create OAuth credentials. 4. Place <code>client_secret.json</code> in app folder.`;
  ytPanel.appendChild(ytInfo);

  // Connect handler
  ytConnectBtn.addEventListener('click', async () => {
      ytConnectBtn.disabled = true;
      ytConnectBtn.textContent = 'Connecting...';
      ytStatusBox.textContent = 'Opening browser for YouTube authorization...';
      ytStatusBox.style.color = 'var(--text-muted)';
      try {
          const res = await window.pywebview.api.connect_youtube();
          if (res && res.status === 'connected') {
              const ch = res.channel || {};
              ytStatusBox.textContent = '✅ Connected\nChannel: ' + (ch.title || 'Unknown');
              ytStatusBox.style.color = 'green';
              ytConnectBtn.style.display = 'none';
              ytDisconnectBtn.style.display = 'block';
          } else {
              ytStatusBox.textContent = '❌ Connection failed: ' + (res.message || 'Unknown error');
              ytStatusBox.style.color = 'red';
          }
      } catch(e) {
          ytStatusBox.textContent = '❌ Connection failed: ' + e;
          ytStatusBox.style.color = 'red';
      }
      ytConnectBtn.disabled = false;
      ytConnectBtn.textContent = 'Connect YouTube';
  });

  // Disconnect handler
  ytDisconnectBtn.addEventListener('click', async () => {
      if (!confirm('Are you sure you want to disconnect YouTube?')) return;
      ytDisconnectBtn.disabled = true;
      try {
          const res = await window.pywebview.api.disconnect_youtube();
          if (res && res.status === 'ok') {
              ytStatusBox.textContent = 'Not connected. Click Connect to authorize.';
              ytStatusBox.style.color = 'var(--text-muted)';
              ytConnectBtn.style.display = 'block';
              ytDisconnectBtn.style.display = 'none';
          } else {
              ytStatusBox.textContent = '❌ Disconnect failed: ' + (res.message || 'Unknown');
              ytStatusBox.style.color = 'red';
          }
      } catch(e) {}
      ytDisconnectBtn.disabled = false;
  });

  // Auto-check status on load
  (async () => {
      try {
          const res = await window.pywebview.api.get_youtube_status();
          if (!res) return;
          if (res.status === 'connected') {
              const ch = res.channel || {};
              ytStatusBox.textContent = '✅ Connected\nChannel: ' + (ch.title || 'Unknown');
              ytStatusBox.style.color = 'green';
              ytConnectBtn.style.display = 'none';
              ytDisconnectBtn.style.display = 'block';
          } else if (res.status === 'not_configured') {
              ytStatusBox.textContent = '⚠ client_secret.json not found in app folder';
              ytStatusBox.style.color = 'orange';
              ytConnectBtn.disabled = true;
          } else if (res.status === 'not_connected') {
              ytStatusBox.textContent = 'Not connected. Click Connect to authorize.';
              ytStatusBox.style.color = 'var(--text-muted)';
          } else if (res.status === 'auth_error') {
              ytStatusBox.textContent = '⚠ Auth error: ' + (res.message || 'Try reconnecting');
              ytStatusBox.style.color = 'orange';
              ytDisconnectBtn.style.display = 'block';
          } else if (res.status === 'module_error') {
              ytStatusBox.textContent = '⚠ ' + (res.message || 'YouTube module not available');
              ytStatusBox.style.color = 'orange';
              ytConnectBtn.disabled = true;
          } else {
              ytStatusBox.textContent = '❌ Error: ' + (res.message || 'Unknown');
              ytStatusBox.style.color = 'red';
          }
      } catch(e) {
          ytStatusBox.textContent = 'Could not check YouTube status.';
      }
  })();

  section.appendChild(ytPanel);

  // Browse logic
  wmBrowseBtn.addEventListener('click', async () => {
      wmBrowseBtn.textContent = '...';
      wmBrowseBtn.disabled = true;
      try {
          const res = await window.pywebview.api.browse_watermark_image();
          if (res && res.status === 'ok') {
              wmImagePath.value = res.path;
          } else if (res && res.status === 'error') {
              alert('Error: ' + res.message);
          }
      } catch(e) {}
      wmBrowseBtn.textContent = 'Browse';
      wmBrowseBtn.disabled = false;
  });

  // Save button
  const saveRow = document.createElement('div');
  saveRow.style.marginTop = '24px';
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
  cmUrlInput.value = 'https://api.anthropic.com/v1';
  const hmUrlInput = document.createElement('input');
  hmUrlInput.type = 'hidden';
  hmUrlInput.value = 'https://generativelanguage.googleapis.com/v1beta/openai/';

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

  const reloadBtn = apiHeader.querySelector('#reload-model-btn');

  return {
    element: section,
    fields: {
      providerButtons: [],
      whisperModel: whisperModelSelect,
      reloadModelBtn: reloadBtn,
      hfUrl: hfUrlInput,
      hfUrlField: hfUrlField,
      hfKey: openai.input,
      hfEye: hfEye,
      hfModel: hfModel.input,
      hfModelTestBtn: hfModel.testBtn,
      hfModelStatus: hfModel.status,
      hfValidateBtn: openai.testBtn,
      hfValidateStatus: openai.status,
      cmUrl: cust1EndpointInput,
      cmUrlField: cmUrlField,
      cmKey: cust1KeyInput,
      cmEye: cmEye,
      cmModel: cmModel.input,
      cmModelTestBtn: cmModel.testBtn,
      cmModelStatus: cmModel.status,
      cmValidateBtn: cust1TestBtn,
      cmValidateStatus: cust1TestStatus,
      hmUrl: hmUrlInput,
      hmUrlField: hmUrlField,
      hmKey: gemini.input,
      hmEye: hmEye,
      hmModel: hmModel.input,
      hmModelTestBtn: hmModel.testBtn,
      hmModelStatus: hmModel.status,
      hmValidateBtn: gemini.testBtn,
      hmValidateStatus: gemini.status,
      cpUrl: cust2EndpointInput,
      cpKey: cust2KeyInput,
      cpValidateBtn: cust2TestBtn,
      cpValidateStatus: cust2TestStatus,
      ytModel: ytTitle.input,
      ytModelTestBtn: ytTitle.testBtn,
      ytModelStatus: ytTitle.status,
      replizAccessKey: replizAccessKey,
      replizSecretKey: replizSecretKey,
      replizTestBtn: replizTestBtn,
      replizStatus: replizStatus,
      accountsTitle: accountsTitle,
      accountsList: accountsList,
      wmEnableCheck: wmEnableCheck,
      wmImagePath: wmImagePath,
      wmPosX: wmPosX.input,
      wmPosY: wmPosY.input,
      wmOpacity: wmOpacity.input,
      wmScale: wmScale.input,
      cwEnableCheck: cwEnableCheck,
      cwPosX: cwPosX.input,
      cwPosY: cwPosY.input,
      cwSize: cwSize.input,
      cwOpacity: cwOpacity.input,
      hsFontSelect: hsFontSelect,
      hsFontColor: hsFontColor,
      hsBgColor: hsBgColor,
      hsFontSize: hsFontSize.input,
      hsCorner: hsCorner.input,
      hsPosX: hsPosX.input,
      hsPosY: hsPosY.input,
      ftOpencvRadio: ftOpencvRadio,
      ftMediapipeRadio: ftMediapipeRadio,
      gaEnableCheck: gaEnableCheck,
      odPath: odPath,
      ytStatusBox: ytStatusBox,
      ytConnectBtn: ytConnectBtn,
      ytDisconnectBtn: ytDisconnectBtn,
      saveBtn: saveBtn,
      status: saveStatus,
    }
  };
};
