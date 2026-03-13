// background.js – GhostVault service worker
// Minimal: the extension is entirely popup-driven.
// This file must exist for Manifest V3 to be valid.

chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === 'install') {
    console.log('[GhostVault] Installed – open the extension popup to get started.');
  }
});
