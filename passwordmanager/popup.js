'use strict';

/**
 * popup.js  – GhostVault main application logic
 *
 * Flow:
 *  1. Lock screen  → user enters master password
 *  2. Vault screen → view / add / edit / delete entries, generate passwords
 *  3. Save         → encrypt with GhostCipher and write .ghostvault file to
 *                    an external device (File System Access API → fallback download)
 *  4. Import       → load .ghostvault file, decrypt in-browser
 */

// ── state ─────────────────────────────────────────────────────────────────────

const state = {
  masterPassword:  null,      // string
  vault:           null,      // { entries: [], lastModified: number }
  vaultFilename:   'vault.ghostvault',
  editingEntryId:  null,      // string | null
  generatedPassword: null,    // latest generated password
};

// Blank vault template
function emptyVault() {
  return { entries: [], lastModified: Date.now() };
}

// ── Web Worker bridge ─────────────────────────────────────────────────────────
// GhostCipher's KDF is CPU-intensive. Running it in a Worker keeps the popup
// alive and the browser from killing the page as unresponsive.

const _worker = new Worker(chrome.runtime.getURL('crypto-worker.js'));
let _msgId = 0;
const _pending = {};

_worker.addEventListener('message', ({ data: { id, success, result, error } }) => {
  const cb = _pending[id];
  if (!cb) return;
  delete _pending[id];
  success ? cb.resolve(result) : cb.reject(new Error(error));
});

function workerCall(action, payload, password) {
  return new Promise((resolve, reject) => {
    const id = ++_msgId;
    _pending[id] = { resolve, reject };
    _worker.postMessage({ id, action, payload, password });
  });
}

// ── DOM refs ──────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

const screens  = { lock: $('screen-lock'), vault: $('screen-vault') };
const tabs     = { passwords: $('tab-passwords'), add: $('tab-add'), generator: $('tab-generator') };
const tabBtns  = $$('.tab');

// lock screen
const masterPasswordInput = $('master-password');
const btnUnlock           = $('btn-unlock');
const btnNewVault         = $('btn-new-vault');
const lockError           = $('lock-error');
const fileImportLock      = $('file-import-lock');

// vault bar
const vaultFilenameEl = $('vault-filename');
const btnSave         = $('btn-save');
const btnLock         = $('btn-lock');

// passwords tab
const searchInput  = $('search-input');
const entriesList  = $('entries-list');

// add/edit tab
const addTabTitle    = $('add-tab-title');
const entrysite      = $('entry-site');
const entryUsername  = $('entry-username');
const entryPassword  = $('entry-password');
const entryNotes     = $('entry-notes');
const btnSaveEntry   = $('btn-save-entry');
const btnCancelEdit  = $('btn-cancel-edit');
const btnUseGenerated = $('btn-use-generated');
const addError       = $('add-error');
const addSuccess     = $('add-success');

// generator tab
const genLength    = $('gen-length');
const genLengthVal = $('gen-length-val');
const genUpper     = $('gen-upper');
const genLower     = $('gen-lower');
const genDigits    = $('gen-digits');
const genSymbols   = $('gen-symbols');
const generatedPw  = $('generated-password');
const btnCopyGen   = $('btn-copy-gen');
const btnGenerate  = $('btn-generate');
const btnUseGenInAdd = $('btn-use-gen-in-add');

// modal
const modalOverlay  = $('modal-overlay');
const modalClose    = $('modal-close');
const modalSite     = $('modal-site');
const modalUsername = $('modal-username');
const modalPassword = $('modal-password');
const modalNotes    = $('modal-notes');
const modalNotesRow = $('modal-notes-row');
const modalUpdated  = $('modal-updated');
const modalEdit     = $('modal-edit');
const modalDelete   = $('modal-delete');

const toastEl = $('toast');
let _toastTimer;

// ── helpers ───────────────────────────────────────────────────────────────────

function showToast(msg, duration = 2000) {
  clearTimeout(_toastTimer);
  toastEl.textContent = msg;
  toastEl.classList.remove('hidden');
  _toastTimer = setTimeout(() => toastEl.classList.add('hidden'), duration);
}

function uuid() {
  return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
}

function formatDate(ts) {
  return new Date(ts).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

function showError(el, msg)   { el.textContent = msg; el.classList.remove('hidden'); }
function hideError(el)        { el.textContent = '';  el.classList.add('hidden'); }
function showSuccess(el, msg) { el.textContent = msg; el.classList.remove('hidden'); setTimeout(() => el.classList.add('hidden'), 2500); }

// ── screens ───────────────────────────────────────────────────────────────────

function showScreen(name) {
  Object.values(screens).forEach(el => el.classList.remove('active'));
  screens[name].classList.add('active');
}

// ── tabs ──────────────────────────────────────────────────────────────────────

function switchTab(name) {
  Object.values(tabs).forEach(el => el.classList.remove('active'));
  tabs[name].classList.add('active');
  tabBtns.forEach(btn => btn.classList.toggle('active', btn.dataset.tab === name));
}

tabBtns.forEach(btn => btn.addEventListener('click', () => switchTab(btn.dataset.tab)));

// ── password visibility toggles ───────────────────────────────────────────────

$$('.toggle-vis').forEach(btn => {
  btn.addEventListener('click', () => {
    const input = $(btn.dataset.target);
    input.type = input.type === 'password' ? 'text' : 'password';
  });
});

// ── lock screen logic ─────────────────────────────────────────────────────────

// Unlock with existing vault (loaded via file import)
btnUnlock.addEventListener('click', handleUnlock);
masterPasswordInput.addEventListener('keydown', e => { if (e.key === 'Enter') handleUnlock(); });

async function handleUnlock() {
  const pw = masterPasswordInput.value.trim();
  if (!pw) { showError(lockError, 'Master password is required'); return; }

  if (!state._pendingVaultJson) {
    showError(lockError, 'Load a vault file first, or create a New Vault');
    return;
  }

  btnUnlock.disabled    = true;
  btnUnlock.textContent = 'Decrypting…';
  hideError(lockError);

  try {
    const plaintext = await workerCall('decrypt', state._pendingVaultJson, pw);
    state.vault             = JSON.parse(plaintext);
    state.masterPassword    = pw;
    state._pendingVaultJson = null;
    openVaultScreen();
  } catch (err) {
    if (err.message.includes('Authentication failed') || err.message.includes('wrong password')) {
      showError(lockError, 'Wrong master password');
    } else {
      showError(lockError, 'Failed to open vault: ' + err.message);
    }
  } finally {
    btnUnlock.disabled    = false;
    btnUnlock.textContent = 'Unlock Vault';
  }
}

// Create a brand-new vault
btnNewVault.addEventListener('click', () => {
  const pw = masterPasswordInput.value.trim();
  if (!pw) { showError(lockError, 'Enter a master password for the new vault'); return; }
  if (pw.length < 8) { showError(lockError, 'Password must be at least 8 characters'); return; }
  state.vault          = emptyVault();
  state.masterPassword = pw;
  state._pendingVaultJson = null;
  openVaultScreen();
  showToast('New vault created. Remember to save it!');
});

// Import from file (lock screen)
fileImportLock.addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    state._pendingVaultJson = ev.target.result;
    state.vaultFilename = file.name;
    hideError(lockError);
    lockError.textContent = '';
    lockError.classList.remove('hidden');
    lockError.style.background = 'rgba(0,229,255,.08)';
    lockError.style.borderColor = 'rgba(0,229,255,.3)';
    lockError.style.color = '#00e5ff';
    lockError.textContent = `Loaded: ${file.name}  — Enter password to unlock`;
  };
  reader.readAsText(file);
  fileImportLock.value = '';
});

function openVaultScreen() {
  hideError(lockError);
  masterPasswordInput.value = '';
  lockError.style.background = '';
  lockError.style.borderColor = '';
  lockError.style.color = '';
  vaultFilenameEl.textContent = state.vaultFilename;
  showScreen('vault');
  switchTab('passwords');
  renderEntries();
}

// ── lock / save buttons ───────────────────────────────────────────────────────

btnLock.addEventListener('click', () => {
  state.masterPassword  = null;
  state.vault           = null;
  state._pendingVaultJson = null;
  showScreen('lock');
});

btnSave.addEventListener('click', saveVault);

// ── save to external device ───────────────────────────────────────────────────

async function saveVault() {
  if (!state.vault || !state.masterPassword) return;
  state.vault.lastModified = Date.now();

  btnSave.disabled = true;
  showToast('Encrypting vault…');

  let ciphertext;
  try {
    ciphertext = await workerCall('encrypt', JSON.stringify(state.vault), state.masterPassword);
  } catch (err) {
    showToast('Encryption failed: ' + err.message);
    btnSave.disabled = false;
    return;
  } finally {
    btnSave.disabled = false;
  }

  const blob = new Blob([ciphertext], { type: 'application/json' });
  const filename = state.vaultFilename.endsWith('.ghostvault')
    ? state.vaultFilename : 'vault.ghostvault';

  // Prefer File System Access API to allow saving to any drive (external device)
  if ('showSaveFilePicker' in window) {
    try {
      const fh = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [{
          description: 'GhostVault file',
          accept: { 'application/json': ['.ghostvault', '.json'] }
        }]
      });
      state.vaultFilename = fh.name;
      vaultFilenameEl.textContent = fh.name;
      const writable = await fh.createWritable();
      await writable.write(blob);
      await writable.close();
      showToast('Vault saved to external device');
      return;
    } catch (err) {
      if (err.name === 'AbortError') return;   // user cancelled
      // fall through to download fallback
    }
  }

  // Fallback: trigger browser download (user can choose path, e.g. USB drive)
  const url = URL.createObjectURL(blob);
  const a   = $('save-anchor');
  a.href     = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  showToast('Download started – save to your external device');
}

// ── entries rendering ─────────────────────────────────────────────────────────

function getFilteredEntries() {
  const q = (searchInput.value || '').toLowerCase().trim();
  if (!q) return state.vault.entries;
  return state.vault.entries.filter(e =>
    e.site.toLowerCase().includes(q) || e.username.toLowerCase().includes(q)
  );
}

function renderEntries() {
  const entries = getFilteredEntries();
  entriesList.innerHTML = '';
  if (entries.length === 0) {
    entriesList.innerHTML = '<div class="empty-state">No entries found</div>';
    return;
  }
  entries.forEach(entry => {
    const card = document.createElement('div');
    card.className = 'entry-card';
    card.dataset.id = entry.id;

    const initial = (entry.site[0] || '?').toUpperCase();
    card.innerHTML = `
      <div class="entry-avatar">${initial}</div>
      <div class="entry-info">
        <div class="entry-site">${escHtml(entry.site)}</div>
        <div class="entry-user">${escHtml(entry.username)}</div>
      </div>
    `;
    card.addEventListener('click', () => openModal(entry.id));
    entriesList.appendChild(card);
  });
}

searchInput.addEventListener('input', renderEntries);

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── add / edit entry ──────────────────────────────────────────────────────────

btnSaveEntry.addEventListener('click', handleSaveEntry);

function handleSaveEntry() {
  const site     = entrysite.value.trim();
  const username = entryUsername.value.trim();
  const password = entryPassword.value;
  const notes    = entryNotes.value.trim();

  hideError(addError);
  if (!site)     { showError(addError, 'Site / App name is required'); return; }
  if (!username) { showError(addError, 'Username is required'); return; }
  if (!password) { showError(addError, 'Password is required'); return; }

  if (state.editingEntryId) {
    // update
    const idx = state.vault.entries.findIndex(e => e.id === state.editingEntryId);
    if (idx !== -1) {
      state.vault.entries[idx] = { ...state.vault.entries[idx], site, username, password, notes, updated: Date.now() };
    }
    state.editingEntryId = null;
    addTabTitle.textContent = 'New Entry';
    btnCancelEdit.classList.add('hidden');
    showSuccess(addSuccess, 'Entry updated');
  } else {
    // create
    state.vault.entries.push({ id: uuid(), site, username, password, notes, created: Date.now(), updated: Date.now() });
    showSuccess(addSuccess, 'Entry added');
  }

  entrysite.value    = '';
  entryUsername.value = '';
  entryPassword.value = '';
  entryNotes.value   = '';

  renderEntries();
}

btnCancelEdit.addEventListener('click', () => {
  state.editingEntryId = null;
  addTabTitle.textContent = 'New Entry';
  btnCancelEdit.classList.add('hidden');
  entrysite.value    = '';
  entryUsername.value = '';
  entryPassword.value = '';
  entryNotes.value   = '';
  hideError(addError);
  switchTab('passwords');
});

btnUseGenerated.addEventListener('click', () => {
  if (state.generatedPassword) {
    entryPassword.value = state.generatedPassword;
  } else {
    showToast('Generate a password first in the Generator tab');
  }
});

// ── modal ─────────────────────────────────────────────────────────────────────

let _modalEntryId = null;
let _modalPasswordRevealed = false;

function openModal(id) {
  const entry = state.vault.entries.find(e => e.id === id);
  if (!entry) return;
  _modalEntryId = id;
  _modalPasswordRevealed = false;

  modalSite.textContent    = entry.site;
  modalUsername.textContent = entry.username;
  modalPassword.textContent = '••••••••';
  modalPassword.classList.add('masked');
  modalPassword.dataset.plain = entry.password;

  if (entry.notes) {
    modalNotes.textContent = entry.notes;
    modalNotesRow.classList.remove('hidden');
  } else {
    modalNotesRow.classList.add('hidden');
  }
  modalUpdated.textContent = formatDate(entry.updated || entry.created);
  modalOverlay.classList.remove('hidden');
}

modalClose.addEventListener('click', closeModal);
modalOverlay.addEventListener('click', e => { if (e.target === modalOverlay) closeModal(); });

function closeModal() {
  modalOverlay.classList.add('hidden');
  _modalEntryId = null;
}

// reveal password
modalPassword.previousElementSibling?.addEventListener('click', revealPassword);
$$('.reveal-btn').forEach(btn => btn.addEventListener('click', revealPassword));
function revealPassword() {
  _modalPasswordRevealed = !_modalPasswordRevealed;
  if (_modalPasswordRevealed) {
    modalPassword.textContent = modalPassword.dataset.plain;
    modalPassword.classList.remove('masked');
  } else {
    modalPassword.textContent = '••••••••';
    modalPassword.classList.add('masked');
  }
}

// copy buttons
$$('.copy-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.dataset.copy === 'username') {
      copyToClipboard(modalUsername.textContent);
    } else if (btn.dataset.copy === 'password') {
      copyToClipboard(modalPassword.dataset.plain);
    }
  });
});

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard')).catch(() => showToast('Copy failed'));
}

// edit entry from modal
modalEdit.addEventListener('click', () => {
  const entry = state.vault.entries.find(e => e.id === _modalEntryId);
  if (!entry) return;
  closeModal();
  state.editingEntryId    = entry.id;
  entrysite.value         = entry.site;
  entryUsername.value     = entry.username;
  entryPassword.value     = entry.password;
  entryNotes.value        = entry.notes || '';
  addTabTitle.textContent = 'Edit Entry';
  btnCancelEdit.classList.remove('hidden');
  hideError(addError);
  hideError(addSuccess);
  switchTab('add');
});

// delete entry
modalDelete.addEventListener('click', () => {
  if (!_modalEntryId) return;
  state.vault.entries = state.vault.entries.filter(e => e.id !== _modalEntryId);
  closeModal();
  renderEntries();
  showToast('Entry deleted');
});

// ── password generator ────────────────────────────────────────────────────────

genLength.addEventListener('input', () => { genLengthVal.textContent = genLength.value; });

btnGenerate.addEventListener('click', generatePassword);

function generatePassword() {
  const len  = parseInt(genLength.value, 10);
  const chars =
    (genUpper.checked  ? 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' : '') +
    (genLower.checked  ? 'abcdefghijklmnopqrstuvwxyz' : '') +
    (genDigits.checked ? '0123456789'                  : '') +
    (genSymbols.checked? '!@#$%^&*()-_=+[]{}|;:,.<>?' : '');

  if (!chars) { showToast('Select at least one character class'); return; }

  const arr = new Uint32Array(len);
  crypto.getRandomValues(arr);
  let pw = '';
  for (let i = 0; i < len; i++) pw += chars[arr[i] % chars.length];

  generatedPw.textContent    = pw;
  state.generatedPassword    = pw;
}

btnCopyGen.addEventListener('click', () => {
  if (state.generatedPassword) copyToClipboard(state.generatedPassword);
});

btnUseGenInAdd.addEventListener('click', () => {
  if (!state.generatedPassword) { showToast('Generate a password first'); return; }
  entryPassword.value = state.generatedPassword;
  switchTab('add');
  showToast('Password pasted into Add Entry form');
});

// ── init ──────────────────────────────────────────────────────────────────────

showScreen('lock');
generatePassword(); // pre-fill generator on load
