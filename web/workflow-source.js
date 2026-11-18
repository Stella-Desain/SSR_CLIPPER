(() => {
  const fields = homeView.fields;
  let selectionVersion = 0;
  window.addEventListener('workflow-sources-dropped', event => {
    if (fields.url.disabled) return;
    const paths = Array.isArray(event.detail) ? event.detail : [];
    if (paths.length) {
      fields.url.value = [fields.url.value.trim(), ...paths].filter(Boolean).join('\n');
      fields.sourceFeedback.textContent = '';
    } else {
      fields.sourceFeedback.textContent = 'File belum terbaca. Gunakan tombol Pilih MP4 lokal.';
    }
  });

  const tools = document.createElement('div');
  tools.className = 'wf-source-actions';
  const browse = document.createElement('button');
  browse.className = 'btn btn-outline';
  browse.type = 'button';
  browse.textContent = 'Pilih MP4 lokal';
  tools.appendChild(browse);
  fields.sourceActions.appendChild(tools);
  browse.onclick = async () => {
    if (fields.url.disabled) return;
    browse.disabled = true;
    try {
      const result = await window.pywebview.api.browse_source_video();
      if (result.status === 'ok' && !fields.url.disabled) {
        fields.url.value = [fields.url.value.trim(), result.path].filter(Boolean).join('\n');
        fields.sourceFeedback.textContent = '';
      } else if (result.status === 'error') {
        fields.sourceFeedback.textContent = result.message || 'Video belum dapat dipilih.';
      }
    } catch (error) {
      fields.sourceFeedback.textContent = String(error);
    } finally {
      browse.disabled = fields.url.disabled;
    }
  };

  const summary = document.createElement('p');
  summary.className = 'wf-campaign-summary';
  summary.id = 'create-campaign-summary';
  summary.setAttribute('role', 'status');
  fields.campaign.setAttribute('aria-describedby', summary.id);
  fields.campaign.parentElement.appendChild(summary);
  fields.campaign.addEventListener('change', async () => {
    const version = ++selectionVersion;
    if (!fields.campaign.value) {
      summary.textContent = '';
      return;
    }
    summary.textContent = 'Memuat template campaign…';
    try {
      const result = await window.pywebview.api.get_campaign_workspace(fields.campaign.value);
      if (version !== selectionVersion) return;
      if (result.status !== 'ok') throw Error(result.message || 'Campaign belum dapat dimuat.');
      const blockers = result.readiness?.production_blockers || [];
      const editing = result.campaign?.editing || {};
      const templateName = editing.preset_name || (editing.preset_id === 'standard' || !editing.preset_id ? 'Standar' : editing.preset_id);
      const pool=(editing.template_pool || []).filter(item=>item.enabled);
      summary.textContent = [editing.selection_mode==='weighted_random'?`Template acak per clip · ${pool.length} template aktif`:'Template '+templateName, ...blockers].join('\n');
    } catch (error) {
      if (version === selectionVersion) summary.textContent = String(error);
    }
  });
})();
