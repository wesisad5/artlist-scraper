/* Artlist Catalog Explorer UI */

const API = {
  base: '',
  async get(path) {
    const r = await fetch(this.base + path);
    if (!r.ok) throw new Error(`${r.status} ${path}`);
    return r.json();
  },
  async getCatalogFile(name) {
    const r = await fetch(this.base + `/data/catalog/${name}.json`);
    if (!r.ok) return null;
    return r.json();
  },
  async getAIFile(name) {
    const r = await fetch(this.base + `/data/ai/${name}.json`);
    if (!r.ok) return null;
    return r.json();
  },
  async getMeta(name) {
    const r = await fetch(this.base + `/data/_meta/${name}.json`);
    if (!r.ok) return null;
    return r.json();
  },
};

// CDN headers (we need to add Origin/Referer for cms-public-artifacts.artlist.io permlinks)
// But browser fetch can't set Origin/Referer — they're forbidden headers.
// Workaround: use a CORS proxy or our own /api/cdn-proxy endpoint.
// For now, the imgix URLs are CORS-friendly (no Origin check).
// The cms-public-artifacts URLs may fail in browser due to CORS — we'll handle that.

// State
const state = {
  currentTab: 'overview',
  catalogData: {},  // name -> data
  aiData: {},       // name -> data
  meta: null,
  searchQuery: '',
  page: 1,
  pageSize: 60,
  filters: {},
};

// =============== Init ===============
document.addEventListener('DOMContentLoaded', init);

async function init() {
  // Wire up tabs
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
  document.getElementById('refresh-btn').addEventListener('click', () => {
    state.catalogData = {};
    state.aiData = {};
    state.meta = null;
    render();
  });
  document.getElementById('global-search').addEventListener('input', (e) => {
    state.searchQuery = e.target.value.toLowerCase();
    if (state.currentTab !== 'overview') renderTab(state.currentTab);
  });

  // Load meta
  try {
    state.meta = await API.getMeta('latest.json');
    const aiMeta = await API.getMeta('ai_latest.json');
    state.aiMeta = aiMeta;
  } catch (e) {
    console.warn('meta load failed', e);
  }

  await switchTab('overview');
}

async function switchTab(tab) {
  state.currentTab = tab;
  state.page = 1;
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  await renderTab(tab);
}

async function renderTab(tab) {
  const main = document.getElementById('main');
  main.innerHTML = '<div class="loading-overlay"><div class="spinner"></div><p>Loading...</p></div>';

  try {
    switch (tab) {
      case 'overview': await renderOverview(); break;
      case 'music': await renderMusic(); break;
      case 'sfx': await renderSfx(); break;
      case 'footage': await renderFootage(); break;
      case 'luts': await renderLuts(); break;
      case 'templates': await renderTemplates(); break;
      case 'collections': await renderCollections(); break;
      case 'flows': await renderFlows(); break;
      case 'studio': await renderStudio(); break;
      case 'audit': await renderAudit(); break;
    }
    renderFooter();
  } catch (e) {
    main.innerHTML = `<div class="empty-state"><h3>Error</h3><p>${e.message}</p></div>`;
    console.error(e);
  }
}

function renderFooter() {
  const runEl = document.getElementById('last-run');
  const countsEl = document.getElementById('item-counts');
  if (state.meta) {
    runEl.textContent = `Last catalog run: ${state.meta.run_id} (${state.meta.finished_at || '...'})`;
  } else {
    runEl.textContent = 'No run metadata';
  }
  const counts = [];
  for (const [k, v] of Object.entries(state.meta?.totals || {})) {
    counts.push(`${k}: ${v}`);
  }
  countsEl.textContent = counts.join('  |  ');
}

// =============== Overview ===============
async function renderOverview() {
  const main = document.getElementById('main');
  const m = state.meta || {};
  const am = state.aiMeta || {};
  const steps = m.steps || {};
  const aiSteps = am.steps || {};

  const cards = [];
  const tabLabels = {
    music: 'Music', sfx: 'SFX', footage: 'Footage', luts: 'LUTs',
    templates: 'Templates', collections: 'Collections',
  };
  for (const [key, label] of Object.entries(tabLabels)) {
    const total = m.totals?.[key === 'footage' ? 'footage_clips' : key] || 0;
    const status = steps[key]?.status || 'pending';
    const cls = status === 'ok' ? 'ok' : (status === 'failed' ? 'fail' : 'warn');
    cards.push(`
      <div class="stat-card" data-jump="${key}">
        <h3>${label}</h3>
        <div class="big-num">${formatNum(total)}</div>
        <div class="sub ${cls}">${status.toUpperCase()}${steps[key]?.duration_sec ? ` · ${steps[key].duration_sec}s` : ''}</div>
      </div>
    `);
  }
  cards.push(`
    <div class="stat-card" data-jump="flows">
      <h3>Flow AI Templates</h3>
      <div class="big-num">${formatNum(am.totals?.flow_templates || 0)}</div>
      <div class="sub ${aiSteps.flows?.status === 'ok' ? 'ok' : 'fail'}">${(aiSteps.flows?.status || 'pending').toUpperCase()}</div>
    </div>
    <div class="stat-card" data-jump="studio">
      <h3>Studio AI Spotlight</h3>
      <div class="big-num">${formatNum(am.totals?.studio_spotlight || 0)}</div>
      <div class="sub ${aiSteps.studio?.status === 'ok' ? 'ok' : 'fail'}">${(aiSteps.studio?.status || 'pending').toUpperCase()}</div>
    </div>
  `);

  main.innerHTML = `
    <div class="section">
      <div class="section-header"><h2>Catalog Overview</h2></div>
      <div class="overview-grid">${cards.join('')}</div>
    </div>
    <div class="section">
      <div class="section-header"><h2>Run History</h2></div>
      <div class="table-wrap"><table>
        <thead><tr><th>Run ID</th><th>Started</th><th>Finished</th><th>Steps</th></tr></thead>
        <tbody>
          <tr><td>${m.run_id || '-'}</td><td>${m.started_at || '-'}</td><td>${m.finished_at || '-'}</td>
              <td>${Object.entries(steps).map(([k,v]) => `${k}:${v.status}`).join(', ')}</td></tr>
          <tr><td>${am.run_id || '-'}</td><td>${am.started_at || '-'}</td><td>${am.finished_at || '-'}</td>
              <td>${Object.entries(aiSteps).map(([k,v]) => `${k}:${v.status}`).join(', ')}</td></tr>
        </tbody>
      </table></div>
    </div>
  `;

  main.querySelectorAll('[data-jump]').forEach(el => {
    el.style.cursor = 'pointer';
    el.addEventListener('click', () => switchTab(el.dataset.jump));
  });
}

// =============== Music ===============
async function loadCatalog(name) {
  if (state.catalogData[name]) return state.catalogData[name];
  const data = await API.getCatalogFile(name);
  state.catalogData[name] = data;
  return data;
}

async function renderMusic() {
  const data = await loadCatalog('music');
  if (!data) return renderEmpty('Music data not yet scraped.');
  const songs = data.songs || [];
  const filtered = filterItems(songs, ['songName', 'artistName', 'albumName']);
  renderAudioGrid(filtered, 'songName', 'artistName', 'sitePlayableFilePath', 'albumImageFilePath', 'duration', 'songId');
}

async function renderSfx() {
  const data = await loadCatalog('sfx');
  if (!data) return renderEmpty('SFX data not yet scraped.');
  const items = data.items || [];
  const filtered = filterItems(items, ['songName', 'artistName', 'albumName']);
  renderAudioGrid(filtered, 'songName', 'artistName', 'sitePlayableFilePath', 'albumImageFilePath', 'durationTime', 'songId');
}

function renderAudioGrid(items, titleKey, subKey, audioKey, imageKey, durationKey, idKey) {
  const main = document.getElementById('main');
  const total = items.length;
  const start = (state.page - 1) * state.pageSize;
  const pageItems = items.slice(start, start + state.pageSize);

  const cards = pageItems.map(item => {
    const tpl = document.getElementById('tpl-audio-card').content.cloneNode(true);
    const img = tpl.querySelector('img');
    const imgSrc = item[imageKey];
    if (imgSrc) {
      img.src = imgSrc;
      img.classList.add('lazy-load');
      img.addEventListener('load', () => img.classList.add('loaded'));
    } else {
      img.style.display = 'none';
    }
    tpl.querySelector('.card-title').textContent = item[titleKey] || '(unnamed)';
    tpl.querySelector('.card-sub').textContent = item[subKey] || '';
    const meta = tpl.querySelector('.card-meta');
    const duration = item[durationKey];
    const id = item[idKey];
    meta.innerHTML = `<span class="tag">ID: ${id}</span>${duration ? `<span class="tag">⏱ ${duration}</span>` : ''}`;
    // Audio URL classification
    const audioUrl = item[audioKey];
    if (audioUrl) {
      const cls = classifyUrl(audioUrl);
      meta.innerHTML += `<span class="tag ${cls}">${cls}</span>`;
      // Set audio src (may fail CORS — handled below)
      const audio = tpl.querySelector('.audio-player');
      const playBtn = tpl.querySelector('.play-btn');
      playBtn.addEventListener('click', () => {
        if (!audio.src) {
          audio.src = audioUrl;
        }
        if (audio.paused) {
          audio.play().catch(err => {
            // If CORS fails, open in new tab
            window.open(audioUrl, '_blank');
          });
          playBtn.textContent = '⏸ Pause';
        } else {
          audio.pause();
          playBtn.textContent = '▶ Play';
        }
      });
      audio.addEventListener('play', () => playBtn.textContent = '⏸ Pause');
      audio.addEventListener('pause', () => playBtn.textContent = '▶ Play');
      const dl = tpl.querySelector('.dl-btn');
      dl.href = audioUrl;
    } else {
      tpl.querySelector('.play-btn').disabled = true;
      tpl.querySelector('.dl-btn').style.display = 'none';
    }
    // Click to open detail modal
    tpl.querySelector('.card-title').style.cursor = 'pointer';
    tpl.querySelector('.card-title').addEventListener('click', () => showDetail(item));
    return tpl;
  });

  main.innerHTML = `
    <div class="section">
      <div class="section-header">
        <h2>${state.currentTab.charAt(0).toUpperCase() + state.currentTab.slice(1)} (${formatNum(total)})</h2>
      </div>
      <div class="cards-grid" id="cards-grid"></div>
      ${renderPagination(state.page, Math.ceil(total / state.pageSize), total)}
    </div>
  `;
  const grid = document.getElementById('cards-grid');
  cards.forEach(c => grid.appendChild(c));
  attachPaginationHandlers((p) => { state.page = p; renderTab(state.currentTab); });
}

// =============== Footage ===============
async function renderFootage() {
  const data = await loadCatalog('footage');
  if (!data) return renderEmpty('Footage data not yet scraped (large catalog, runs separately).');
  const clips = data.clips || [];
  const filtered = filterItems(clips, ['clipName', 'filmMakerDisplayName', 'storyName']);
  renderVideoGrid(filtered, 'clipName', 'filmMakerDisplayName', 'thumbnailUrl', 'clipPath', 'id', 'orientation', 'duration');
}

function renderVideoGrid(items, titleKey, subKey, thumbKey, videoKey, idKey, ...metaKeys) {
  const main = document.getElementById('main');
  const total = items.length;
  const start = (state.page - 1) * state.pageSize;
  const pageItems = items.slice(start, start + state.pageSize);

  const cards = pageItems.map(item => {
    const tpl = document.getElementById('tpl-video-card').content.cloneNode(true);
    const img = tpl.querySelector('img');
    const thumb = item[thumbKey];
    if (thumb) {
      img.src = thumb;
      img.classList.add('lazy-load');
      img.addEventListener('load', () => img.classList.add('loaded'));
    }
    tpl.querySelector('.card-title').textContent = item[titleKey] || '(unnamed)';
    tpl.querySelector('.card-sub').textContent = item[subKey] || '';
    const meta = tpl.querySelector('.card-meta');
    let metaHtml = `<span class="tag">ID: ${item[idKey]}</span>`;
    for (const mk of metaKeys) {
      if (item[mk] != null) {
        let v = item[mk];
        if (mk === 'duration') v = formatDuration(v);
        metaHtml += `<span class="tag">${mk}: ${v}</span>`;
      }
    }
    const videoUrl = item[videoKey];
    if (videoUrl) {
      const cls = classifyUrl(videoUrl);
      metaHtml += `<span class="tag ${cls}">${cls}</span>`;
    }
    meta.innerHTML = metaHtml;
    // HLS player
    const watchBtn = tpl.querySelector('.watch-btn');
    if (videoUrl && videoUrl.endsWith('.m3u8')) {
      watchBtn.href = videoUrl;
      watchBtn.addEventListener('click', (e) => {
        e.preventDefault();
        openHlsPlayer(videoUrl, item[titleKey]);
      });
    } else if (videoUrl) {
      watchBtn.href = videoUrl;
    } else {
      watchBtn.style.display = 'none';
    }
    const dl = tpl.querySelector('.dl-btn');
    if (videoUrl) dl.href = videoUrl;
    else dl.style.display = 'none';
    tpl.querySelector('.card-title').style.cursor = 'pointer';
    tpl.querySelector('.card-title').addEventListener('click', () => showDetail(item));
    return tpl;
  });

  main.innerHTML = `
    <div class="section">
      <div class="section-header">
        <h2>${state.currentTab.charAt(0).toUpperCase() + state.currentTag?.slice(1) || state.currentTab} (${formatNum(total)})</h2>
      </div>
      <div class="cards-grid" id="cards-grid"></div>
      ${renderPagination(state.page, Math.ceil(total / state.pageSize), total)}
    </div>
  `;
  const grid = document.getElementById('cards-grid');
  cards.forEach(c => grid.appendChild(c));
  attachPaginationHandlers((p) => { state.page = p; renderTab(state.currentTab); });
}

// =============== LUTs / Templates ===============
async function renderLuts() {
  const data = await loadCatalog('luts');
  if (!data) return renderEmpty('LUTs data not yet scraped.');
  const items = data.luts || [];
  const filtered = filterItems(items, ['name', 'videoCategoryName', 'moodCategoryName']);
  renderSimpleGrid(filtered, 'name', 'videoCategoryName', 'thumbnailUrl', 'hlsUrl', 'id', ['moodCategoryName', 'contrast', 'saturation', 'temperature']);
}

async function renderTemplates() {
  const data = await loadCatalog('templates');
  if (!data) return renderEmpty('Templates data not yet scraped.');
  const items = data.templates || [];
  const filtered = filterItems(items, ['name', 'artistName']);
  renderSimpleGrid(filtered, 'name', 'artistName', 'thumbnailUrl', 'previewVideoFileUrl', 'id', ['resolutions', 'availableFormats']);
}

function renderSimpleGrid(items, titleKey, subKey, thumbKey, videoKey, idKey, metaKeys) {
  const main = document.getElementById('main');
  const total = items.length;
  const start = (state.page - 1) * state.pageSize;
  const pageItems = items.slice(start, start + state.pageSize);

  const cards = pageItems.map(item => {
    const tpl = document.getElementById('tpl-video-card').content.cloneNode(true);
    const img = tpl.querySelector('img');
    const thumb = item[thumbKey];
    if (thumb) {
      img.src = thumb;
      img.classList.add('lazy-load');
      img.addEventListener('load', () => img.classList.add('loaded'));
    }
    tpl.querySelector('.card-title').textContent = item[titleKey] || '(unnamed)';
    tpl.querySelector('.card-sub').textContent = item[subKey] || '';
    const meta = tpl.querySelector('.card-meta');
    let metaHtml = `<span class="tag">ID: ${item[idKey]}</span>`;
    for (const mk of metaKeys) {
      const v = item[mk];
      if (v != null && v !== '' && (!Array.isArray(v) || v.length)) {
        metaHtml += `<span class="tag">${mk}: ${Array.isArray(v) ? v.join(',') : v}</span>`;
      }
    }
    const videoUrl = item[videoKey];
    if (videoUrl) {
      const cls = classifyUrl(videoUrl);
      metaHtml += `<span class="tag ${cls}">${cls}</span>`;
    }
    meta.innerHTML = metaHtml;
    const watchBtn = tpl.querySelector('.watch-btn');
    if (videoUrl && videoUrl.endsWith('.m3u8')) {
      watchBtn.href = videoUrl;
      watchBtn.addEventListener('click', (e) => {
        e.preventDefault();
        openHlsPlayer(videoUrl, item[titleKey]);
      });
    } else if (videoUrl) {
      watchBtn.href = videoUrl;
    } else {
      watchBtn.style.display = 'none';
    }
    const dl = tpl.querySelector('.dl-btn');
    if (videoUrl) dl.href = videoUrl;
    else dl.style.display = 'none';
    tpl.querySelector('.card-title').style.cursor = 'pointer';
    tpl.querySelector('.card-title').addEventListener('click', () => showDetail(item));
    return tpl;
  });

  main.innerHTML = `
    <div class="section">
      <div class="section-header"><h2>${state.currentTab.charAt(0).toUpperCase() + state.currentTab.slice(1)} (${formatNum(total)})</h2></div>
      <div class="cards-grid" id="cards-grid"></div>
      ${renderPagination(state.page, Math.ceil(total / state.pageSize), total)}
    </div>
  `;
  const grid = document.getElementById('cards-grid');
  cards.forEach(c => grid.appendChild(c));
  attachPaginationHandlers((p) => { state.page = p; renderTab(state.currentTab); });
}

// =============== Collections ===============
async function renderCollections() {
  const data = await loadCatalog('collections');
  if (!data) return renderEmpty('Collections data not yet scraped.');
  const items = data.collections || [];
  if (!items.length) return renderEmpty('No collections found (user may not have any).');
  // Render as table
  const main = document.getElementById('main');
  const rows = items.map(c => `<tr>
    <td>${c.id || '-'}</td>
    <td>${c.name || c.title || '-'}</td>
    <td>${c.itemCount || c.assetsCount || '-'}</td>
    <td>${c.updatedAt || c.lastUpdated || '-'}</td>
    <td><button data-detail='${JSON.stringify(c).replace(/'/g, "&#39;")}'>View</button></td>
  </tr>`).join('');
  main.innerHTML = `
    <div class="section">
      <div class="section-header"><h2>Collections (${items.length})</h2></div>
      <div class="table-wrap"><table>
        <thead><tr><th>ID</th><th>Name</th><th>Items</th><th>Updated</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
    </div>
  `;
  main.querySelectorAll('[data-detail]').forEach(btn => {
    btn.addEventListener('click', () => showDetail(JSON.parse(btn.dataset.detail)));
  });
}

// =============== Flow AI ===============
async function renderFlows() {
  const data = state.aiData.flows || await API.getAIFile('flows');
  state.aiData.flows = data;
  if (!data) return renderEmpty('Flow AI data not yet scraped.');

  const main = document.getElementById('main');
  const templates = data.templates || [];
  const nodes = data.catalog?.nodes || [];
  const userFlows = data.user_flows?.flows || [];

  const templateCards = templates.map(t => {
    const thumb = t.thumbnailUrl;
    const cls = thumb ? classifyUrl(thumb) : '';
    const cfg = t.full_config || {};
    const nodeCount = (cfg.flowConfig?.nodes || []).length;
    return `
      <article class="card" data-detail='${JSON.stringify(t).replace(/'/g, "&#39;")}'>
        <div class="card-thumb" style="background-image: url('${thumb || ''}')"></div>
        <div class="card-body">
          <h3 class="card-title">${t.name || '(unnamed)'}</h3>
          <p class="card-sub">${t.description || ''}</p>
          <div class="card-meta">
            <span class="tag">ID: ${t.id}</span>
            <span class="tag">Nodes: ${nodeCount}</span>
            ${thumb ? `<span class="tag ${cls}">${cls}</span>` : ''}
          </div>
        </div>
      </article>`;
  }).join('');

  const nodeCards = nodes.map(n => `
    <div class="flow-node type-${n.nodeType || 'util'}">
      <strong>${n.slug}</strong>
      <div style="font-size: 10px; color: var(--text-faint)">${n.nodeType} / ${n.outputType || '?'}</div>
    </div>
  `).join('');

  const userFlowCards = userFlows.map(f => `
    <article class="card" data-detail='${JSON.stringify(f).replace(/'/g, "&#39;")}'>
      <div class="card-body">
        <h3 class="card-title">${f.name || '(unnamed)'}</h3>
        <p class="card-sub">Updated: ${f.updatedAt || '?'}</p>
        <div class="card-meta"><span class="tag">ID: ${f.id}</span></div>
      </div>
    </article>
  `).join('');

  main.innerHTML = `
    <div class="section">
      <div class="section-header"><h2>Flow AI Templates (${templates.length})</h2></div>
      <p style="color: var(--text-dim); margin-bottom: 12px;">Pre-built example flows from Artlist's Flow/Canvas AI tool.</p>
      <div class="cards-grid">${templateCards}</div>
    </div>
    <div class="section">
      <div class="section-header"><h2>Available Node Types (${nodes.length})</h2></div>
      <div>${nodeCards}</div>
    </div>
    <div class="section">
      <div class="section-header"><h2>User Flows (${userFlows.length})</h2></div>
      <div class="cards-grid">${userFlowCards || '<p class="empty-state">No user flows.</p>'}</div>
    </div>
  `;

  main.querySelectorAll('[data-detail]').forEach(el => {
    el.style.cursor = 'pointer';
    el.addEventListener('click', () => showDetail(JSON.parse(el.dataset.detail)));
  });
}

// =============== Studio AI ===============
async function renderStudio() {
  const data = state.aiData.studio || await API.getAIFile('studio');
  state.aiData.studio = data;
  if (!data) return renderEmpty('Studio AI data not yet scraped.');

  const main = document.getElementById('main');
  const spotlight = data.spotlight_projects || [];
  const userProjects = data.user_projects || [];
  const locations = data.predefined?.predefined_locations?.data || [];
  const props = data.predefined?.predefined_props?.data || [];

  const spotlightCards = spotlight.map(p => {
    const img = p.previewImageUrl;
    const cls = img ? classifyUrl(img) : '';
    const charCount = (p.characters || []).length;
    return `
      <article class="card" data-detail='${JSON.stringify(p).replace(/'/g, "&#39;")}'>
        <div class="card-thumb">${img ? `<img loading="lazy" src="${img}" />` : ''}</div>
        <div class="card-body">
          <h3 class="card-title">${p.name || '(unnamed)'}</h3>
          <p class="card-sub">Type: ${p.type || '-'}  ·  ${p.shotCount || 0} shots</p>
          <div class="card-meta">
            <span class="tag">ID: ${p.id}</span>
            <span class="tag">Chars: ${charCount}</span>
            ${img ? `<span class="tag ${cls}">${cls}</span>` : ''}
          </div>
        </div>
      </article>`;
  }).join('');

  const locCards = locations.slice(0, 50).map(l => `
    <article class="card" data-detail='${JSON.stringify(l).replace(/'/g, "&#39;")}'>
      <div class="card-thumb">${l.previewImageUrl ? `<img loading="lazy" src="${l.previewImageUrl}" />` : ''}</div>
      <div class="card-body">
        <h3 class="card-title">${l.name || '(unnamed)'}</h3>
        <p class="card-sub">${l.description || l.category || ''}</p>
      </div>
    </article>
  `).join('');

  const propCards = props.slice(0, 50).map(p => `
    <article class="card" data-detail='${JSON.stringify(p).replace(/'/g, "&#39;")}'>
      <div class="card-thumb">${p.previewImageUrl ? `<img loading="lazy" src="${p.previewImageUrl}" />` : ''}</div>
      <div class="card-body">
        <h3 class="card-title">${p.name || '(unnamed)'}</h3>
        <p class="card-sub">${p.description || p.category || ''}</p>
      </div>
    </article>
  `).join('');

  main.innerHTML = `
    <div class="section">
      <div class="section-header"><h2>Studio AI Spotlight Projects (${spotlight.length})</h2></div>
      <p style="color: var(--text-dim); margin-bottom: 12px;">Public example projects from Artlist's Studio AI tool.</p>
      <div class="cards-grid">${spotlightCards || '<p class="empty-state">No spotlight projects.</p>'}</div>
    </div>
    <div class="section">
      <div class="section-header"><h2>Predefined Locations (${locations.length})</h2></div>
      <div class="cards-grid">${locCards}</div>
    </div>
    <div class="section">
      <div class="section-header"><h2>Predefined Props (${props.length})</h2></div>
      <div class="cards-grid">${propCards}</div>
    </div>
    <div class="section">
      <div class="section-header"><h2>User Projects (${userProjects.length})</h2></div>
      <div class="cards-grid">${userProjects.length ? '' : '<p class="empty-state">No user projects.</p>'}</div>
    </div>
  `;

  main.querySelectorAll('[data-detail]').forEach(el => {
    el.style.cursor = 'pointer';
    el.addEventListener('click', () => showDetail(JSON.parse(el.dataset.detail)));
  });
}

// =============== Audit ===============
async function renderAudit() {
  const main = document.getElementById('main');
  main.innerHTML = '<div class="loading-overlay"><div class="spinner"></div><p>Running audit...</p></div>';

  // Run audit by fetching files and checking
  const checks = [];

  // File existence checks
  const files = [
    ['catalog/music.json', 'Music catalog'],
    ['catalog/sfx.json', 'SFX catalog'],
    ['catalog/footage.json', 'Footage catalog'],
    ['catalog/luts.json', 'LUTs catalog'],
    ['catalog/templates.json', 'Templates catalog'],
    ['catalog/collections.json', 'Collections catalog'],
    ['catalog/categories.json', 'Categories'],
    ['catalog/search_terms.json', 'Search terms'],
    ['ai/flows.json', 'Flow AI'],
    ['ai/studio.json', 'Studio AI'],
    ['_meta/latest.json', 'Catalog run meta'],
    ['_meta/ai_latest.json', 'AI run meta'],
  ];

  for (const [path, label] of files) {
    const r = await fetch(`/data/${path}`).catch(() => ({ ok: false, status: 0 }));
    const ok = r.ok;
    const size = ok ? r.headers.get('content-length') || '?' : '0';
    checks.push({ label, path, ok, size });
  }

  const sections = checks.map(c => {
    const status = c.ok ? '<span class="ok">✓ OK</span>' : '<span class="fail">✗ MISSING</span>';
    return `<li><strong>${c.label}</strong> (<code>/data/${c.path}</code>) — ${status} ${c.ok ? `(${c.size} bytes)` : ''}</li>`;
  }).join('');

  main.innerHTML = `
    <div class="section">
      <div class="section-header"><h2>Data File Audit</h2></div>
      <div class="audit-section">
        <h3>File Existence Checks</h3>
        <ul>${sections}</ul>
      </div>
    </div>
    <div class="section">
      <div class="section-header"><h2>Run Metadata</h2></div>
      <div class="audit-section">
        <h3>Catalog Latest Run</h3>
        <pre>${JSON.stringify(state.meta || {}, null, 2)}</pre>
      </div>
      <div class="audit-section">
        <h3>AI Latest Run</h3>
        <pre>${JSON.stringify(state.aiMeta || {}, null, 2)}</pre>
      </div>
    </div>
  `;
}

// =============== Helpers ===============
function formatNum(n) {
  if (!n && n !== 0) return '?';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'k';
  return n.toString();
}

function formatDuration(ms) {
  if (!ms) return '?';
  const s = ms / 1000;
  if (s < 60) return s.toFixed(1) + 's';
  const m = Math.floor(s / 60);
  const rs = Math.floor(s % 60);
  return `${m}:${rs.toString().padStart(2, '0')}`;
}

function filterItems(items, searchFields) {
  if (!state.searchQuery) return items;
  return items.filter(item => {
    return searchFields.some(f => {
      const v = item[f];
      return v && String(v).toLowerCase().includes(state.searchQuery);
    });
  });
}

function classifyUrl(url) {
  if (!url) return 'permlink';
  if (url.includes('Expires=') && url.includes('Signature=')) return 'signed';
  if (url.includes('artlist-studio-proxy.imgix.net')) return 'proxy';
  return 'permlink';
}

function renderEmpty(msg) {
  document.getElementById('main').innerHTML = `
    <div class="empty-state"><h3>Nothing here yet</h3><p>${msg}</p></div>
  `;
}

function renderPagination(page, totalPages, total) {
  if (totalPages <= 1) return '';
  return `
    <div class="pagination">
      <button data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>← Prev</button>
      <span class="page-info">Page ${page} of ${totalPages} (${formatNum(total)} items)</span>
      <button data-page="${page + 1}" ${page >= totalPages ? 'disabled' : ''}>Next →</button>
    </div>
  `;
}

function attachPaginationHandlers(cb) {
  document.querySelectorAll('.pagination button[data-page]').forEach(btn => {
    btn.addEventListener('click', () => {
      const p = parseInt(btn.dataset.page);
      if (p > 0) {
        state.page = p;
        cb(p);
      }
    });
  });
}

function showDetail(obj) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h3>${obj.songName || obj.name || obj.clipName || 'Detail'}</h3>
        <button onclick="this.closest('.modal-overlay').remove()">✕</button>
      </div>
      <div class="modal-body">
        <pre>${JSON.stringify(obj, null, 2)}</pre>
      </div>
    </div>
  `;
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.remove();
  });
  document.body.appendChild(overlay);
}

function openHlsPlayer(url, title) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal" style="max-width: 800px;">
      <div class="modal-header">
        <h3>${title || 'HLS Player'}</h3>
        <button onclick="this.closest('.modal-overlay').remove()">✕</button>
      </div>
      <div class="modal-body">
        <video id="hls-video" controls autoplay style="width: 100%; max-height: 60vh;"></video>
        <p style="margin-top: 8px; font-size: 12px; color: var(--text-dim);">URL: <a href="${url}" target="_blank">${url}</a></p>
      </div>
    </div>
  `;
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.remove();
  });
  document.body.appendChild(overlay);
  const video = overlay.querySelector('#hls-video');
  if (window.Hls && Hls.isSupported()) {
    const hls = new Hls();
    hls.loadSource(url);
    hls.attachMedia(video);
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = url;
  } else {
    video.replaceWith(`<p>HLS not supported. <a href="${url}" target="_blank">Open URL</a></p>`);
  }
}
