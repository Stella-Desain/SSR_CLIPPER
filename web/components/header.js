window.Components = window.Components || {};

window.Components.Shell = function () {
  // ── Sidebar ──
  const sidebar = document.createElement('aside');
  sidebar.className = 'sidebar';

  // Logo
  const logo = document.createElement('div');
  logo.className = 'sidebar-logo';
  logo.innerHTML = `
    <div class="sidebar-logo-icon">
      <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round">
        <path d="m3 21 1.9-5.7a8.5 8.5 0 1 1 3.8 3.8z"></path>
        <path d="M8.5 14.5 12 11l-2-2-3.5 3.5"></path>
      </svg>
    </div>
    <span class="sidebar-logo-text">Clipper</span>
  `;
  sidebar.appendChild(logo);

  // Nav
  const nav = document.createElement('nav');
  nav.className = 'sidebar-nav';

  const menuItems = [
    { id: 'dashboard', icon: 'dashboard', label: 'Dashboard' },
    { id: 'create-clip', icon: 'create-clip', label: 'Create Clip' },
    { id: 'stock-clip', icon: 'stock-clip', label: 'Stock Clip' },
  ];

  const generalItems = [
    { id: 'settings', icon: 'settings', label: 'Settings' },
    { id: 'credit', icon: 'credit', label: 'Credit' },
  ];

  function svgIcon(type) {
    const icons = {
      'dashboard': '<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><rect height="9" rx="1" width="7" x="3" y="3"></rect><rect height="5" rx="1" width="7" x="14" y="3"></rect><rect height="9" rx="1" width="7" x="14" y="12"></rect><rect height="5" rx="1" width="7" x="3" y="16"></rect></svg>',
      'create-clip': '<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><rect height="18" rx="2" width="18" x="3" y="3"></rect><path d="M15 3v18"></path><path d="M3 15h12"></path><path d="m9 9 3 3-3 3"></path></svg>',
      'stock-clip': '<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path></svg>',
      'settings': '<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path><circle cx="12" cy="12" r="3"></circle></svg>',
      'credit': '<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>',
    };
    return icons[type] || '';
  }

  function createNavGroup(label, items) {
    const group = document.createElement('div');
    group.className = 'sidebar-nav-group';

    const sectionLabel = document.createElement('div');
    sectionLabel.className = 'sidebar-section-label';
    sectionLabel.textContent = label;
    group.appendChild(sectionLabel);

    items.forEach(item => {
      const a = document.createElement('div');
      a.className = 'nav-item';
      a.dataset.view = item.id;
      a.innerHTML = svgIcon(item.icon) + `<span>${item.label}</span>`;
      group.appendChild(a);
    });

    return group;
  }

  nav.appendChild(createNavGroup('MENU', menuItems));
  nav.appendChild(createNavGroup('GENERAL', generalItems));
  sidebar.appendChild(nav);

  // ── Top Header ──
  const topHeader = document.createElement('header');
  topHeader.className = 'top-header';
  topHeader.innerHTML = `
    <div class="top-header-left">
      <span class="top-header-user">Bintang SSR</span>
    </div>
    <div class="top-header-search">
      <div class="search-wrapper">
        <div class="search-icon">
          <svg fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"></path></svg>
        </div>
        <input class="search-input" type="text" placeholder="Search anything...">
      </div>
    </div>
    <div class="top-header-actions">
      <button class="header-icon-btn">
        <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"></path><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"></path><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"></path></svg>
      </button>
      <button class="header-icon-btn">
        <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"></path><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"></path></svg>
        <span class="notification-dot"></span>
      </button>
    </div>
  `;

  // Collect nav items for wiring
  const navItems = sidebar.querySelectorAll('.nav-item');

  return {
    sidebar,
    topHeader,
    navItems: Array.from(navItems),
  };
};
