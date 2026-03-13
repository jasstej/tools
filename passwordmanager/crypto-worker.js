/**
 * crypto-worker.js
 * Runs GhostCipher in a Web Worker so the KDF never blocks the main thread.
 */
importScripts('crypto.js');

self.addEventListener('message', (e) => {
  const { id, action, payload, password } = e.data;
  try {
    let result;
    if (action === 'encrypt') {
      result = GhostCipher.encrypt(payload, password);
    } else if (action === 'decrypt') {
      result = GhostCipher.decrypt(payload, password);
    } else {
      throw new Error('Unknown action: ' + action);
    }
    self.postMessage({ id, success: true, result });
  } catch (err) {
    self.postMessage({ id, success: false, error: err.message });
  }
});
