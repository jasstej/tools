/**
 * GhostCipher v1 - Custom Symmetric Encryption Engine
 *
 * Algorithm overview:
 * 1. Key Derivation  : ghostKDF  - custom KDF, 10,000 rounds of LCG + XOR mixing
 * 2. Key Setup (KSA) : ghostKSA  - Fisher-Yates shuffle seeded with derived key
 * 3. Stream Cipher   : ghostPRGA - RC4-variant PRGA using custom S-box + IV injection
 * 4. Integrity       : ghostMAC  - keyed MAC over plaintext using key material tail
 *
 * File format (JSON):
 * {
 *   "v"    : 1,             // format version
 *   "alg"  : "GhostCipher-1",
 *   "salt" : "<64-hex>",   // 32 random bytes
 *   "iv"   : "<32-hex>",   // 16 random bytes
 *   "mac"  : "<16-hex>",   //  8 bytes integrity tag
 *   "data" : "<hex>"       // encrypted payload
 * }
 */

'use strict';

const GhostCipher = (() => {

  // ── helpers ─────────────────────────────────────────────────────────────────

  function strToBytes(str) {
    const enc = new TextEncoder();
    return enc.encode(str);
  }

  function bytesToStr(bytes) {
    return new TextDecoder().decode(bytes);
  }

  function hexEncode(bytes) {
    return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  function hexDecode(hex) {
    if (hex.length % 2 !== 0) throw new Error('Invalid hex string');
    const out = new Uint8Array(hex.length / 2);
    for (let i = 0; i < out.length; i++) {
      out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    }
    return out;
  }

  function randomBytes(n) {
    const buf = new Uint8Array(n);
    crypto.getRandomValues(buf);
    return buf;
  }

  /** Rotate byte left by `bits` */
  function rotl8(v, bits) {
    bits &= 7;
    return ((v << bits) | (v >>> (8 - bits))) & 0xFF;
  }

  /** Convert 32-bit int to 4-byte little-endian array */
  function i32ToBytes(n) {
    return [n & 0xFF, (n >>> 8) & 0xFF, (n >>> 16) & 0xFF, (n >>> 24) & 0xFF];
  }

  // ── GhostKDF ────────────────────────────────────────────────────────────────
  // Derives 512 bytes of key material from password + salt.
  // Each round mixes the 64-byte state with password, salt and a round counter
  // via LCG, XOR and bit-rotation to make inversion computationally expensive.

  function ghostKDF(password, salt, iterations = 10000) {
    const pw   = strToBytes(password);
    const sl   = salt;                    // Uint8Array, 32 bytes

    // Initialise 64-byte state
    let state = new Uint8Array(64);
    for (let i = 0; i < 64; i++) {
      state[i] = pw[i % pw.length] ^ sl[i % sl.length] ^ (i * 0x1B);
    }

    for (let round = 0; round < iterations; round++) {
      const rc = i32ToBytes(round);
      const next = new Uint8Array(64);

      for (let i = 0; i < 64; i++) {
        let v = state[i];
        v ^= state[(i + 1) % 64];
        v ^= pw  [(i + round) % pw.length];
        v ^= sl  [i % sl.length];
        v ^= rc  [i % 4];
        v  = rotl8(v, (i + round) % 8);
        // LCG step on the byte
        v  = ((v * 0x6B + 0x3D) & 0xFF);
        // Feedback from a distance-7 byte
        v ^= state[(i + 7) % 64];
        next[i] = v;
      }

      // Final pass: each byte depends on its two neighbours (diffusion)
      for (let i = 0; i < 64; i++) {
        next[i] ^= next[(i + 3) % 64] ^ next[(i + 59) % 64];
      }

      state = next;
    }

    // Expand 64-byte seed → 512 bytes using continued mixing rounds
    const output = new Uint8Array(512);
    let pos = 0;
    let expand = state.slice();

    while (pos < 512) {
      // One extra mix round (no password/salt, just self-mixing)
      const next = new Uint8Array(64);
      for (let i = 0; i < 64; i++) {
        let v = expand[i];
        v ^= expand[(i + 5) % 64];
        v  = rotl8(v, (i % 6) + 1);
        v  = ((v * 0xC3 + 0x29) & 0xFF);
        v ^= expand[(i + 11) % 64];
        next[i] = v;
      }
      const chunk = Math.min(64, 512 - pos);
      output.set(next.slice(0, chunk), pos);
      pos += chunk;
      expand = next;
    }

    return output; // Uint8Array(512)
  }

  // ── GhostKSA ────────────────────────────────────────────────────────────────
  // Fisher-Yates shuffle of [0..255] keyed with key material bytes.
  // Returns a 256-element Uint8Array (the S-box).

  function ghostKSA(keyMaterial) {
    const s = new Uint8Array(256);
    for (let i = 0; i < 256; i++) s[i] = i;

    let j = 0;
    for (let i = 0; i < 256; i++) {
      // Mix two key bytes at different offsets for more diffusion
      j = (j + s[i] + keyMaterial[i % keyMaterial.length]
                     + keyMaterial[(i * 3 + 7) % keyMaterial.length]) & 0xFF;
      const tmp = s[i]; s[i] = s[j]; s[j] = tmp;
    }
    return s;
  }

  // ── GhostPRGA ───────────────────────────────────────────────────────────────
  // RC4-variant stream cipher using a pre-built S-box, IV-injected into state.

  function ghostPRGA(sbox, iv, length) {
    const s = sbox.slice(); // work on a copy

    // Inject IV into the first 16 positions of the state
    for (let i = 0; i < iv.length; i++) {
      s[i] ^= iv[i];
    }
    // Re-shuffle the IV-modified positions
    let j = 0;
    for (let i = 0; i < iv.length; i++) {
      j = (j + s[i]) & 0xFF;
      const tmp = s[i]; s[i] = s[j]; s[j] = tmp;
    }

    // PRGA
    let si = 0, sj = 0;
    const out = new Uint8Array(length);
    for (let k = 0; k < length; k++) {
      si = (si + 1) & 0xFF;
      sj = (sj + s[si]) & 0xFF;
      const tmp = s[si]; s[si] = s[sj]; s[sj] = tmp;
      out[k] = s[(s[si] + s[sj]) & 0xFF];
    }
    return out;
  }

  // ── GhostMAC ────────────────────────────────────────────────────────────────
  // 8-byte keyed Message Authentication Code over the plaintext.

  function ghostMAC(keyMaterial, plaintext) {
    // Use the tail of the key material as MAC key
    const macKey = keyMaterial.slice(448, 512); // 64 bytes
    const mac = new Uint8Array(8);

    for (let i = 0; i < plaintext.length; i++) {
      mac[i % 8] ^= plaintext[i] ^ macKey[(i * 5 + 3) % 64];
      mac[(i + 2) % 8] = rotl8(mac[(i + 2) % 8], 1);
      mac[(i + 5) % 8] ^= macKey[(i + 7) % 64];
    }

    // Final avalanche pass
    for (let i = 0; i < 8; i++) {
      mac[i] ^= macKey[i];
      mac[i]  = ((mac[i] * 0xD3 + 0x49) & 0xFF);
      mac[i] ^= macKey[i + 8];
    }
    return mac; // Uint8Array(8)
  }

  // ── public API ───────────────────────────────────────────────────────────────

  /**
   * Encrypt a UTF-8 string with a master password.
   * Returns a JSON string (the vault file content).
   */
  function encrypt(plaintext, password) {
    const salt       = randomBytes(32);
    const iv         = randomBytes(16);
    const keyMat     = ghostKDF(password, salt);
    const sbox       = ghostKSA(keyMat.slice(0, 256));
    const ptBytes    = strToBytes(plaintext);
    const keystream  = ghostPRGA(sbox, iv, ptBytes.length);

    // XOR encrypt
    const ciphertext = new Uint8Array(ptBytes.length);
    for (let i = 0; i < ptBytes.length; i++) {
      ciphertext[i] = ptBytes[i] ^ keystream[i];
    }

    const mac = ghostMAC(keyMat, ptBytes);

    return JSON.stringify({
      v:    1,
      alg:  'GhostCipher-1',
      salt: hexEncode(salt),
      iv:   hexEncode(iv),
      mac:  hexEncode(mac),
      data: hexEncode(ciphertext)
    });
  }

  /**
   * Decrypt vault file content (JSON string) with master password.
   * Returns the original UTF-8 plaintext or throws on wrong password / tampered data.
   */
  function decrypt(vaultJson, password) {
    let vault;
    try {
      vault = JSON.parse(vaultJson);
    } catch {
      throw new Error('Invalid vault file: not valid JSON');
    }
    if (vault.v !== 1 || vault.alg !== 'GhostCipher-1') {
      throw new Error('Unsupported vault format');
    }

    const salt       = hexDecode(vault.salt);
    const iv         = hexDecode(vault.iv);
    const storedMac  = hexDecode(vault.mac);
    const ciphertext = hexDecode(vault.data);

    const keyMat     = ghostKDF(password, salt);
    const sbox       = ghostKSA(keyMat.slice(0, 256));
    const keystream  = ghostPRGA(sbox, iv, ciphertext.length);

    // XOR decrypt
    const ptBytes = new Uint8Array(ciphertext.length);
    for (let i = 0; i < ciphertext.length; i++) {
      ptBytes[i] = ciphertext[i] ^ keystream[i];
    }

    // Verify MAC
    const computedMac = ghostMAC(keyMat, ptBytes);
    let mismatch = 0;
    for (let i = 0; i < 8; i++) mismatch |= storedMac[i] ^ computedMac[i];
    if (mismatch !== 0) throw new Error('Authentication failed: wrong password or corrupted vault');

    return bytesToStr(ptBytes);
  }

  return { encrypt, decrypt };
})();
