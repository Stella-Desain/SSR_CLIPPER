window.Components = window.Components || {};

window.Components.CampaignListView = function () {
  const section = document.createElement('section');
  section.className = 'view entrance';
  section.dataset.view = 'campaign';

  const headerRow = document.createElement('div');
  headerRow.style.cssText = 'display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:28px;flex-wrap:wrap;gap:16px;';
  
  const headerLeft = document.createElement('div');
  headerLeft.innerHTML = `
    <h1 class="page-title">Campaigns</h1>
    <p class="page-subtitle" style="margin-bottom:0;">Manage and edit your video campaigns.</p>
  `;
  
  const headerRight = document.createElement('div');
  const createBtn = document.createElement('button');
  createBtn.className = 'btn btn-lime';
  createBtn.textContent = 'Create Campaign';
  headerRight.appendChild(createBtn);

  headerRow.appendChild(headerLeft);
  headerRow.appendChild(headerRight);
  section.appendChild(headerRow);

  const grid = document.createElement('div');
  grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill, minmax(300px, 1fr));gap:20px;';
  section.appendChild(grid);

  return {
    element: section,
    fields: {
      grid,
      createBtn
    }
  };
};
