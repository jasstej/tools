# GhostVault – Browser Password Manager Extension

Encrypted password manager browser extension.
Passwords are encrypted with **GhostCipher** (custom symmetric cipher) and the vault file lives on your external device — never in cloud storage.

---

## Installation (Chrome / Edge / Brave / Opera)

1. Open your browser and navigate to `chrome://extensions` (or `edge://extensions`, etc.).
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked**.
4. Select the `password-manager-extension/` folder.
5. The GhostVault icon appears in your toolbar. Pin it for quick access.

### Firefox

Firefox supports Manifest V3 from version 109+.

1. Navigate to `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on**.
3. Select any file inside `password-manager-extension/` (e.g. `manifest.json`).

> Note: Temporary add-ons are removed when Firefox closes. For permanent installation, the extension must be signed via AMO.

---

## Usage

### First run – create a new vault

1. Click the extension icon.
2. Type a strong master password (≥ 8 characters).
3. Click **New Vault**.
4. Add your first entry via the **+ Add** tab.
5. Click the **Save** icon (floppy disk) in the top bar.
6. In the file-save dialog, navigate to your USB / external drive and save `vault.ghostvault`.

### Subsequent runs – unlock an existing vault

1. Click the extension icon.
2. Click **Browse** at the bottom of the lock screen.
3. Select your `vault.ghostvault` from the external device.
4. Enter your master password and click **Unlock Vault**.

### Saving changes

Click the **Save** icon any time to write the re-encrypted vault back to your external device.
If the browser supports the File System Access API (Chrome 86+, Edge 86+), a native save dialog appears and you choose the destination.
On other browsers a download is triggered — manually move the file to your external device.

---

## GhostCipher – Encryption Details

All encryption runs **in-browser**, in JavaScript. The vault file is standard JSON:

```json
{
  "v":    1,
  "alg":  "GhostCipher-1",
  "salt": "<64-hex chars>  (32 random bytes)",
  "iv":   "<32-hex chars>  (16 random bytes)",
  "mac":  "<16-hex chars>  ( 8 bytes integrity tag)",
  "data": "<hex>           (ciphertext)"
}
```

### Algorithm

| Stage | Detail |
|-------|--------|
| **ghostKDF** | Custom key-derivation: 10,000 rounds of LCG mixing + bit-rotation over a 64-byte state, expanded to **512 bytes** of key material. Inputs: master password + 32-byte random salt. |
| **ghostKSA** | Fisher-Yates shuffle of `[0..255]` seeded with the first 256 bytes of key material → custom S-box. |
| **ghostPRGA** | RC4-variant PRGA using the custom S-box. The 16-byte IV is XOR-injected into the state before the keystream is generated. |
| **Encrypt** | `ciphertext[i] = plaintext[i] XOR keystream[i]` |
| **ghostMAC** | 8-byte keyed MAC: iterates over plaintext mixing each byte with key-material tail bytes via XOR and rotations, then applies a final avalanche pass. Provides authentication and detects wrong passwords or data tampering. |

> The MAC is verified **before** returning decrypted data. A wrong password or modified file raises an error immediately.

### Security notes

- GhostCipher is a **custom algorithm** designed for educational/personal use. It is **not audited** and should not be considered a substitute for AES-GCM or ChaCha20-Poly1305 in high-security contexts.
- The vault file is safe to store on an external drive. Without the master password, the ciphertext reveals nothing about the contents.
- No data is ever sent to the internet. The extension declares no network permissions.

---

## File structure

```
password-manager-extension/
├── manifest.json     ← Manifest V3 extension descriptor
├── background.js     ← Minimal service worker (required by MV3)
├── popup.html        ← Extension popup UI
├── popup.css         ← Dark terminal-themed styles
├── popup.js          ← Application logic (vault, entries, generator)
├── crypto.js         ← GhostCipher encryption engine
└── icons/
    ├── icon16.svg
    ├── icon48.svg
    └── icon128.svg
```

---

## Permissions used

| Permission | Reason |
|-----------|--------|
| `storage` | Persist session state within the extension popup |
| `clipboardWrite` | Copy passwords/usernames to clipboard |

No host permissions. No network access.
