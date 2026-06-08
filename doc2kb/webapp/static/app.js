/* doc2kb PKB — frontend */

// ── Navigation ────────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item[data-view]').forEach(btn => {
  btn.addEventListener('click', () => {
    const view = btn.dataset.view;
    document.querySelectorAll('.nav-item[data-view]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`view-${view}`).classList.add('active');
    // Lazy-load per view
    if (view === 'home')   { loadStats(); loadActivity(); }
    if (view === 'wiki')   loadWikiTree();
    if (view === 'docs')   loadDocuments();
  });
});

// ── Ingest tabs ───────────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const group = tab.closest('.card');
    group.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    group.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    group.querySelector(`#tab-${tab.dataset.tab}`).classList.add('active');
  });
});

// ── File drop zone ────────────────────────────────────────────────────────────
const dropZone  = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const fileNameEl = document.getElementById('file-name');

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) fileNameEl.textContent = fileInput.files[0].name;
});
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files.length) {
    fileInput.files = e.dataTransfer.files;
    fileNameEl.textContent = e.dataTransfer.files[0].name;
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStatus(id, msg, type) {
  const el = document.getElementById(id);
  el.className = `status ${type} show`;
  el.innerHTML = msg;
}

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (loading) {
    btn._orig = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> Processing…`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn._orig || btn.innerHTML;
    btn.disabled = false;
  }
}

function typeBadge(type) {
  return `<span class="type-badge type-${type}">${type}</span>`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Stats & activity ──────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const res  = await fetch('/api/stats');
    const data = await res.json();
    document.getElementById('stat-docs').textContent  = `${data.total_docs} docs`;
    document.getElementById('stat-pages').textContent = `${data.wiki_pages} wiki pages`;
    document.getElementById('home-docs').textContent  = data.total_docs;
    document.getElementById('home-wiki').textContent  = data.wiki_pages;
    document.getElementById('home-cats').textContent  = data.wiki_categories;
  } catch { /* ignore */ }
}

async function loadActivity() {
  const el = document.getElementById('activity-log');
  try {
    const res  = await fetch('/api/wiki/log');
    const data = await res.json();

    if (!data.entries.length) {
      el.innerHTML = '<div class="empty">No activity yet. Ingest some documents to get started.</div>';
      return;
    }
    el.innerHTML = data.entries.map(e => `
      <div class="activity-entry">
        <div class="activity-icon ${escHtml(e.action)}">
          ${e.action === 'ingest' ? '⬆️' : '🔍'}
        </div>
        <div>
          <div class="activity-meta">${escHtml(e.timestamp)} · ${escHtml(e.action)}</div>
          <div class="activity-title">${escHtml(e.title)}</div>
          ${e.summary ? `<div class="activity-summary">${escHtml(e.summary)}</div>` : ''}
        </div>
      </div>`).join('');
  } catch {
    el.innerHTML = '<div class="empty" style="color:var(--red)">Failed to load activity.</div>';
  }
}

// ── Ingest URL ────────────────────────────────────────────────────────────────
async function ingestUrl() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) return setStatus('url-status', 'Please enter a URL.', 'err');

  const langs = document.getElementById('url-langs').value
    .split(',').map(s => s.trim()).filter(Boolean);
  const force = document.getElementById('url-force').checked;
  const description = document.getElementById('url-desc').value.trim();

  setLoading('url-btn', true);
  setStatus('url-status', '<span class="spinner"></span> Fetching and ingesting…', 'info show');

  try {
    const res  = await fetch('/api/ingest/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, force, langs, description }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    if (data.status === 'skipped') {
      setStatus('url-status', '⚠️ Already indexed — use "Force re-ingest" to update.', 'info');
    } else {
      const wiki = data.wiki_pages ? ` · ${data.wiki_pages} wiki page(s) created` : '';
      setStatus('url-status',
        `✅ Ingested <strong>${escHtml(data.title)}</strong> — ${data.chunks} chunk(s)${wiki}`,
        'ok');
    }
    loadStats();
    loadActivity();
  } catch (err) {
    setStatus('url-status', `❌ ${err.message}`, 'err');
  } finally {
    setLoading('url-btn', false);
    document.getElementById('url-desc').value = '';
  }
}

// ── Ingest file ───────────────────────────────────────────────────────────────
async function ingestFile() {
  if (!fileInput.files.length) return setStatus('file-status', 'Please select a file.', 'err');

  const langs = document.getElementById('file-langs').value
    .split(',').map(s => s.trim()).filter(Boolean).join(',') || 'en';
  const force = document.getElementById('file-force').checked;
  const description = document.getElementById('file-desc').value.trim();

  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  fd.append('force', force);
  fd.append('langs', langs);
  if (description) fd.append('description', description);

  setLoading('file-btn', true);
  setStatus('file-status', '<span class="spinner"></span> Uploading and ingesting…', 'info show');

  try {
    const res  = await fetch('/api/ingest/file', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    if (data.status === 'skipped') {
      setStatus('file-status', '⚠️ Already indexed — use "Force re-ingest".', 'info');
    } else {
      const wiki = data.wiki_pages ? ` · ${data.wiki_pages} wiki page(s) created` : '';
      setStatus('file-status',
        `✅ Ingested <strong>${escHtml(data.title)}</strong> — ${data.chunks} chunk(s)${wiki}`,
        'ok');
    }
    loadStats();
    loadActivity();
  } catch (err) {
    setStatus('file-status', `❌ ${err.message}`, 'err');
  } finally {
    setLoading('file-btn', false);
    fileNameEl.textContent = '';
    fileInput.value = '';
    document.getElementById('file-desc').value = '';
  }
}

// ── Ingest directory ──────────────────────────────────────────────────────────
const dirInput     = document.getElementById('dir-input');
const dirFolderName = document.getElementById('dir-folder-name');
const dirBtn       = document.getElementById('dir-btn');

const SUPPORTED_EXTS = new Set([
  '.pdf', '.docx', '.doc', '.pptx', '.ppt',
  '.txt', '.md', '.html', '.htm',
  '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp',
]);

dirInput.addEventListener('change', () => {
  const files = [...dirInput.files].filter(f =>
    SUPPORTED_EXTS.has('.' + f.name.split('.').pop().toLowerCase())
  );
  if (files.length) {
    const folderName = dirInput.files[0].webkitRelativePath.split('/')[0];
    dirFolderName.textContent = `📁 ${folderName} — ${files.length} supported file(s)`;
    dirBtn.disabled = false;
  } else {
    dirFolderName.textContent = 'No supported files found.';
    dirBtn.disabled = true;
  }
});

async function ingestDir() {
  const allFiles = [...dirInput.files].filter(f =>
    SUPPORTED_EXTS.has('.' + f.name.split('.').pop().toLowerCase())
  );
  if (!allFiles.length) return setStatus('dir-status', 'Please select a folder first.', 'err');

  const langs = document.getElementById('dir-langs').value
    .split(',').map(s => s.trim()).filter(Boolean).join(',') || 'en';
  const force = document.getElementById('dir-force').checked;
  const description = document.getElementById('dir-desc').value.trim();

  setLoading('dir-btn', true);
  document.getElementById('dir-results').innerHTML = '';
  let ok = 0, skipped = 0, errors = 0;
  const rows = [];

  for (let i = 0; i < allFiles.length; i++) {
    const file = allFiles[i];
    const relPath = file.webkitRelativePath || file.name;
    setStatus('dir-status',
      `<span class="spinner"></span> Processing ${i + 1}/${allFiles.length}: ${escHtml(relPath)}`,
      'info show');

    const fd = new FormData();
    fd.append('file', file, file.name);
    fd.append('force', force);
    fd.append('langs', langs);
    if (description) fd.append('description', description);

    try {
      const res  = await fetch('/api/ingest/file', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);

      if (data.status === 'skipped') {
        skipped++;
        rows.push({ path: relPath, icon: '⏭️', detail: 'already indexed' });
      } else {
        ok++;
        const wiki = data.wiki_pages ? `, ${data.wiki_pages} wiki pages` : '';
        rows.push({ path: relPath, icon: '✅', detail: `${data.chunks} chunks${wiki}` });
      }
    } catch (err) {
      errors++;
      rows.push({ path: relPath, icon: '❌', detail: err.message });
    }
  }

  setStatus('dir-status',
    `✅ Done — ${ok} indexed, ${skipped} skipped, ${errors} errors (${allFiles.length} total)`,
    errors ? 'info' : 'ok');

  document.getElementById('dir-results').innerHTML = `
    <table class="doc-table" style="margin-top:12px;">
      <thead><tr><th></th><th>File</th><th>Result</th></tr></thead>
      <tbody>${rows.map(r => `
        <tr>
          <td>${r.icon}</td>
          <td title="${escHtml(r.path)}">${escHtml(r.path.split('/').pop())}</td>
          <td>${escHtml(r.detail)}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;

  dirFolderName.textContent = '';
  dirInput.value = '';
  dirBtn.disabled = true;
  document.getElementById('dir-desc').value = '';
  setLoading('dir-btn', false);
  loadStats();
  loadActivity();
}

// ── Wiki ──────────────────────────────────────────────────────────────────────
async function loadWikiTree() {
  const treeEl = document.getElementById('wiki-tree');
  try {
    const res  = await fetch('/api/wiki/pages');
    const data = await res.json();
    const pages = data.pages || [];

    if (!pages.length) {
      treeEl.innerHTML = `<div class="empty" style="padding:20px 14px;font-size:12px;">
        No wiki pages yet.<br>Ingest documents to build the wiki.</div>`;
      return;
    }

    const meta    = pages.filter(p => p.is_meta);
    const regular = pages.filter(p => !p.is_meta);
    const cats    = {};
    regular.forEach(p => (cats[p.category] || (cats[p.category] = [])).push(p));

    const catIcon = { entities: '👤', concepts: '💡', _root: '📄' };
    let html = '';

    if (meta.length) {
      html += `<div class="wiki-tree-category">📋 Meta</div>`;
      meta.forEach(p => {
        html += `<div class="wiki-tree-item wiki-tree-meta"
                      data-path="${escHtml(p.path)}"
                      onclick="loadWikiPage('${escHtml(p.path)}')">${escHtml(p.name)}.md</div>`;
      });
    }

    Object.entries(cats).sort().forEach(([cat, catPages]) => {
      const icon = catIcon[cat] || '📁';
      html += `<div class="wiki-tree-category">
                 ${icon} ${escHtml(cat)}
                 <span style="color:var(--border)">(${catPages.length})</span>
               </div>`;
      catPages.forEach(p => {
        html += `<div class="wiki-tree-item"
                      data-path="${escHtml(p.path)}"
                      onclick="loadWikiPage('${escHtml(p.path)}')">${escHtml(p.name)}</div>`;
      });
    });

    treeEl.innerHTML = html;
  } catch {
    treeEl.innerHTML = `<div class="empty" style="padding:20px 14px;color:var(--red)">
      Failed to load wiki.</div>`;
  }
}

async function loadWikiPage(path) {
  // Highlight active item
  document.querySelectorAll('.wiki-tree-item').forEach(el => el.classList.remove('active'));
  const active = document.querySelector(`.wiki-tree-item[data-path="${path}"]`);
  if (active) active.classList.add('active');

  document.getElementById('wiki-page-path').textContent = path;
  document.getElementById('wiki-page-body').innerHTML =
    '<div class="empty"><span class="spinner"></span> Loading…</div>';
  document.getElementById('wiki-answer-area').style.display = 'none';

  try {
    const res  = await fetch(`/api/wiki/page?path=${encodeURIComponent(path)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    document.getElementById('wiki-page-body').innerHTML = marked.parse(data.content);
  } catch (err) {
    document.getElementById('wiki-page-body').innerHTML =
      `<div class="empty" style="color:var(--red)">Error: ${escHtml(err.message)}</div>`;
  }
}

async function queryWiki() {
  const question = document.getElementById('wiki-query-input').value.trim();
  if (!question) return;

  const answerArea  = document.getElementById('wiki-answer-area');
  const wikiAskBtn  = document.getElementById('wiki-ask-btn');
  answerArea.style.display = 'block';
  answerArea.innerHTML = `
    <div class="wiki-answer">
      <div class="wiki-answer-question">💬 ${escHtml(question)}</div>
      <div><span class="spinner"></span> Thinking…</div>
    </div>`;
  wikiAskBtn.disabled = true;

  try {
    const res  = await fetch('/api/wiki/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    const consulted = (data.pages_consulted || []).length
      ? `<div class="wiki-answer-meta">Pages consulted: ${
          data.pages_consulted.map(p => `<code>${escHtml(p)}</code>`).join(', ')
        }</div>`
      : '';

    answerArea.innerHTML = `
      <div class="wiki-answer">
        <div class="wiki-answer-question">💬 ${escHtml(question)}</div>
        <div class="wiki-answer-body">${marked.parse(data.answer)}</div>
        ${consulted}
      </div>`;

    document.getElementById('wiki-query-input').value = '';
    loadActivity();
  } catch (err) {
    answerArea.innerHTML =
      `<div class="wiki-answer" style="color:var(--red)">❌ ${escHtml(err.message)}</div>`;
  } finally {
    wikiAskBtn.disabled = false;
  }
}

// ── Semantic search ───────────────────────────────────────────────────────────
async function search() {
  const q = document.getElementById('query-input').value.trim();
  if (!q) return;
  const n  = document.getElementById('query-n').value || 5;
  const el = document.getElementById('results');
  el.innerHTML = '<div class="empty"><span class="spinner"></span> Searching…</div>';

  try {
    const res  = await fetch(`/api/query?q=${encodeURIComponent(q)}&n=${n}`);
    const hits = await res.json();
    if (!res.ok) throw new Error(hits.detail || res.statusText);

    if (!hits.length) {
      el.innerHTML = '<div class="empty">No results found.</div>';
      return;
    }
    el.innerHTML = hits.map((h, i) => `
      <div class="result-card">
        <div class="result-meta">
          ${typeBadge(h.type)}
          <span style="font-size:12px;color:var(--muted);">#${i + 1}</span>
          <span class="score-badge">score ${h.score}</span>
        </div>
        <div class="result-title">${escHtml(h.title)}</div>
        <div class="result-source">${escHtml(h.source)}</div>
        <div class="result-snippet">${escHtml(h.text.slice(0, 400))}${h.text.length > 400 ? '…' : ''}</div>
      </div>`).join('');
  } catch (err) {
    el.innerHTML = `<div class="empty" style="color:var(--red)">Error: ${err.message}</div>`;
  }
}

// ── Documents ─────────────────────────────────────────────────────────────────
async function loadDocuments() {
  const el = document.getElementById('doc-list');
  try {
    const res  = await fetch('/api/documents');
    const docs = await res.json();

    if (!docs.length) {
      el.innerHTML = '<div class="empty">No documents yet.</div>';
      return;
    }
    el.innerHTML = `
      <table class="doc-table">
        <thead>
          <tr><th>Type</th><th>Title</th><th>Source</th><th>ID</th><th></th></tr>
        </thead>
        <tbody>
          ${docs.map(d => `
            <tr>
              <td>${typeBadge(d.type)}</td>
              <td>${escHtml(d.title)}</td>
              <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
                  title="${escHtml(d.source)}">${escHtml(d.source)}</td>
              <td class="doc-id-cell">${escHtml(d.doc_id)}</td>
              <td><button class="del-btn"
                    onclick="deleteDoc('${escHtml(d.doc_id)}','${escHtml(d.title)}')">Delete</button></td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  } catch {
    el.innerHTML = '<div class="empty" style="color:var(--red)">Failed to load documents.</div>';
  }
}

async function deleteDoc(docId, title) {
  if (!confirm(`Delete "${title}" from the knowledge base?`)) return;
  try {
    const res = await fetch(`/api/documents/${encodeURIComponent(docId)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error((await res.json()).detail);
    loadDocuments();
    loadStats();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

// ── Index rebuild ─────────────────────────────────────────────────────────────
async function rebuildIndex() {
  try {
    await fetch('/api/index', { method: 'POST' });
    alert('_INDEX.md regenerated in the Obsidian vault.');
  } catch {
    alert('Failed to rebuild index.');
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadStats();
loadActivity();
