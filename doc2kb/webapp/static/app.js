/* doc2kb frontend */

// ── Tabs ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const group = tab.closest('.card');
    group.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    group.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    group.querySelector(`#tab-${tab.dataset.tab}`).classList.add('active');
  });
});

// ── Drop zone ─────────────────────────────────────────────────────────────────
const dropZone = document.getElementById('drop-zone');
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
  const dt = e.dataTransfer;
  if (dt.files.length) {
    fileInput.files = dt.files;
    fileNameEl.textContent = dt.files[0].name;
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

// ── Ingest URL ────────────────────────────────────────────────────────────────
async function ingestUrl() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) return setStatus('url-status', 'Please enter a URL.', 'err');

  const langs = document.getElementById('url-langs').value
    .split(',').map(s => s.trim()).filter(Boolean);
  const force = document.getElementById('url-force').checked;

  setLoading('url-btn', true);
  setStatus('url-status', '<span class="spinner"></span> Fetching and ingesting…', 'info show');

  try {
    const res = await fetch('/api/ingest/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, force, langs }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    if (data.status === 'skipped') {
      setStatus('url-status', `⚠️ Already indexed — use "Force" to re-ingest.`, 'info');
    } else {
      setStatus('url-status', `✅ Ingested <strong>${data.title}</strong> — ${data.chunks} chunk(s)`, 'ok');
    }
    loadDocuments();
  } catch (err) {
    setStatus('url-status', `❌ ${err.message}`, 'err');
  } finally {
    setLoading('url-btn', false);
  }
}

// ── Ingest File ───────────────────────────────────────────────────────────────
async function ingestFile() {
  if (!fileInput.files.length) return setStatus('file-status', 'Please select a file.', 'err');

  const langs = document.getElementById('file-langs').value
    .split(',').map(s => s.trim()).filter(Boolean).join(',') || 'en';
  const force = document.getElementById('file-force').checked;

  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  fd.append('force', force);
  fd.append('langs', langs);

  setLoading('file-btn', true);
  setStatus('file-status', '<span class="spinner"></span> Uploading and ingesting…', 'info show');

  try {
    const res = await fetch('/api/ingest/file', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    if (data.status === 'skipped') {
      setStatus('file-status', `⚠️ Already indexed — use "Force" to re-ingest.`, 'info');
    } else {
      setStatus('file-status', `✅ Ingested <strong>${data.title}</strong> — ${data.chunks} chunk(s)`, 'ok');
    }
    loadDocuments();
  } catch (err) {
    setStatus('file-status', `❌ ${err.message}`, 'err');
  } finally {
    setLoading('file-btn', false);
    fileNameEl.textContent = '';
    fileInput.value = '';
  }
}

// ── Ingest Directory ──────────────────────────────────────────────────────────
async function ingestDir() {
  const directory = document.getElementById('dir-input').value.trim();
  if (!directory) return setStatus('dir-status', 'Please enter a directory path.', 'err');

  const langs = document.getElementById('dir-langs').value
    .split(',').map(s => s.trim()).filter(Boolean);
  const force = document.getElementById('dir-force').checked;

  setLoading('dir-btn', true);
  setStatus('dir-status', '<span class="spinner"></span> Scanning and ingesting…', 'info show');
  document.getElementById('dir-results').innerHTML = '';

  try {
    const res = await fetch('/api/ingest/dir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ directory, force, langs }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    if (data.status === 'empty') {
      setStatus('dir-status', '⚠️ No supported files found in that directory.', 'info');
    } else {
      setStatus('dir-status',
        `✅ Done — ${data.indexed} indexed, ${data.skipped} skipped, ${data.errors} errors (${data.total} total)`,
        data.errors ? 'info' : 'ok');

      // Detail table
      const rows = data.details.map(r => {
        const name = r.file.replace(/.*[\\/]/, '');
        const icon = r.status === 'ok' ? '✅' : r.status === 'skipped' ? '⏭️' : '❌';
        const detail = r.status === 'ok' ? `${r.chunks} chunks`
                     : r.status === 'skipped' ? 'already indexed'
                     : escHtml(r.message || '');
        return `<tr><td>${icon}</td><td title="${escHtml(r.file)}">${escHtml(name)}</td><td>${detail}</td></tr>`;
      }).join('');

      document.getElementById('dir-results').innerHTML = `
        <table class="doc-table" style="margin-top:12px;">
          <thead><tr><th></th><th>File</th><th>Result</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>`;
    }
    loadDocuments();
  } catch (err) {
    setStatus('dir-status', `❌ ${err.message}`, 'err');
  } finally {
    setLoading('dir-btn', false);
  }
}

// ── Search ────────────────────────────────────────────────────────────────────
async function search() {
  const q = document.getElementById('query-input').value.trim();
  if (!q) return;
  const n = document.getElementById('query-n').value || 5;
  const el = document.getElementById('results');
  el.innerHTML = '<div class="empty"><span class="spinner"></span> Searching…</div>';

  try {
    const res = await fetch(`/api/query?q=${encodeURIComponent(q)}&n=${n}`);
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
      </div>
    `).join('');
  } catch (err) {
    el.innerHTML = `<div class="empty" style="color:var(--red);">Error: ${err.message}</div>`;
  }
}

// ── Documents ─────────────────────────────────────────────────────────────────
async function loadDocuments() {
  const el = document.getElementById('doc-list');
  try {
    const res = await fetch('/api/documents');
    const docs = await res.json();

    document.getElementById('doc-count').textContent =
      `${docs.length} document${docs.length !== 1 ? 's' : ''}`;

    if (!docs.length) {
      el.innerHTML = '<div class="empty">No documents yet.</div>';
      return;
    }

    el.innerHTML = `
      <table class="doc-table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Title</th>
            <th>Source</th>
            <th>ID</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${docs.map(d => `
            <tr>
              <td>${typeBadge(d.type)}</td>
              <td>${escHtml(d.title)}</td>
              <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escHtml(d.source)}">${escHtml(d.source)}</td>
              <td class="doc-id-cell">${escHtml(d.doc_id)}</td>
              <td><button class="del-btn" onclick="deleteDoc('${escHtml(d.doc_id)}','${escHtml(d.title)}')">Delete</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>`;
  } catch {
    el.innerHTML = '<div class="empty" style="color:var(--red);">Failed to load documents.</div>';
  }
}

async function deleteDoc(docId, title) {
  if (!confirm(`Delete "${title}" from the knowledge base?`)) return;
  try {
    const res = await fetch(`/api/documents/${encodeURIComponent(docId)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error((await res.json()).detail);
    loadDocuments();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

// ── Index rebuild ─────────────────────────────────────────────────────────────
async function rebuildIndex() {
  try {
    await fetch('/api/index', { method: 'POST' });
    alert('_INDEX.md regenerated in Obsidian vault.');
  } catch {
    alert('Failed to rebuild index.');
  }
}

// ── Utils ─────────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadDocuments();
