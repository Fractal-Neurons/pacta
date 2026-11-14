// Zero-dependency Keccak-f[1600] sponge (rate 136 bytes / 256-bit output).
// Node's crypto exposes SHA3-256 but not the original Keccak-256 used by Ethereum (they differ only in the
// domain-separation padding byte: 0x01 for Keccak, 0x06 for SHA3). Both are exposed so tests can cross-check the
// permutation against node:crypto's sha3-256 and the Keccak-256 known-answer vectors.

const RATE = 136;
const MASK64 = (1n << 64n) - 1n;

const ROUND_CONSTANTS = [
  0x0000000000000001n, 0x0000000000008082n, 0x800000000000808an, 0x8000000080008000n,
  0x000000000000808bn, 0x0000000080000001n, 0x8000000080008081n, 0x8000000000008009n,
  0x000000000000008an, 0x0000000000000088n, 0x0000000080008009n, 0x000000008000000an,
  0x000000008000808bn, 0x800000000000008bn, 0x8000000000008089n, 0x8000000000008003n,
  0x8000000000008002n, 0x8000000000000080n, 0x000000000000800an, 0x800000008000000an,
  0x8000000080008081n, 0x8000000000008080n, 0x0000000080000001n, 0x8000000080008008n,
];

// Rotation offsets r[x][y] (state index = x + 5y).
const ROTATIONS = [
  [0, 36, 3, 41, 18],
  [1, 44, 10, 45, 2],
  [62, 6, 43, 15, 61],
  [28, 55, 25, 21, 56],
  [27, 20, 39, 8, 14],
];

const rotl64 = (v, r) => (r === 0 ? v : ((v << BigInt(r)) | (v >> BigInt(64 - r))) & MASK64);

function keccakF1600(s) {
  const c = new Array(5);
  const b = new Array(25);
  for (let round = 0; round < 24; round++) {
    // theta
    for (let x = 0; x < 5; x++) c[x] = s[x] ^ s[x + 5] ^ s[x + 10] ^ s[x + 15] ^ s[x + 20];
    for (let x = 0; x < 5; x++) {
      const d = c[(x + 4) % 5] ^ rotl64(c[(x + 1) % 5], 1);
      for (let y = 0; y < 25; y += 5) s[x + y] ^= d;
    }
    // rho + pi
    for (let x = 0; x < 5; x++) {
      for (let y = 0; y < 5; y++) {
        b[y + 5 * ((2 * x + 3 * y) % 5)] = rotl64(s[x + 5 * y], ROTATIONS[x][y]);
      }
    }
    // chi
    for (let y = 0; y < 25; y += 5) {
      for (let x = 0; x < 5; x++) {
        s[x + y] = b[x + y] ^ (~b[((x + 1) % 5) + y] & MASK64 & b[((x + 2) % 5) + y]);
      }
    }
    // iota
    s[0] ^= ROUND_CONSTANTS[round];
  }
}

function toBytes(input) {
  if (input instanceof Uint8Array) return input;
  if (typeof input === "string") return new TextEncoder().encode(input);
  throw new TypeError("keccak input must be a Uint8Array or string");
}

function sponge256(input, padByte) {
  const msg = toBytes(input);
  const padded = new Uint8Array(Math.floor(msg.length / RATE) * RATE + RATE);
  padded.set(msg);
  padded[msg.length] ^= padByte;
  padded[padded.length - 1] ^= 0x80;

  const state = new Array(25).fill(0n);
  for (let off = 0; off < padded.length; off += RATE) {
    for (let i = 0; i < RATE / 8; i++) {
      let lane = 0n;
      for (let k = 7; k >= 0; k--) lane = (lane << 8n) | BigInt(padded[off + 8 * i + k]);
      state[i] ^= lane;
    }
    keccakF1600(state);
  }

  let out = "";
  for (let i = 0; i < 4; i++) {
    let lane = state[i];
    for (let k = 0; k < 8; k++) {
      out += Number(lane & 0xffn).toString(16).padStart(2, "0");
      lane >>= 8n;
    }
  }
  return out;
}

/** Ethereum Keccak-256. Returns 64 lowercase hex chars (no 0x prefix). */
export const keccak256Hex = (input) => sponge256(input, 0x01);

/** FIPS-202 SHA3-256 on the same permutation (used only to cross-check against node:crypto). */
export const sha3_256Hex = (input) => sponge256(input, 0x06);
