/* ═══════════════════════════════════════
   Clipper - App Shell
   ═══════════════════════════════════════ */

const root = document.getElementById('app');
const shell = document.createElement('div');
shell.className = 'shell';
root.appendChild(shell);

// ── Build Shell: Sidebar + Main ──
const shellComp = window.Components.Shell();
shell.appendChild(shellComp.sidebar);

const mainWrapper = document.createElement('div');
mainWrapper.className = 'main-wrapper';
mainWrapper.appendChild(shellComp.topHeader);

const pageContent = document.createElement('div');
pageContent.className = 'page-content';
mainWrapper.appendChild(pageContent);
shell.appendChild(mainWrapper);

// ── Build Views ──
const dashboardView = window.Components.DashboardView();
const homeView = window.Components.HomeView();
const stockClipView = window.Components.StockClipView();
const aiView = window.Components.AiSettingsView();

pageContent.appendChild(dashboardView.element);
pageContent.appendChild(homeView.element);
pageContent.appendChild(stockClipView.element);
pageContent.appendChild(aiView.element);

const allViews = [dashboardView.element, homeView.element, stockClipView.element, aiView.element];
const navItems = shellComp.navItems;

// ── State ──
let polling = null;
let providerType = 'ytclip';

// ── Navigation ──
function setActiveView(name) {
  allViews.forEach(v => v.classList.toggle('active', v.dataset.view === name));
  navItems.forEach(n => n.classList.toggle('active', n.dataset.view === name));
  // Scroll to top
  pageContent.scrollTop = 0;
  
  // Refresh data if view has a refresh method
  if (name === 'dashboard' && dashboardView.refresh) dashboardView.refresh();
  if (name === 'stock-clip' && stockClipView.refresh) stockClipView.refresh();
}

navItems.forEach(item => {
  item.addEventListener('click', () => {
    const view = item.dataset.view;
    if (view === 'credit') return; // Not implemented yet
    setActiveView(view);
  });
});

// ── API Helpers ──
function waitForApi() {
  return new Promise((resolve) => {
    if (window.pywebview && window.pywebview.api) {
      resolve();
      return;
    }
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (window.pywebview && window.pywebview.api) {
        clearInterval(timer);
        resolve();
      } else if (tries > 50) {
        clearInterval(timer);
        resolve();
      }
    }, 100);
  });
}

// ── Provider Management ──
function setProviderType(type, applyBaseUrl) {
  providerType = type;
  aiView.fields.providerButtons.forEach(btn => {
    const isActive = btn.dataset.provider === type;
    btn.style.background = isActive ? 'var(--lime)' : 'var(--card)';
    btn.style.color = isActive ? 'var(--text-on-lime)' : 'var(--text)';
    btn.style.borderColor = isActive ? 'var(--lime)' : 'var(--border)';
    btn.style.fontWeight = isActive ? '700' : '500';
  });

  const showCustom = type === 'custom';
  document.querySelectorAll('.url-field').forEach(el => {
    el.classList.toggle('hidden', !showCustom);
  });

  if (applyBaseUrl && !showCustom) {
    const baseUrl = type === 'ytclip' ? 'https://ai-api.ytclip.org/v1' : 'https://api.openai.com/v1';
    aiView.fields.hfUrl.value = baseUrl;
    aiView.fields.cmUrl.value = baseUrl;
    aiView.fields.hmUrl.value = baseUrl;
  }
}

function setSelectOptions(select, models, preferred) {
  select.innerHTML = '';
  if (!models || models.length === 0) {
    const opt = document.createElement('option');
    opt.value = preferred || '';
    opt.textContent = preferred || 'No models';
    select.appendChild(opt);
    return;
  }
  models.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m;
    select.appendChild(opt);
  });
  if (preferred && models.includes(preferred)) {
    select.value = preferred;
  }
}

// ── Processing Controls ──
function lockControls(state) {
  homeView.fields.url.disabled = state;
  homeView.fields.clips.disabled = state;
  homeView.fields.subtitle.disabled = state;
  homeView.fields.captions.disabled = state;
  homeView.fields.hook.disabled = state;
  homeView.fields.start.disabled = state;
  if (state) {
    homeView.fields.start.style.opacity = '0.5';
    homeView.fields.start.style.cursor = 'not-allowed';
  } else {
    homeView.fields.start.style.opacity = '1';
    homeView.fields.start.style.cursor = 'pointer';
  }
}

function updateStepStatus(status) {
  const statusLower = (status || '').toLowerCase();

  function setStep(el, cls, text) {
    const span = el.querySelector('.step-status');
    if (span) {
      span.className = 'step-status ' + cls;
      span.textContent = text;
    }
  }

  if (statusLower.includes('download')) {
    setStep(homeView.fields.stepDownload, 'ongoing', 'Ongoing');
  } else if (statusLower.includes('highlight') || statusLower.includes('finding')) {
    setStep(homeView.fields.stepDownload, 'complete', 'Complete');
    setStep(homeView.fields.stepHighlight, 'ongoing', 'Ongoing');
  } else if (statusLower.includes('edit') || statusLower.includes('process') || statusLower.includes('portrait') || statusLower.includes('caption') || statusLower.includes('hook')) {
    setStep(homeView.fields.stepDownload, 'complete', 'Complete');
    setStep(homeView.fields.stepHighlight, 'complete', 'Complete');
    setStep(homeView.fields.stepEditing, 'ongoing', 'Ongoing');
  } else if (statusLower.includes('export') || statusLower.includes('saving') || statusLower.includes('complete')) {
    setStep(homeView.fields.stepDownload, 'complete', 'Complete');
    setStep(homeView.fields.stepHighlight, 'complete', 'Complete');
    setStep(homeView.fields.stepEditing, 'complete', 'Complete');
    setStep(homeView.fields.stepExport, statusLower === 'complete' ? 'complete' : 'ongoing', statusLower === 'complete' ? 'Complete' : 'Ongoing');
  } else if (statusLower.startsWith('error')) {
    setStep(homeView.fields.stepExport, 'failed', 'Failed');
  }
}

async function start() {
  const url = homeView.fields.url.value.trim();
  if (!url) return;
  lockControls(true);
  homeView.fields.status.textContent = 'Starting...';
  homeView.fields.terminal.textContent = 'Starting clip creation...\n';
  homeView.fields.bar.style.width = '0%';

  try {
    const res = await window.pywebview.api.start_processing(
      url,
      parseInt(homeView.fields.clips.value, 10),
      homeView.fields.captions.checked,
      homeView.fields.hook.checked,
      homeView.fields.subtitle.value
    );
    if (res && res.status === 'started') {
      poll();
      polling = setInterval(poll, 500);
    } else {
      homeView.fields.status.textContent = 'Busy - another process is running';
      lockControls(false);
    }
  } catch (e) {
    homeView.fields.status.textContent = 'Error: ' + e;
    lockControls(false);
  }
}

async function poll() {
  try {
    const p = await window.pywebview.api.get_progress();
    const pr = Math.max(0, Math.min(1, p.progress || 0));
    homeView.fields.bar.style.width = (pr * 100).toFixed(1) + '%';
    homeView.fields.status.textContent = p.status || '';
    homeView.fields.terminal.textContent += (p.status || '') + '\n';
    homeView.fields.terminal.scrollTop = homeView.fields.terminal.scrollHeight;

    updateStepStatus(p.status);

    if (p.status && (p.status.startsWith('error') || p.status === 'complete')) {
      clearInterval(polling);
      polling = null;
      lockControls(false);
    }
  } catch {
    clearInterval(polling);
    polling = null;
    lockControls(false);
  }
}

homeView.fields.start.addEventListener('click', start);

// ── Save AI Settings ──
aiView.fields.saveBtn.addEventListener('click', async () => {
  const payload = {
    _provider_type: providerType,
    highlight_finder: {
      base_url: aiView.fields.hfUrl.value.trim(),
      api_key: aiView.fields.hfKey.value.trim(),
      model: aiView.fields.hfModel.value.trim()
    },
    caption_maker: {
      base_url: aiView.fields.cmUrl.value.trim(),
      api_key: aiView.fields.cmKey.value.trim(),
      model: aiView.fields.cmModel.value.trim()
    },
    hook_maker: {
      base_url: aiView.fields.hmUrl.value.trim(),
      api_key: aiView.fields.hmKey.value.trim(),
      model: aiView.fields.hmModel.value.trim()
    }
  };
  aiView.fields.status.textContent = 'Saving...';
  try {
    const res = await window.pywebview.api.save_ai_settings(payload);
    aiView.fields.status.textContent = res && res.status === 'saved' ? '✓ Saved successfully' : 'Error saving';
  } catch {
    aiView.fields.status.textContent = 'Error saving settings';
  }
});

// ── Provider Button Listeners ──
aiView.fields.providerButtons.forEach(btn => {
  btn.addEventListener('click', () => setProviderType(btn.dataset.provider, true));
});

// ── Validate & Load Models ──
async function validateAndLoad(kind) {
  const baseUrl = kind.url.value.trim();
  const apiKey = kind.key.value.trim();
  kind.status.textContent = 'Validating...';
  const res = await window.pywebview.api.validate_api_key(baseUrl, apiKey);
  if (!res || res.status !== 'ok') {
    kind.status.textContent = res && res.message ? res.message : 'Invalid';
    kind.status.style.color = 'var(--error)';
    return;
  }
  kind.status.textContent = 'Loading models...';
  kind.status.style.color = 'var(--text-muted)';
  const modelsRes = await window.pywebview.api.get_models(baseUrl, apiKey);
  const models = (modelsRes && modelsRes.models) || [];
  setSelectOptions(kind.model, models, kind.model.value);
  kind.status.textContent = models.length ? '✓ Valid' : '✓ Valid, no models';
  kind.status.style.color = 'var(--success)';
}

aiView.fields.hfValidateBtn.addEventListener('click', () => validateAndLoad({
  url: aiView.fields.hfUrl,
  key: aiView.fields.hfKey,
  model: aiView.fields.hfModel,
  status: aiView.fields.hfValidateStatus
}));

aiView.fields.cmValidateBtn.addEventListener('click', () => validateAndLoad({
  url: aiView.fields.cmUrl,
  key: aiView.fields.cmKey,
  model: aiView.fields.cmModel,
  status: aiView.fields.cmValidateStatus
}));

aiView.fields.hmValidateBtn.addEventListener('click', () => validateAndLoad({
  url: aiView.fields.hmUrl,
  key: aiView.fields.hmKey,
  model: aiView.fields.hmModel,
  status: aiView.fields.hmValidateStatus
}));

// ── Init ──
async function init() {
  await waitForApi();

  // Load AI settings
  try {
    const ai = await window.pywebview.api.get_ai_settings();
    const hf = ai.highlight_finder || {};
    const cm = ai.caption_maker || {};
    const hm = ai.hook_maker || {};
    aiView.fields.hfUrl.value = hf.base_url || '';
    aiView.fields.hfKey.value = hf.api_key || '';
    setSelectOptions(aiView.fields.hfModel, [hf.model].filter(Boolean), hf.model || '');
    aiView.fields.cmUrl.value = cm.base_url || '';
    aiView.fields.cmKey.value = cm.api_key || '';
    setSelectOptions(aiView.fields.cmModel, [cm.model].filter(Boolean), cm.model || '');
    aiView.fields.hmUrl.value = hm.base_url || '';
    aiView.fields.hmKey.value = hm.api_key || '';
    setSelectOptions(aiView.fields.hmModel, [hm.model].filter(Boolean), hm.model || '');
  } catch {}

  // Load provider type
  try {
    const provider = await window.pywebview.api.get_provider_type();
    providerType = provider.provider_type || 'ytclip';
  } catch {}

  setProviderType(providerType, true);
  setActiveView('dashboard');
}

window.addEventListener('pywebviewready', init);
setTimeout(() => init(), 800);
