#!/usr/bin/env python3
"""Monocypher CLI — stdin/stdout hex protocol, pure Python implementation."""
import sys, struct

# ========================= I/O HELPERS =========================

def read_line():
    line = sys.stdin.readline()
    if not line:
        return None
    return line.rstrip('\n\r: ')

def hex_decode(s):
    s = s.strip()
    if not s:
        return b''
    return bytes.fromhex(s)

def hex_encode(b):
    return b.hex()

def print_hex(b):
    sys.stdout.write(b.hex() + ':\n')
    sys.stdout.flush()

def load32_le(s):
    return struct.unpack('<I', s[:4])[0]

def load64_le(s):
    return struct.unpack('<Q', s[:8])[0]

def load24_le(s):
    return s[0] | (s[1] << 8) | (s[2] << 16)

def store32_le(v):
    return struct.pack('<I', v & 0xFFFFFFFF)

def store64_le(v):
    return struct.pack('<Q', v & 0xFFFFFFFFFFFFFFFF)

def rotr64(x, n):
    return ((x >> n) | (x << (64 - n))) & 0xFFFFFFFFFFFFFFFF

def rotl32(x, n):
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF

ZERO128 = b'\x00' * 128

def gap(n, align):
    return (-n) % align if n % align != 0 else 0

# ========================= CHACHA20 =========================

CHACHA_CONST = [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574]

def _qr(s, a, b, c, d):
    s[a] = (s[a] + s[b]) & 0xFFFFFFFF
    s[d] = rotl32(s[d] ^ s[a], 16)
    s[c] = (s[c] + s[d]) & 0xFFFFFFFF
    s[b] = rotl32(s[b] ^ s[c], 12)
    s[a] = (s[a] + s[b]) & 0xFFFFFFFF
    s[d] = rotl32(s[d] ^ s[a], 8)
    s[c] = (s[c] + s[d]) & 0xFFFFFFFF
    s[b] = rotl32(s[b] ^ s[c], 7)

def _chacha20_rounds(state):
    working = list(state)
    for _ in range(10):
        _qr(working, 0, 4, 8, 12)
        _qr(working, 1, 5, 9, 13)
        _qr(working, 2, 6, 10, 14)
        _qr(working, 3, 7, 11, 15)
        _qr(working, 0, 5, 10, 15)
        _qr(working, 1, 6, 11, 12)
        _qr(working, 2, 7, 8, 13)
        _qr(working, 3, 4, 9, 14)
    return working

def chacha20_block(key, counter, nonce):
    k = list(struct.unpack('<8I', key))
    n = list(struct.unpack('<2I', nonce))
    state = CHACHA_CONST + k + [counter & 0xFFFFFFFF, (counter >> 32) & 0xFFFFFFFF] + n
    result = _chacha20_rounds(state)
    return struct.pack('<16I', *[(result[i] + state[i]) & 0xFFFFFFFF for i in range(16)])

def chacha20_h(key, inp16):
    k = list(struct.unpack('<8I', key))
    i = list(struct.unpack('<4I', inp16))
    state = CHACHA_CONST + k + i
    result = _chacha20_rounds(state)
    return struct.pack('<4I', *result[0:4]) + struct.pack('<4I', *result[12:16])

def chacha20_djb(plain, size, key, nonce8, ctr):
    cipher = bytearray(size)
    pos = 0
    c = ctr
    if plain is None:
        while pos < size:
            block = chacha20_block(key, c, nonce8)
            end = min(64, size - pos)
            for i in range(end):
                cipher[pos + i] = block[i]
            pos += 64
            c += 1
    else:
        while pos < size:
            block = chacha20_block(key, c, nonce8)
            end = min(64, size - pos)
            for i in range(end):
                cipher[pos + i] = plain[pos + i] ^ block[i]
            pos += 64
            c += 1
    return bytes(cipher), c

def chacha20_ietf_enc(plain, size, key, nonce12, ctr_u32):
    n_lo = load32_le(nonce12[4:8])
    n_hi = load32_le(nonce12[8:12])
    big_nonce = struct.pack('<II', n_lo, n_hi)
    big_ctr = ctr_u32 + (load32_le(nonce12[0:4]) << 32)
    cipher, new_ctr = chacha20_djb(plain, size, key, big_nonce, big_ctr)
    return cipher, new_ctr & 0xFFFFFFFF

def chacha20_x_enc(plain, size, key, nonce24, ctr):
    sub = chacha20_h(key, nonce24[:16])
    cipher, new_ctr = chacha20_djb(plain, size, sub, nonce24[16:24], ctr)
    return cipher, new_ctr

def crypto_chacha20_h_cmd(key, inp):
    return chacha20_h(key, inp)

def crypto_chacha20_djb_cmd(key, nonce, plain, ctr_buf):
    ctr = load64_le(ctr_buf)
    cipher, new_ctr = chacha20_djb(plain, len(plain), key, nonce, ctr)
    return cipher, store64_le(new_ctr)

def crypto_chacha20_ietf_cmd(key, nonce, plain, ctr_buf):
    ctr = load32_le(ctr_buf)
    cipher, new_ctr = chacha20_ietf_enc(plain, len(plain), key, nonce, ctr)
    return cipher, store32_le(new_ctr)

def crypto_chacha20_x_cmd(key, nonce, plain, ctr_buf):
    ctr = load64_le(ctr_buf)
    cipher, new_ctr = chacha20_x_enc(plain, len(plain), key, nonce, ctr)
    return cipher, store64_le(new_ctr)

# ========================= POLY1305 =========================

def poly1305(msg, key):
    r0 = load32_le(key[0:4]) & 0x0fffffff
    r1 = load32_le(key[4:8]) & 0x0ffffffc
    r2 = load32_le(key[8:12]) & 0x0ffffffc
    r3 = load32_le(key[12:16]) & 0x0ffffffc
    pad0 = load32_le(key[16:20])
    pad1 = load32_le(key[20:24])
    pad2 = load32_le(key[24:28])
    pad3 = load32_le(key[28:32])
    rr0 = ((r0 >> 2) * 5) & 0xFFFFFFFF
    rr1 = (r1 >> 2) + r1
    rr2 = (r2 >> 2) + r2
    rr3 = (r3 >> 2) + r3
    rr4 = r0 & 3
    h0 = h1 = h2 = h3 = h4 = 0
    idx = 0
    mlen = len(msg)
    while idx + 16 <= mlen:
        s0 = h0 + load32_le(msg[idx:idx+4])
        s1 = h1 + load32_le(msg[idx+4:idx+8])
        s2 = h2 + load32_le(msg[idx+8:idx+12])
        s3 = h3 + load32_le(msg[idx+12:idx+16])
        s4 = h4 + 1
        x0 = s0*r0 + s1*rr3 + s2*rr2 + s3*rr1 + s4*rr0
        x1 = s0*r1 + s1*r0  + s2*rr3 + s3*rr2 + s4*rr1
        x2 = s0*r2 + s1*r1  + s2*r0  + s3*rr3 + s4*rr2
        x3 = s0*r3 + s1*r2  + s2*r1  + s3*r0  + s4*rr3
        x4 = s4*rr4
        u5 = (x3 >> 32) + x4
        u0 = ((u5 >> 2) * 5) + (x0 & 0xFFFFFFFF)
        u1 = (u0 >> 32) + (x1 & 0xFFFFFFFF) + (x0 >> 32)
        u2 = (u1 >> 32) + (x2 & 0xFFFFFFFF) + (x1 >> 32)
        u3 = (u2 >> 32) + (x3 & 0xFFFFFFFF) + (x2 >> 32)
        u4 = (u3 >> 32) + (u5 & 3)
        h0 = u0 & 0xFFFFFFFF
        h1 = u1 & 0xFFFFFFFF
        h2 = u2 & 0xFFFFFFFF
        h3 = u3 & 0xFFFFFFFF
        h4 = u4 & 0xFFFFFFFF
        idx += 16
    if idx < mlen:
        c_idx = mlen - idx
        partial = bytearray(16)
        partial[:c_idx] = msg[idx:idx+c_idx]
        partial[c_idx] = 1
        s0 = h0 + load32_le(bytes(partial[0:4]))
        s1 = h1 + load32_le(bytes(partial[4:8]))
        s2 = h2 + load32_le(bytes(partial[8:12]))
        s3 = h3 + load32_le(bytes(partial[12:16]))
        s4 = h4
        x0 = s0*r0 + s1*rr3 + s2*rr2 + s3*rr1 + s4*rr0
        x1 = s0*r1 + s1*r0  + s2*rr3 + s3*rr2 + s4*rr1
        x2 = s0*r2 + s1*r1  + s2*r0  + s3*rr3 + s4*rr2
        x3 = s0*r3 + s1*r2  + s2*r1  + s3*r0  + s4*rr3
        x4 = s4*rr4
        u5 = (x3 >> 32) + x4
        u0 = ((u5 >> 2) * 5) + (x0 & 0xFFFFFFFF)
        u1 = (u0 >> 32) + (x1 & 0xFFFFFFFF) + (x0 >> 32)
        u2 = (u1 >> 32) + (x2 & 0xFFFFFFFF) + (x1 >> 32)
        u3 = (u2 >> 32) + (x3 & 0xFFFFFFFF) + (x2 >> 32)
        u4 = (u3 >> 32) + (u5 & 3)
        h0 = u0 & 0xFFFFFFFF
        h1 = u1 & 0xFFFFFFFF
        h2 = u2 & 0xFFFFFFFF
        h3 = u3 & 0xFFFFFFFF
        h4 = u4 & 0xFFFFFFFF
    c = 5
    c += h0; c >>= 32
    c += h1; c >>= 32
    c += h2; c >>= 32
    c += h3; c >>= 32
    c += h4
    c = (c >> 2) * 5
    r = bytearray(16)
    h = [h0, h1, h2, h3]
    for i in range(4):
        c += h[i] + [pad0, pad1, pad2, pad3][i]
        struct.pack_into('<I', r, i*4, c & 0xFFFFFFFF)
        c >>= 32
    return bytes(r)

# ========================= BLAKE2b =========================

BLAKE2b_IV = [
    0x6a09e667f3bcc908, 0xbb67ae8584caa73b,
    0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1,
    0x510e527fade682d1, 0x9b05688c2b3e6c1f,
    0x1f83d9abfb41bd6b, 0x5be0cd19137e2179,
]

SIGMA = [
    [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15],
    [14,10,4,8,9,15,13,6,1,12,0,2,11,7,5,3],
    [11,8,12,0,5,2,15,13,10,14,3,6,7,1,9,4],
    [7,9,3,1,13,12,11,14,2,6,5,10,4,0,15,8],
    [9,0,5,7,2,4,10,15,14,1,11,12,6,8,3,13],
    [2,12,6,10,0,11,8,3,4,13,7,5,15,14,1,9],
    [12,5,1,15,14,13,4,10,0,7,6,3,9,2,8,11],
    [13,11,7,14,12,1,3,9,5,0,15,4,8,6,2,10],
    [6,15,14,9,11,3,0,8,12,2,13,7,1,4,10,5],
    [10,2,8,4,7,6,1,5,15,11,9,14,3,12,13,0],
    [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15],
    [14,10,4,8,9,15,13,6,1,12,0,2,11,7,5,3],
]

def _blake2b_G(v, a, b, c, d, x, y):
    v[a] = (v[a] + v[b] + x) & 0xFFFFFFFFFFFFFFFF
    v[d] = rotr64(v[d] ^ v[a], 32)
    v[c] = (v[c] + v[d]) & 0xFFFFFFFFFFFFFFFF
    v[b] = rotr64(v[b] ^ v[c], 24)
    v[a] = (v[a] + v[b] + y) & 0xFFFFFFFFFFFFFFFF
    v[d] = rotr64(v[d] ^ v[a], 16)
    v[c] = (v[c] + v[d]) & 0xFFFFFFFFFFFFFFFF
    v[b] = rotr64(v[b] ^ v[c], 63)

def _blake2b_compress(h, t, block, last):
    v = [0]*16
    v[0:8] = list(h)
    v[8:15] = BLAKE2b_IV[0:7]
    v[15] = BLAKE2b_IV[7]
    v[12] ^= (t & 0xFFFFFFFFFFFFFFFF)
    v[13] ^= ((t >> 64) & 0xFFFFFFFFFFFFFFFF)
    if last:
        v[14] ^= 0xFFFFFFFFFFFFFFFF
    m = list(struct.unpack('<16Q', block))
    for r in range(12):
        s = SIGMA[r % 10]
        _blake2b_G(v,0,4,8,12, m[s[ 0]], m[s[ 1]])
        _blake2b_G(v,1,5,9,13, m[s[ 2]], m[s[ 3]])
        _blake2b_G(v,2,6,10,14,m[s[ 4]], m[s[ 5]])
        _blake2b_G(v,3,7,11,15,m[s[ 6]], m[s[ 7]])
        _blake2b_G(v,0,5,10,15,m[s[ 8]], m[s[ 9]])
        _blake2b_G(v,1,6,11,12,m[s[10]], m[s[11]])
        _blake2b_G(v,2,7,8,13, m[s[12]], m[s[13]])
        _blake2b_G(v,3,4,9,14, m[s[14]], m[s[15]])
    for i in range(8):
        h[i] ^= v[i] ^ v[i+8]

def blake2b_full(out_size, msg, key=b''):
    klen = len(key)
    h = list(BLAKE2b_IV)
    h[0] ^= 0x01010000 ^ (klen << 8) ^ out_size
    t = 0
    block = bytearray(128)
    if klen > 0:
        bl = min(klen, 128)
        block[:bl] = key[:bl]
        t = 128
        _blake2b_compress(h, t, bytes(block), False)
    idx = 0
    mlen = len(msg)
    while mlen - idx > 128:
        t += 128
        _blake2b_compress(h, t, msg[idx:idx+128], False)
        idx += 128
    rest = mlen - idx
    block = bytearray(128)
    block[:rest] = msg[idx:idx+rest]
    t += rest
    _blake2b_compress(h, t, bytes(block), True)
    out = bytearray()
    for i in range(8):
        out += struct.pack('<Q', h[i])
    return bytes(out[:out_size])

def crypto_blake2b(msg):
    return blake2b_full(64, msg)

def crypto_blake2b_keyed(msg, key):
    return blake2b_full(64, msg, key)

# ========================= SHA-512 =========================

SHA512_K = [
    0x428a2f98d728ae22, 0x7137449123ef65cd, 0xb5c0fbcfec4d3b2f, 0xe9b5dba58189dbbc,
    0x3956c25bf348b538, 0x59f111f1b605d019, 0x923f82a4af194f9b, 0xab1c5ed5da6d8118,
    0xd807aa98a3030242, 0x12835b0145706fbe, 0x243185be4ee4b28c, 0x550c7dc3d5ffb4e2,
    0x72be5d74f27b896f, 0x80deb1fe3b1696b1, 0x9bdc06a725c71235, 0xc19bf174cf692694,
    0xe49b69c19ef14ad2, 0xefbe4786384f25e3, 0x0fc19dc68b8cd5b5, 0x240ca1cc77ac9c65,
    0x2de92c6f592b0275, 0x4a7484aa6ea6e483, 0x5cb0a9dcbd41fbd4, 0x76f988da831153b5,
    0x983e5152ee66dfab, 0xa831c66d2db43210, 0xb00327c898fb213f, 0xbf597fc7beef0ee4,
    0xc6e00bf33da88fc2, 0xd5a79147930aa725, 0x06ca6351e003826f, 0x142929670a0e6e70,
    0x27b70a8546d22ffc, 0x2e1b21385c26c926, 0x4d2c6dfc5ac42aed, 0x53380d139d95b3df,
    0x650a73548baf63de, 0x766a0abb3c77b2a8, 0x81c2c92e47edaee6, 0x92722c851482353b,
    0xa2bfe8a14cf10364, 0xa81a664bbc423001, 0xc24b8b70d0f89791, 0xc76c51a30654be30,
    0xd192e819d6ef5218, 0xd69906245565a910, 0xf40e35855771202a, 0x106aa07032bbd1b8,
    0x19a4c116b8d2d0c8, 0x1e376c085141ab53, 0x2748774cdf8eeb99, 0x34b0bcb5e19b48a8,
    0x391c0cb3c5c95a63, 0x4ed8aa4ae3418acb, 0x5b9cca4f7763e373, 0x682e6ff3d6b2b8a3,
    0x748f82ee5defb2fc, 0x78a5636f43172f60, 0x84c87814a1f0ab72, 0x8cc702081a6439ec,
    0x90befffa23631e28, 0xa4506cebde82bde9, 0xbef9a3f7b2c67915, 0xc67178f2e372532b,
    0xca273eceea26619c, 0xd186b8c721c0c207, 0xeada7dd6cde0eb1e, 0xf57d4f7fee6ed178,
    0x06f067aa72176fba, 0x0a637dc5a2c898a6, 0x113f9804bef90dae, 0x1b710b35131c471b,
    0x28db77f523047d84, 0x32caab7b40c72493, 0x3c9ebe0a15c9bebc, 0x431d67c49c100d4c,
    0x4cc5d4becb3e42b6, 0x597f299cfc657e2a, 0x5fcb6fab3ad6faec, 0x6c44198c4a475817,
]

SHA512_IV = [
    0x6a09e667f3bcc908, 0xbb67ae8584caa73b,
    0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1,
    0x510e527fade682d1, 0x9b05688c2b3e6c1f,
    0x1f83d9abfb41bd6b, 0x5be0cd19137e2179,
]

def _sha512_compress(h, block):
    w = list(struct.unpack('>16Q', block))
    for i in range(16, 80):
        s0 = rotr64(w[i-15], 1) ^ rotr64(w[i-15], 8) ^ (w[i-15] >> 7)
        s1 = rotr64(w[i-2], 19) ^ rotr64(w[i-2], 61) ^ (w[i-2] >> 6)
        w.append((w[i-16] + s0 + w[i-7] + s1) & 0xFFFFFFFFFFFFFFFF)
    a, b, c, d, e, f, g, hh = h
    for i in range(80):
        S1 = rotr64(e, 14) ^ rotr64(e, 18) ^ rotr64(e, 41)
        ch = (e & f) ^ (~e & g) & 0xFFFFFFFFFFFFFFFF
        t1 = (hh + S1 + ch + SHA512_K[i] + w[i]) & 0xFFFFFFFFFFFFFFFF
        S0 = rotr64(a, 28) ^ rotr64(a, 34) ^ rotr64(a, 39)
        mj = (a & b) ^ (a & c) ^ (b & c)
        t2 = (S0 + mj) & 0xFFFFFFFFFFFFFFFF
        hh = g; g = f; f = e; e = (d + t1) & 0xFFFFFFFFFFFFFFFF
        d = c; c = b; b = a; a = (t1 + t2) & 0xFFFFFFFFFFFFFFFF
    h[0] = (h[0] + a) & 0xFFFFFFFFFFFFFFFF
    h[1] = (h[1] + b) & 0xFFFFFFFFFFFFFFFF
    h[2] = (h[2] + c) & 0xFFFFFFFFFFFFFFFF
    h[3] = (h[3] + d) & 0xFFFFFFFFFFFFFFFF
    h[4] = (h[4] + e) & 0xFFFFFFFFFFFFFFFF
    h[5] = (h[5] + f) & 0xFFFFFFFFFFFFFFFF
    h[6] = (h[6] + g) & 0xFFFFFFFFFFFFFFFF
    h[7] = (h[7] + hh) & 0xFFFFFFFFFFFFFFFF

def sha512(msg):
    h = list(SHA512_IV)
    msg_len = len(msg)
    t = 0
    idx = 0
    while msg_len - idx >= 128:
        t += 1024
        _sha512_compress(h, msg[idx:idx+128])
        idx += 128
    rest = bytearray(msg_len - idx)
    rest[:] = msg[idx:]
    rest.append(0x80)
    pad_len = (-len(rest) - 16) % 128
    rest.extend(b'\x00' * pad_len)
    t += (msg_len - idx) * 8
    rest += struct.pack('>QQ', t >> 64, t & 0xFFFFFFFFFFFFFFFF)
    _sha512_compress(h, bytes(rest[:128]))
    if len(rest) > 128:
        _sha512_compress(h, bytes(rest[128:256]))
    out = b''
    for v in h:
        out += struct.pack('>Q', v)
    return out

def sha512_hmac(key, msg):
    if len(key) > 128:
        key = sha512(key)
    key = key.ljust(128, b'\x00')
    ipad = bytes(k ^ 0x36 for k in key)
    opad = bytes(k ^ 0x5c for k in key)
    return sha512(opad + sha512(ipad + msg))

def sha512_hkdf(okm_size, ikm, salt, info):
    prk = sha512_hmac(salt, ikm)
    n = (okm_size + 63) // 64
    okm = b''
    t = b''
    for i in range(1, n + 1):
        t = sha512_hmac(prk, t + info + bytes([i]))
        okm += t
    return okm[:okm_size]

# ========================= FIELD ARITHMETIC =========================

# Radix 2^25.5: even limbs 26 bits, odd limbs 25 bits
# p = 2^255 - 19

FE_ONE = [1,0,0,0,0,0,0,0,0,0]
FE_ZERO = [0]*10

FE_SQRTM1 = [-32595792, -7943725, 9377950, 3500415, 12389472, -272473, -25146209, -2005654, 326686, 11406482]
FE_D = [-10913610, 13857413, -15372611, 6949391, 114729, -8787816, -6275908, -3247719, -18696448, -12055116]
FE_D2 = [-21827239, -5839606, -30745221, 13898782, 229458, 15978800, -12551817, -6495438, 29715968, 9444199]
FE_LOP_X = [21352778, 5345713, 4660180, -8347857, 24143090, 14568123, 30185756, -12247770, -33528939, 8345319]
FE_LOP_Y = [-6952922, -1265500, 6862341, -7057498, -4037696, -5447722, 31680899, -15325402, -19365852, 1569102]
FE_UFACTOR = [-1917299, 15887451, -18755900, -7000830, -24778944, 544946, -16816446, 4011309, -653372, 10741468]
FE_A2 = [12721188, 3529, 0, 0, 0, 0, 0, 0, 0, 0]
FE_A = [486662, 0, 0, 0, 0, 0, 0, 0, 0, 0]

def fe_copy(f):
    return list(f)

def fe_0():
    return [0]*10

def fe_1():
    h = [0]*10
    h[0] = 1
    return h

def fe_neg(f):
    return [-f[i] for i in range(10)]

def fe_add(f, g):
    return [f[i] + g[i] for i in range(10)]

def fe_sub(f, g):
    return [f[i] - g[i] for i in range(10)]

def fe_carry(h):
    t0, t1, t2, t3, t4, t5, t6, t7, t8, t9 = h
    c = (t0 + (1 << 25)) >> 26; t0 -= c * (1 << 26); t1 += c
    c = (t4 + (1 << 25)) >> 26; t4 -= c * (1 << 26); t5 += c
    c = (t1 + (1 << 24)) >> 25; t1 -= c * (1 << 25); t2 += c
    c = (t5 + (1 << 24)) >> 25; t5 -= c * (1 << 25); t6 += c
    c = (t2 + (1 << 25)) >> 26; t2 -= c * (1 << 26); t3 += c
    c = (t6 + (1 << 25)) >> 26; t6 -= c * (1 << 26); t7 += c
    c = (t3 + (1 << 24)) >> 25; t3 -= c * (1 << 25); t4 += c
    c = (t7 + (1 << 24)) >> 25; t7 -= c * (1 << 25); t8 += c
    c = (t4 + (1 << 25)) >> 26; t4 -= c * (1 << 26); t5 += c
    c = (t8 + (1 << 25)) >> 26; t8 -= c * (1 << 26); t9 += c
    c = (t9 + (1 << 24)) >> 25; t9 -= c * (1 << 25); t0 += c * 19
    c = (t0 + (1 << 25)) >> 26; t0 -= c * (1 << 26); t1 += c
    return [t0, t1, t2, t3, t4, t5, t6, t7, t8, t9]

def fe_frombytes_mask(s, nb_mask):
    mask = 0xffffff >> nb_mask
    t0 =  load32_le(s)
    t1 =  load24_le(s[4:7]) << 6
    t2 =  load24_le(s[7:10]) << 5
    t3 =  load24_le(s[10:13]) << 3
    t4 =  load24_le(s[13:16]) << 2
    t5 =  load32_le(s[16:20])
    t6 =  load24_le(s[20:23]) << 7
    t7 =  load24_le(s[23:26]) << 5
    t8 =  load24_le(s[26:29]) << 4
    t9 = (load24_le(s[29:32]) & mask) << 2
    return fe_carry([t0, t1, t2, t3, t4, t5, t6, t7, t8, t9])

def fe_frombytes(s):
    return fe_frombytes_mask(s, 1)

def fe_tobytes(h):
    t = list(h)
    q = (19 * t[9] + (1 << 24)) >> 25
    for i in range(5):
        q += t[2*i]; q >>= 26
        q += t[2*i+1]; q >>= 25
    q *= 19
    for i in range(5):
        t[i*2] += q; q = t[i*2] >> 26; t[i*2] -= q * (1 << 26)
        t[i*2+1] += q; q = t[i*2+1] >> 25; t[i*2+1] -= q * (1 << 25)
    s = bytearray(32)
    struct.pack_into('<I', s,  0, ((t[0] & 0xFFFFFFFF) | ((t[1] & 0xFFFFFFFF) << 26)) & 0xFFFFFFFF)
    struct.pack_into('<I', s,  4, (((t[1] >> 6) & 0x3FFFFFF) | ((t[2] & 0x1FFFFFF) << 19)) & 0xFFFFFFFF)
    struct.pack_into('<I', s,  8, (((t[2] >> 13) & 0x1FFF) | ((t[3] & 0x1FFFFFF) << 13)) & 0xFFFFFFFF)
    struct.pack_into('<I', s, 12, (((t[3] >> 19) & 0x3F) | ((t[4] & 0x3FFFFFF) << 6)) & 0xFFFFFFFF)
    struct.pack_into('<I', s, 16, ((t[5] & 0xFFFFFFFF) | ((t[6] & 0x1FFFFFF) << 25)) & 0xFFFFFFFF)
    struct.pack_into('<I', s, 20, (((t[6] >> 7) & 0x1FFFFFF) | ((t[7] & 0x1FFFFFF) << 19)) & 0xFFFFFFFF)
    struct.pack_into('<I', s, 24, (((t[7] >> 13) & 0xFFF) | ((t[8] & 0x3FFFFFF) << 12)) & 0xFFFFFFFF)
    struct.pack_into('<I', s, 28, (((t[8] >> 20) & 0x3F) | ((t[9] & 0x1FFFFFF) << 6)) & 0xFFFFFFFF)
    return bytes(s)

def fe_isodd(f):
    s = fe_tobytes(f)
    return s[0] & 1

def fe_isequal(f, g):
    return 1 if fe_tobytes(f) == fe_tobytes(g) else 0

def fe_mul_small(f, g):
    return fe_carry([f[i] * g for i in range(10)])

def fe_mul(f, g):
    f0,f1,f2,f3,f4,f5,f6,f7,f8,f9 = f
    g0,g1,g2,g3,g4,g5,g6,g7,g8,g9 = g
    F1=f1*2; F3=f3*2; F5=f5*2; F7=f7*2; F9=f9*2
    G1=g1*19; G2=g2*19; G3=g3*19; G4=g4*19; G5=g5*19; G6=g6*19; G7=g7*19; G8=g8*19; G9=g9*19
    t0 = f0*g0 + F1*G9 + f2*G8 + F3*G7 + f4*G6 + F5*G5 + f6*G4 + F7*G3 + f8*G2 + F9*G1
    t1 = f0*g1 + f1*g0 + f2*G9 + f3*G8 + f4*G7 + f5*G6 + f6*G5 + f7*G4 + f8*G3 + f9*G2
    t2 = f0*g2 + F1*g1 + f2*g0 + F3*G9 + f4*G8 + F5*G7 + f6*G6 + F7*G5 + f8*G4 + F9*G3
    t3 = f0*g3 + f1*g2 + f2*g1 + f3*g0 + f4*G9 + f5*G8 + f6*G7 + f7*G6 + f8*G5 + f9*G4
    t4 = f0*g4 + F1*g3 + f2*g2 + F3*g1 + f4*g0 + F5*G9 + f6*G8 + F7*G7 + f8*G6 + F9*G5
    t5 = f0*g5 + f1*g4 + f2*g3 + f3*g2 + f4*g1 + f5*g0 + f6*G9 + f7*G8 + f8*G7 + f9*G6
    t6 = f0*g6 + F1*g5 + f2*g4 + F3*g3 + f4*g2 + F5*g1 + f6*g0 + F7*G9 + f8*G8 + F9*G7
    t7 = f0*g7 + f1*g6 + f2*g5 + f3*g4 + f4*g3 + f5*g2 + f6*g1 + f7*g0 + f8*G9 + f9*G8
    t8 = f0*g8 + F1*g7 + f2*g6 + F3*g5 + f4*g4 + F5*g3 + f6*g2 + F7*g1 + f8*g0 + F9*G9
    t9 = f0*g9 + f1*g8 + f2*g7 + f3*g6 + f4*g5 + f5*g4 + f6*g3 + f7*g2 + f8*g1 + f9*g0
    return fe_carry([t0,t1,t2,t3,t4,t5,t6,t7,t8,t9])

def fe_sq(f):
    f0,f1,f2,f3,f4,f5,f6,f7,f8,f9 = f
    f0_2=f0*2; f1_2=f1*2; f2_2=f2*2; f3_2=f3*2; f4_2=f4*2
    f5_2=f5*2; f6_2=f6*2; f7_2=f7*2
    f5_38=f5*38; f6_19=f6*19; f7_38=f7*38; f8_19=f8*19; f9_38=f9*38
    t0 = f0*f0 + f1_2*f9_38 + f2_2*f8_19 + f3_2*f7_38 + f4_2*f6_19 + f5*f5_38
    t1 = f0_2*f1 + f2*f9_38 + f3_2*f8_19 + f4*f7_38 + f5_2*f6_19
    t2 = f0_2*f2 + f1_2*f1 + f3_2*f9_38 + f4_2*f8_19 + f5_2*f7_38 + f6*f6_19
    t3 = f0_2*f3 + f1_2*f2 + f4*f9_38 + f5_2*f8_19 + f6*f7_38
    t4 = f0_2*f4 + f1_2*f3_2 + f2*f2 + f5_2*f9_38 + f6_2*f8_19 + f7*f7_38
    t5 = f0_2*f5 + f1_2*f4 + f2_2*f3 + f6*f9_38 + f7_2*f8_19
    t6 = f0_2*f6 + f1_2*f5_2 + f2_2*f4 + f3_2*f3 + f7_2*f9_38 + f8*f8_19
    t7 = f0_2*f7 + f1_2*f6 + f2_2*f5 + f3_2*f4 + f8*f9_38
    t8 = f0_2*f8 + f1_2*f7_2 + f2_2*f6 + f3_2*f5_2 + f4*f4 + f9*f9_38
    t9 = f0_2*f9 + f1_2*f8 + f2_2*f7 + f3_2*f6 + f4*f5_2
    return fe_carry([t0,t1,t2,t3,t4,t5,t6,t7,t8,t9])

def fe_ccopy(f, g, b):
    mask = -b
    return [f[i] ^ ((f[i] ^ g[i]) & mask) for i in range(10)]

def fe_cswap(f, g, b):
    mask = -b
    return [f[i] ^ ((f[i] ^ g[i]) & mask) for i in range(10)], [g[i] ^ ((f[i] ^ g[i]) & mask) for i in range(10)]

def invsqrt(isr, x):
    t0 = fe_sq(x)
    t1 = fe_sq(t0); t1 = fe_sq(t1); t1 = fe_mul(x, t1)
    t0 = fe_mul(t0, t1)
    t0 = fe_sq(t0); t0 = fe_mul(t1, t0)
    t1 = fe_sq(t0)
    for _ in range(4): t1 = fe_sq(t1)
    t0 = fe_mul(t1, t0)
    t1 = fe_sq(t0)
    for _ in range(9): t1 = fe_sq(t1)
    t1 = fe_mul(t1, t0)
    t2 = fe_sq(t1)
    for _ in range(19): t2 = fe_sq(t2)
    t1 = fe_mul(t2, t1)
    t1 = fe_sq(t1)
    for _ in range(9): t1 = fe_sq(t1)
    t0 = fe_mul(t1, t0)
    t1 = fe_sq(t0)
    for _ in range(49): t1 = fe_sq(t1)
    t1 = fe_mul(t1, t0)
    t2 = fe_sq(t1)
    for _ in range(99): t2 = fe_sq(t2)
    t1 = fe_mul(t2, t1)
    t1 = fe_sq(t1)
    for _ in range(49): t1 = fe_sq(t1)
    t0 = fe_mul(t1, t0)
    t0 = fe_sq(t0); t0 = fe_sq(t0); t0 = fe_mul(t0, x)
    quartic = fe_sq(t0)
    quartic = fe_mul(quartic, x)
    check = fe_0(); z0 = fe_isequal(x, check)
    check = fe_1(); p1 = fe_isequal(quartic, check)
    check = fe_neg(check); m1 = fe_isequal(quartic, check)
    check = fe_neg(FE_SQRTM1); ms = fe_isequal(quartic, check)
    result = fe_mul(t0, FE_SQRTM1)
    result = fe_ccopy(result, t0, 1 - (m1 | ms))
    for i in range(10):
        isr[i] = result[i]
    return p1 | m1 | z0

def fe_invert(out, x):
    tmp = fe_sq(x)
    invsqrt(tmp, tmp)
    tmp = fe_sq(tmp)
    result = fe_mul(tmp, x)
    for i in range(10):
        out[i] = result[i]

# ========================= GE (EXTENDED POINTS) =========================

class GE:
    __slots__ = ['X','Y','Z','T']
    def __init__(self, X=None, Y=None, Z=None, T=None):
        self.X = list(X) if X else [0]*10
        self.Y = list(Y) if Y else [0]*10
        self.Z = list(Z) if Z else [0]*10
        self.T = list(T) if T else [0]*10

class GE_CACHED:
    __slots__ = ['Yp','Ym','Z','T2']
    def __init__(self, Yp=None, Ym=None, Z=None, T2=None):
        self.Yp = list(Yp) if Yp else [0]*10
        self.Ym = list(Ym) if Ym else [0]*10
        self.Z  = list(Z)  if Z  else [0]*10
        self.T2 = list(T2) if T2 else [0]*10

class GE_PRECOMP:
    __slots__ = ['Yp','Ym','T2']
    def __init__(self, Yp=None, Ym=None, T2=None):
        self.Yp = list(Yp) if Yp else [0]*10
        self.Ym = list(Ym) if Ym else [0]*10
        self.T2 = list(T2) if T2 else [0]*10

def ge_zero():
    return GE(FE_ZERO[:], FE_ONE[:], FE_ONE[:], FE_ZERO[:])

def ge_tobytes(h):
    recip = [0]*10
    fe_invert(recip, h.Z)
    x = fe_mul(h.X, recip)
    y = fe_mul(h.Y, recip)
    s = bytearray(fe_tobytes(y))
    s[31] ^= fe_isodd(x) << 7
    return bytes(s)

def ge_frombytes_neg_vartime(s):
    h = GE()
    h.Y = fe_frombytes(s)
    h.Z = FE_ONE[:]
    h.T = fe_sq(h.Y)
    h.X = fe_mul(h.T, FE_D)
    h.T = fe_sub(h.T, h.Z)
    h.X = fe_add(h.X, h.Z)
    h.X = fe_mul(h.T, h.X)
    isr = [0]*10
    is_square = invsqrt(isr, h.X)
    if not is_square:
        return None, -1
    h.X = fe_mul(h.T, isr)
    if fe_isodd(h.X) == (s[31] >> 7):
        h.X = fe_neg(h.X)
    h.T = fe_mul(h.X, h.Y)
    # negate: the function returns -s (negated point)
    h.X = fe_neg(h.X)
    h.T = fe_neg(h.T)
    return h, 0

def ge_cache(c, p):
    c.Yp = fe_add(p.Y, p.X)
    c.Ym = fe_sub(p.Y, p.X)
    c.Z  = list(p.Z)
    c.T2 = fe_mul(p.T, FE_D2)

def ge_add(s, p, q):
    a = fe_mul(fe_add(p.Y, p.X), q.Yp)
    b = fe_mul(fe_sub(p.Y, p.X), q.Ym)
    s.Y = fe_add(a, b)
    s.X = fe_sub(a, b)
    s.Z = fe_mul(fe_add(p.Z, p.Z), q.Z)
    s.T = fe_mul(p.T, q.T2)
    a = fe_add(s.Z, s.T)
    b = fe_sub(s.Z, s.T)
    s.T = fe_mul(s.X, s.Y)
    s.X = fe_mul(s.X, b)
    s.Y = fe_mul(s.Y, a)
    s.Z = fe_mul(a, b)

def ge_sub(s, p, q):
    neg = GE_CACHED(fe_copy(q.Ym), fe_copy(q.Yp), fe_copy(q.Z), fe_neg(q.T2))
    ge_add(s, p, neg)

def ge_madd(s, p, q, a, b):
    a2 = fe_add(p.Y, p.X)
    b2 = fe_sub(p.Y, p.X)
    a2 = fe_mul(a2, q.Yp)
    b2 = fe_mul(b2, q.Ym)
    s.Y = fe_add(a2, b2)
    s.X = fe_sub(a2, b2)
    s.Z = fe_add(p.Z, p.Z)
    s.T = fe_mul(p.T, q.T2)
    a2 = fe_add(s.Z, s.T)
    b2 = fe_sub(s.Z, s.T)
    s.T = fe_mul(s.X, s.Y)
    s.X = fe_mul(s.X, b2)
    s.Y = fe_mul(s.Y, a2)
    s.Z = fe_mul(a2, b2)

def ge_msub(s, p, q, a, b):
    neg = GE_PRECOMP(fe_copy(q.Ym), fe_copy(q.Yp), fe_neg(q.T2))
    ge_madd(s, p, neg, a, b)

def ge_double(s, p, q):
    q.X = fe_sq(p.X)
    q.Y = fe_sq(p.Y)
    q.Z = fe_sq(p.Z)
    q.Z = fe_mul_small(q.Z, 2)
    q.T = fe_add(p.X, p.Y)
    s.T = fe_sq(q.T)
    q.T = fe_add(q.Y, q.X)
    q.Y = fe_sub(q.Y, q.X)
    s.X = fe_sub(s.T, q.T)
    q.Z = fe_sub(q.Z, q.Y)
    s.X = fe_mul(s.X, q.Z)
    s.Y = fe_mul(q.T, q.Y)
    s.Z = fe_mul(q.Y, q.Z)
    s.T = fe_mul(s.X, q.T)

# ========================= SLIDING WINDOW =========================

def scalar_bit(s, i):
    if i < 0:
        return 0
    return (s[i >> 3] >> (i & 7)) & 1

def slide_init(scalar):
    i = 252
    while i > 0 and scalar_bit(scalar, i) == 0:
        i -= 1
    return {'next_check': i + 1, 'next_index': -1, 'next_digit': -1}

def slide_step(ctx, width, i, scalar):
    if i == ctx['next_check']:
        if scalar_bit(scalar, i) == scalar_bit(scalar, i - 1):
            ctx['next_check'] -= 1
        else:
            w = min(width, i + 1)
            v = -(scalar_bit(scalar, i) << (w-1))
            for j in range(w-1):
                v += scalar_bit(scalar, i-(w-1)+j) << j
            v += scalar_bit(scalar, i-w)
            lsb = v & (-v)
            s = (((lsb & 0xAA) != 0) << 0) | (((lsb & 0xCC) != 0) << 1) | (((lsb & 0xF0) != 0) << 2)
            ctx['next_index'] = i - (w-1) + s
            ctx['next_digit'] = v >> s
            ctx['next_check'] -= w
    return ctx['next_digit'] if i == ctx['next_index'] else 0

# ========================= BASE POINT TABLES =========================

B_WINDOW = [
    GE_PRECOMP([25967493,-14356035,29566456,3660896,-12694345,4014787,27544626,-11754271,-6079156,2047605],
               [-12545711,934262,-2722910,3049990,-727428,9406986,12720692,5043384,19500929,-15469378],
               [-8738181,4489570,9688441,-14785194,10184609,-12363380,29287919,11864899,-24514362,-4438546]),
    GE_PRECOMP([15636291,-9688557,24204773,-7912398,616977,-16685262,27787600,-14772189,28944400,-1550024],
               [16568933,4717097,-11556148,-1102322,15682896,-11807043,16354577,-11775962,7689662,11199574],
               [30464156,-5976125,-11779434,-15670865,23220365,15915852,7512774,10017326,-17749093,-9920357]),
    GE_PRECOMP([10861363,11473154,27284546,1981175,-30064349,12577861,32867885,14515107,-15438304,10819380],
               [4708026,6336745,20377586,9066809,-11272109,6594696,-25653668,12483688,-12668491,5581306],
               [19563160,16186464,-29386857,4097519,10237984,-4348115,28542350,13850243,-23678021,-15815942]),
    GE_PRECOMP([5153746,9909285,1723747,-2777874,30523605,5516873,19480852,5230134,-23952439,-15175766],
               [-30269007,-3463509,7665486,10083793,28475525,1649722,20654025,16520125,30598449,7715701],
               [28881845,14381568,9657904,3680757,-20181635,7843316,-31400660,1370708,29794553,-1409300]),
    GE_PRECOMP([-22518993,-6692182,14201702,-8745502,-23510406,8844726,18474211,-1361450,-13062696,13821877],
               [-6455177,-7839871,3374702,-4740862,-27098617,-10571707,31655028,-7212327,18853322,-14220951],
               [4566830,-12963868,-28974889,-12240689,-7602672,-2830569,-8514358,-10431137,2207753,-3209784]),
    GE_PRECOMP([-25154831,-4185821,29681144,7868801,-6854661,-9423865,-12437364,-663000,-31111463,-16132436],
               [25576264,-2703214,7349804,-11814844,16472782,9300885,3844789,15725684,171356,6466918],
               [23103977,13316479,9739013,-16149481,817875,-15038942,8965339,-14088058,-30714912,16193877]),
    GE_PRECOMP([-33521811,3180713,-2394130,14003687,-16903474,-16270840,17238398,4729455,-18074513,9256800],
               [-25182317,-4174131,32336398,5036987,-21236817,11360617,22616405,9761698,-19827198,630305],
               [-13720693,2639453,-24237460,-7406481,9494427,-5774029,-6554551,-15960994,-2449256,-14291300]),
    GE_PRECOMP([-3151181,-5046075,9282714,6866145,-31907062,-863023,-18940575,15033784,25105118,-7894876],
               [-24326370,15950226,-31801215,-14592823,-11662737,-5090925,1573892,-2625887,2198790,-15804619],
               [-3099351,10324967,-2241613,7453183,-5446979,-2735503,-13812022,-16236442,-32461234,-12290683]),
]

B_COMB_LOW = [
    GE_PRECOMP([-6816601,-2324159,-22559413,124364,18015490,8373481,19993724,1979872,-18549925,9085059],
               [10306321,403248,14839893,9633706,8463310,-8354981,-14305673,14668847,26301366,2818560],
               [-22701500,-3210264,-13831292,-2927732,-16326337,-14016360,12940910,177905,12165515,-2397893]),
    GE_PRECOMP([-12282262,-7022066,9920413,-3064358,-32147467,2927790,22392436,-14852487,2719975,16402117],
               [-7236961,-4729776,2685954,-6525055,-24242706,-15940211,-6238521,14082855,10047669,12228189],
               [-30495588,-12893761,-11161261,3539405,-11502464,16491580,-27286798,-15030530,-7272871,-15934455]),
    GE_PRECOMP([17650926,582297,-860412,-187745,-12072900,-10683391,-20352381,15557840,-31072141,-5019061],
               [-6283632,-2259834,-4674247,-4598977,-4089240,12435688,-31278303,1060251,6256175,10480726],
               [-13871026,2026300,-21928428,-2741605,-2406664,-8034988,7355518,15733500,-23379862,7489131]),
    GE_PRECOMP([6883359,695140,23196907,9644202,-33430614,11354760,-20134606,6388313,-8263585,-8491918],
               [-7716174,-13605463,-13646110,14757414,-19430591,-14967316,10359532,-11059670,-21935259,12082603],
               [-11253345,-15943946,10046784,5414629,24840771,8086951,-6694742,9868723,15842692,-16224787]),
    GE_PRECOMP([9639399,11810955,-24007778,-9320054,3912937,-9856959,996125,-8727907,-8919186,-14097242],
               [7248867,14468564,25228636,-8795035,14346339,8224790,6388427,-7181107,6468218,-8720783],
               [15513115,15439095,7342322,-10157390,18005294,-7265713,2186239,4884640,10826567,7135781]),
    GE_PRECOMP([-14204238,5297536,-5862318,-6004934,28095835,4236101,-14203318,1958636,-16816875,3837147],
               [-5511166,-13176782,-29588215,12339465,15325758,-15945770,-8813185,11075932,-19608050,-3776283],
               [11728032,9603156,-4637821,-5304487,-7827751,2724948,31236191,-16760175,-7268616,14799772]),
    GE_PRECOMP([-28842672,4840636,-12047946,-9101456,-1445464,381905,-30977094,-16523389,1290540,12798615],
               [27246947,-10320914,14792098,-14518944,5302070,-8746152,-3403974,-4149637,-27061213,10749585],
               [25572375,-6270368,-15353037,16037944,1146292,32198,23487090,9585613,24714571,-1418265]),
    GE_PRECOMP([19844825,282124,-17583147,11004019,-32004269,-2716035,6105106,-1711007,-21010044,14338445],
               [8027505,8191102,-18504907,-12335737,25173494,-5923905,15446145,7483684,-30440441,10009108],
               [-14134701,-4174411,10246585,-14677495,33553567,-14012935,23366126,15080531,-7969992,7663473]),
]

B_COMB_HIGH = [
    GE_PRECOMP([33055887,-4431773,-521787,6654165,951411,-6266464,-5158124,6995613,-5397442,-6985227],
               [4014062,6967095,-11977872,3960002,8001989,5130302,-2154812,-1899602,-31954493,-16173976],
               [16271757,-9212948,23792794,731486,-25808309,-3546396,6964344,-4767590,10976593,10050757]),
    GE_PRECOMP([2533007,-4288439,-24467768,-12387405,-13450051,14542280,12876301,13893535,15067764,8594792],
               [20073501,-11623621,3165391,-13119866,13188608,-11540496,-10751437,-13482671,29588810,2197295],
               [-1084082,11831693,6031797,14062724,14748428,-8159962,-20721760,11742548,31368706,13161200]),
    GE_PRECOMP([2050412,-6457589,15321215,5273360,25484180,124590,-18187548,-7097255,-6691621,-14604792],
               [9938196,2162889,-6158074,-1711248,4278932,-2598531,-22865792,-7168500,-24323168,11746309],
               [-22691768,-14268164,5965485,9383325,20443693,5854192,28250679,-1381811,-10837134,13717818]),
    GE_PRECOMP([-8495530,16382250,9548884,-4971523,-4491811,-3902147,6182256,-12832479,26628081,10395408],
               [27329048,-15853735,7715764,8717446,-9215518,-14633480,28982250,-5668414,4227628,242148],
               [-13279943,-7986904,-7100016,8764468,-27276630,3096719,29678419,-9141299,3906709,11265498]),
    GE_PRECOMP([11918285,15686328,-17757323,-11217300,-27548967,4853165,-27168827,6807359,6871949,-1075745],
               [-29002610,13984323,-27111812,-2713442,28107359,-13266203,6155126,15104658,3538727,-7513788],
               [14103158,11233913,-33165269,9279850,31014152,4335090,-1827936,4590951,13960841,12787712]),
    GE_PRECOMP([1469134,-16738009,33411928,13942824,8092558,-8778224,-11165065,1437842,22521552,-2792954],
               [31352705,-4807352,-25327300,3962447,12541566,-9399651,-27425693,7964818,-23829869,5541287],
               [-25732021,-6864887,23848984,3039395,-9147354,6022816,-27421653,10590137,25309915,-1584678]),
    GE_PRECOMP([-22951376,5048948,31139401,-190316,-19542447,-626310,-17486305,-16511925,-18851313,-12985140],
               [-9684890,14681754,30487568,7717771,-10829709,9630497,30290549,-10531496,-27798994,-13812825],
               [5827835,16097107,-24501327,12094619,7413972,11447087,28057551,-1793987,-14056981,4359312]),
    GE_PRECOMP([26323183,2342588,-21887793,-1623758,-6062284,2107090,-28724907,9036464,-19618351,-13055189],
               [-29697200,14829398,-4596333,14220089,-30022969,2955645,12094100,-13693652,-5941445,7047569],
               [-3201977,14413268,-12058324,-16417589,-9035655,-7224648,9258160,1399236,30397584,-5684634]),
]

def lookup_add(p, comb, scalar, i):
    teeth = (scalar_bit(scalar, i) +
             (scalar_bit(scalar, i + 32) << 1) +
             (scalar_bit(scalar, i + 64) << 2) +
             (scalar_bit(scalar, i + 96) << 3))
    high = teeth >> 3
    index = (teeth ^ (high - 1)) & 7
    tmp_c = GE_PRECOMP()
    for j in range(8):
        select = 1 & (((j ^ index) - 1) >> 8)
        tmp_c.Yp = fe_ccopy(tmp_c.Yp, comb[j].Yp, select)
        tmp_c.Ym = fe_ccopy(tmp_c.Ym, comb[j].Ym, select)
        tmp_c.T2 = fe_ccopy(tmp_c.T2, comb[j].T2, select)
    tmp_a = fe_neg(tmp_c.T2)
    # swap T2, Yp/Ym based on high
    mask = -(high ^ 1)
    t2_masked = tmp_c.T2[:]
    for k in range(10):
        t2_masked[k] = tmp_c.T2[k] ^ ((tmp_c.T2[k] ^ tmp_a[k]) & mask)
    yp_masked = tmp_c.Yp[:]
    ym_masked = tmp_c.Ym[:]
    for k in range(10):
        yp_masked[k] = tmp_c.Yp[k] ^ ((tmp_c.Yp[k] ^ tmp_c.Ym[k]) & mask)
        ym_masked[k] = tmp_c.Ym[k] ^ ((tmp_c.Yp[k] ^ tmp_c.Ym[k]) & mask)
    tmp_c.T2 = t2_masked
    tmp_c.Yp = yp_masked
    tmp_c.Ym = ym_masked
    a = [0]*10
    b = [0]*10
    ge_madd(p, p, tmp_c, a, b)

def ge_scalarmult_base(scalar):
    half_mod_L = bytes([247,233,122,46,141,49,9,44,107,206,123,81,239,124,111,10,
                        0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,8])
    half_ones = bytes([142,74,204,70,186,24,118,107,184,231,190,57,250,173,119,99,
                       255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,7])
    s_scalar = bytearray(32)
    mul_add_into(s_scalar, scalar, half_mod_L, half_ones)
    s_scalar = bytes(s_scalar)
    p = ge_zero()
    tmp_a = [0]*10
    tmp_b = [0]*10
    tmp_c = GE_PRECOMP(FE_ONE[:], FE_ONE[:], FE_ZERO[:])
    tmp_d = GE()
    lookup_add(p, B_WINDOW, s_scalar, 31)
    lookup_add(p, B_COMB_HIGH, s_scalar, 31 + 128)
    for i in range(30, -1, -1):
        ge_double(p, p, tmp_d)
        lookup_add(p, B_WINDOW, s_scalar, i)
        lookup_add(p, B_COMB_HIGH, s_scalar, i + 128)
    return p

# ========================= SCALAR ARITHMETIC MOD L =========================

L_WORDS = [0x5cf5d3ed, 0x5812631a, 0xa2f79cd6, 0x14def9de, 0, 0, 0, 0x10000000]
L_BYTES = bytes([0xeb,0xd3,0xf5,0x5c,0x1a,0x63,0x12,0x58,
                  0xd6,0x9c,0xf7,0xa2,0xde,0xf9,0xde,0x14,
                  0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
                  0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x10])

def _mod_l_multiply(p, a, b):
    for i in range(16):
        p[i] = 0
    for i in range(8):
        carry = 0
        for j in range(8):
            carry += p[i+j] + a[i] * b[j]
            p[i+j] = carry & 0xFFFFFFFF
            carry >>= 32
        p[i+8] = carry & 0xFFFFFFFF

def _is_above_l(x):
    carry = 1
    for i in range(8):
        carry += x[i] + (0xFFFFFFFF ^ L_WORDS[i])
        carry >>= 32
    return carry

def _remove_l(r, x):
    c = _is_above_l(x)
    mask = (~c + 1) & 0xFFFFFFFF
    carry = c
    for i in range(8):
        carry += x[i] + ((0xFFFFFFFF ^ L_WORDS[i]) & mask)
        r[i] = carry & 0xFFFFFFFF
        carry >>= 32

def _mod_l(reduced, x16):
    barrett_r = [0x0a2c131b,0xed9ce5a3,0x086329a7,0x2106215d,
                 0xffffffeb,0xffffffff,0xffffffff,0xffffffff,0xf]
    xr = [0]*25
    for i in range(9):
        carry = 0
        for j in range(16):
            carry += xr[i+j] + barrett_r[i] * x16[j]
            xr[i+j] = carry & 0xFFFFFFFF
            carry >>= 32
        xr[i+16] = carry & 0xFFFFFFFF
    for i in range(8):
        xr[i] = 0
    for i in range(8):
        carry = 0
        for j in range(8 - i):
            carry += xr[i+j] + xr[i+16] * L_WORDS[j]
            xr[i+j] = carry & 0xFFFFFFFF
            carry >>= 32
    carry = 1
    for i in range(8):
        carry += x16[i] + (0xFFFFFFFF ^ xr[i])
        xr[i] = carry & 0xFFFFFFFF
        carry >>= 32
    _remove_l(xr, xr)
    for i in range(8):
        struct.pack_into('<I', reduced, i*4, xr[i])

def crypto_eddsa_reduce(reduced, expanded):
    x = [0]*16
    for i in range(16):
        x[i] = load32_le(expanded[i*4:(i+1)*4])
    _mod_l(reduced, x)

def mul_add_into(r, a, b, c):
    A = [0]*8
    B = [0]*8
    for i in range(8):
        A[i] = load32_le(a[i*4:(i+1)*4])
        B[i] = load32_le(b[i*4:(i+1)*4])
    p = [0]*16
    for i in range(8):
        p[i] = load32_le(c[i*4:(i+1)*4])
    _mod_l_multiply(p, A, B)
    _mod_l(r, p)

def crypto_eddsa_mul_add(r, a, b, c):
    ra = bytearray(32)
    mul_add_into(ra, a, b, c)
    return bytes(ra)

def crypto_eddsa_trim_scalar(scalar):
    s = bytearray(scalar)
    s[0] &= 248
    s[31] &= 127
    s[31] |= 64
    return bytes(s)

def crypto_eddsa_scalarbase(scalar):
    P = ge_scalarmult_base(scalar)
    return ge_tobytes(P)

def hash_reduce(msg_parts):
    h = blake2b_full(64, b''.join(msg_parts))
    reduced = bytearray(32)
    crypto_eddsa_reduce(reduced, h)
    return bytes(reduced)

# ========================= EDDSA SIGN/CHECK =========================

def eddsa_key_pair(seed):
    a = blake2b_full(64, seed)
    a_trimmed = crypto_eddsa_trim_scalar(a[:32])
    public = crypto_eddsa_scalarbase(a_trimmed)
    secret = bytearray(64)
    secret[:32] = seed
    secret[32:] = public
    return bytes(secret), public

def eddsa_sign(secret_key, message):
    a = blake2b_full(64, secret_key[:32])
    a = crypto_eddsa_trim_scalar(a[:32])
    prefix = a[32:64] if len(a) > 32 else bytes(32)
    r = hash_reduce([secret_key[32:64] if len(secret_key) >= 64 else bytes(32), message])
    R = crypto_eddsa_scalarbase(r)
    h = hash_reduce([R, secret_key[32:64] if len(secret_key) >= 64 else bytes(32), message])
    sig = bytearray(64)
    sig[:32] = R
    s_bytes = crypto_eddsa_mul_add(h, a[:32], r)
    sig[32:] = s_bytes
    return bytes(sig)

def eddsa_check(signature, public_key, message):
    R = signature[:32]
    s = signature[32:]
    h = hash_reduce([R, public_key, message])
    return _check_equation(signature, public_key, h)

def _check_equation(signature, public_key, h):
    minus_A, r1 = ge_frombytes_neg_vartime(public_key)
    if r1 != 0:
        return -1
    minus_R, r2 = ge_frombytes_neg_vartime(signature[:32])
    if r2 != 0:
        return -1
    s = signature[32:]
    s_words = [load32_le(s[i*4:(i+1)*4]) for i in range(8)]
    if _is_above_l(s_words):
        return -1
    P_W_WIDTH = 3
    B_W_WIDTH = 5
    P_W_SIZE = 1 << (P_W_WIDTH - 2)
    minus_A2 = GE()
    tmp_ge = GE()
    ge_double(minus_A2, minus_A, tmp_ge)
    lutA = [GE_CACHED() for _ in range(P_W_SIZE)]
    ge_cache(lutA[0], minus_A)
    tmp_cached = GE_CACHED()
    for i_idx in range(1, P_W_SIZE):
        ge_add(tmp_ge, minus_A2, lutA[i_idx-1])
        ge_cache(lutA[i_idx], tmp_ge)
    h_slide = slide_init(h)
    s_slide = slide_init(s)
    i = max(h_slide['next_check'], s_slide['next_check'])
    sum_point = ge_zero()
    while i >= 0:
        tmp_ge2 = GE()
        ge_double(sum_point, sum_point, tmp_ge2)
        h_digit = slide_step(h_slide, P_W_WIDTH, i, h)
        s_digit = slide_step(s_slide, B_W_WIDTH, i, s)
        if h_digit > 0:
            ge_add(sum_point, sum_point, lutA[h_digit // 2])
        elif h_digit < 0:
            ge_sub(sum_point, sum_point, lutA[-h_digit // 2])
        t1 = [0]*10
        t2 = [0]*10
        if s_digit > 0:
            ge_madd(sum_point, sum_point, B_WINDOW[s_digit // 2], t1, t2)
        elif s_digit < 0:
            ge_msub(sum_point, sum_point, B_WINDOW[-s_digit // 2], t1, t2)
        i -= 1
    cached = GE_CACHED()
    ge_cache(cached, minus_R)
    ge_add(sum_point, sum_point, cached)
    tmp_ge3 = GE()
    ge_double(sum_point, sum_point, tmp_ge3)
    ge_double(sum_point, sum_point, tmp_ge3)
    ge_double(sum_point, sum_point, tmp_ge3)
    check = ge_tobytes(sum_point)
    zero_point = bytearray(32)
    zero_point[0] = 1
    return crypto_verify32(check, bytes(zero_point))

# ========================= ED25519 (SHA-512 based) =========================

DOMAIN_SEP_SIG = b"SigEd25519 no Ed25519 collisions\x01"
DOMAIN_SEP_PH_SIG = b"SigEd25519 no Ed25519 collisions\x02"

def ed25519_key_pair(seed):
    a = sha512(seed)
    a = bytearray(a)
    a[0] &= 248
    a[31] &= 127
    a[31] |= 64
    public = crypto_eddsa_scalarbase(a[:32])
    secret = bytearray(64)
    secret[:32] = seed
    secret[32:] = public
    return bytes(secret), public

def ed25519_sign(secret_key, message):
    a = sha512(secret_key[:32])
    a = bytearray(a)
    a[0] &= 248
    a[31] &= 127
    a[31] |= 64
    prefix = sha512(secret_key[:32])[32:64]
    r = hash_reduce([prefix, message])
    R = crypto_eddsa_scalarbase(r)
    h = hash_reduce([R, secret_key[32:64], message])
    sig = bytearray(64)
    sig[:32] = R
    s_bytes = crypto_eddsa_mul_add(h, a[:32], r)
    sig[32:] = s_bytes
    return bytes(sig)

def ed25519_check(signature, public_key, message):
    R = signature[:32]
    h = hash_reduce([R, public_key, message])
    return _check_equation(signature, public_key, h)

def ed25519_ph_sign(secret_key, hash_val):
    a = sha512(secret_key[:32])
    a = bytearray(a)
    a[0] &= 248
    a[31] &= 127
    a[31] |= 64
    prefix = sha512(secret_key[:32])[32:64]
    r = hash_reduce([prefix, hash_val])
    R = crypto_eddsa_scalarbase(r)
    h_raw = DOMAIN_SEP_PH_SIG + bytes([64]) + secret_key[32:64] + R + hash_val
    h_bytes = sha512(h_raw)
    h = bytearray(32)
    crypto_eddsa_reduce(h, h_bytes)
    sig = bytearray(64)
    sig[:32] = R
    s_bytes = crypto_eddsa_mul_add(h, a[:32], r)
    sig[32:] = s_bytes
    return bytes(sig)

def ed25519_ph_check(signature, public_key, hash_val):
    R = signature[:32]
    h_raw = DOMAIN_SEP_PH_SIG + bytes([64]) + public_key + R + hash_val
    h_bytes = sha512(h_raw)
    h = bytearray(32)
    crypto_eddsa_reduce(h, h_bytes)
    return _check_equation(signature, public_key, h)

# ========================= X25519 =========================

def x25519_scalarmult(scalar, point, nb_bits):
    x1 = fe_frombytes(point)
    x2 = fe_1()
    z2 = fe_0()
    x3 = list(x1)
    z3 = fe_1()
    swap = 0
    for pos in range(nb_bits - 1, -1, -1):
        b = scalar_bit(scalar, pos)
        swap ^= b
        if swap:
            x2, x3 = x3, x2
            z2, z3 = z3, z2
        swap = b
        t0 = fe_sub(x3, z3)
        t1 = fe_sub(x2, z2)
        x2 = fe_add(x2, z2)
        z2 = fe_add(x3, z3)
        z3 = fe_mul(t0, x2)
        z2 = fe_mul(z2, t1)
        t0 = fe_sq(t1)
        t1 = fe_sq(x2)
        x3 = fe_add(z3, z2)
        z2 = fe_sub(z3, z2)
        x2 = fe_mul(t1, t0)
        t1 = fe_sub(t1, t0)
        z2 = fe_sq(z2)
        z3 = fe_mul_small(t1, 121666)
        x3 = fe_sq(x3)
        t0 = fe_add(t0, z3)
        z3 = fe_mul(x1, z2)
        z2 = fe_mul(t1, t0)
    if swap:
        x2, x3 = x3, x2
        z2, z3 = z3, z2
    inv = [0]*10
    fe_invert(inv, z2)
    x2 = fe_mul(x2, inv)
    return fe_tobytes(x2)

def crypto_x25519(sk, pk):
    sk = crypto_eddsa_trim_scalar(sk)
    return x25519_scalarmult(sk, pk, 255)

def crypto_x25519_public_key(sk):
    sk = crypto_eddsa_trim_scalar(sk)
    return x25519_scalarmult(sk, bytes([9] + [0]*31), 255)

# ========================= X25519 DIRTY =========================

DIRTY_BASE_POINT = bytes([0xd8,0x86,0x1a,0xa2,0x78,0x7a,0xd9,0x26,
                          0x8b,0x74,0x74,0xb6,0x82,0xe3,0xbe,0xc3,
                          0xce,0x36,0x9a,0x1e,0x5e,0x31,0x47,0xa2,
                          0x6d,0x37,0x7c,0xfd,0x20,0xb5,0xdf,0x75])

def add_xl(s, x):
    mod8 = x & 7
    s_words = [load32_le(s[i*4:(i+1)*4]) for i in range(8)]
    carry = 0
    for i in range(8):
        carry += s_words[i] + L_WORDS[i] * mod8
        s_words[i] = carry & 0xFFFFFFFF
        carry >>= 32
    result = bytearray(32)
    for i in range(8):
        struct.pack_into('<I', result, i*4, s_words[i])
    return bytes(result)

def crypto_x25519_dirty_small(sk):
    scalar = crypto_eddsa_trim_scalar(sk)
    scalar = add_xl(scalar, sk[0])
    return x25519_scalarmult(scalar, DIRTY_BASE_POINT, 256)

def select_lop(x, k, cofactor):
    out = fe_0()
    out = fe_ccopy(out, k, (cofactor >> 1) & 1)
    out = fe_ccopy(out, x, (cofactor >> 0) & 1)
    tmp = fe_neg(out)
    out = fe_ccopy(out, tmp, (cofactor >> 2) & 1)
    return out

def crypto_x25519_dirty_fast(sk):
    scalar = crypto_eddsa_trim_scalar(sk)
    pk = ge_scalarmult_base(scalar)
    t1 = select_lop(FE_LOP_X, FE_SQRTM1, sk[0])
    t2 = select_lop(FE_LOP_Y, FE_ONE, sk[0] + 2)
    low_order_point = GE_PRECOMP()
    low_order_point.Yp = fe_add(t2, t1)
    low_order_point.Ym = fe_sub(t2, t1)
    low_order_point.T2 = fe_mul(fe_mul(t2, t1), FE_D2)
    a = [0]*10
    b = [0]*10
    ge_madd(pk, pk, low_order_point, a, b)
    t1 = fe_add(pk.Z, pk.Y)
    t2 = fe_sub(pk.Z, pk.Y)
    inv = [0]*10
    fe_invert(inv, t2)
    t1 = fe_mul(t1, inv)
    return fe_tobytes(t1)

# ========================= X25519 INVERSE =========================

def crypto_x25519_inverse(private_key, curve_point):
    scalar = crypto_eddsa_trim_scalar(private_key)
    m_scl_words = [0]*8
    tmp = [0]*16
    for i in range(8):
        tmp[i+8] = load32_le(scalar[i*4:(i+1)*4])
    scalar_out = bytearray(32)
    _mod_l(scalar_out, tmp)
    for i in range(8):
        m_scl_words[i] = load32_le(scalar_out[i*4:(i+1)*4])
    m_inv_words = [0x8d98951d, 0xd6ec3174, 0x737dcf70, 0xc6ef5bf4,
                   0xfffffffe, 0xffffffff, 0xffffffff, 0x0fffffff]
    k_words = [0x12547e1b, 0xd2b51da3, 0xfdba84ff, 0xb1a206f2,
               0xffa36bea, 0x14e75438, 0x6fe91836, 0x9db6c6f2]
    Lm2 = [0xeb,0xd3,0xf5,0x5c,0x1a,0x63,0x12,0x58,
           0xd6,0x9c,0xf7,0xa2,0xde,0xf9,0xde,0x14,
           0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
           0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x10]
    product = [0]*16
    for i in range(252, -1, -1):
        product = [0]*16
        _mod_l_multiply(product, m_inv_words, m_inv_words)
        m_inv_out = [0]*8
        _mod_l_redc(m_inv_out, product)
        m_inv_words = m_inv_out
        if scalar_bit(Lm2, i):
            product = [0]*16
            _mod_l_multiply(product, m_inv_words, m_scl_words)
            m_inv_out = [0]*8
            _mod_l_redc(m_inv_out, product)
            m_inv_words = m_inv_out
    product = [0]*8 + m_inv_words[:]
    inv_out = [0]*8
    _mod_l_redc(inv_out, product)
    scalar_result = bytearray(32)
    for i in range(8):
        struct.pack_into('<I', scalar_result, i*4, inv_out[i])
    scalar_result = bytearray(add_xl(scalar_result, scalar_result[0] * 3))
    return x25519_scalarmult(scalar_result, curve_point, 256)

def _mod_l_redc(u, x):
    k_words = [0x12547e1b, 0xd2b51da3, 0xfdba84ff, 0xb1a206f2,
               0xffa36bea, 0x14e75438, 0x6fe91836, 0x9db6c6f2]
    s = [0]*8
    for i in range(8):
        carry = 0
        for j in range(8 - i):
            carry += s[i+j] + x[i] * k_words[j]
            s[i+j] = carry & 0xFFFFFFFF
            carry >>= 32
    t = [0]*16
    _mod_l_multiply(t, s, L_WORDS)
    carry = 0
    for i in range(16):
        carry += t[i] + x[i]
        t[i] = carry & 0xFFFFFFFF
        carry >>= 32
    _remove_l(u, t[8:])

# ========================= ELLIGATOR 2 =========================

def crypto_elligator_map(hidden):
    r = fe_frombytes_mask(hidden, 2)
    r = fe_sq(r)
    t1 = fe_add(r, r)
    u = fe_add(t1, FE_ONE)
    t2 = fe_sq(u)
    t3 = fe_mul(FE_A2, t1)
    t3 = fe_sub(t3, t2)
    t3 = fe_mul(t3, FE_A)
    t1 = fe_mul(t2, u)
    t1 = fe_mul(t3, t1)
    isr = [0]*10
    is_sq = invsqrt(isr, t1)
    u_val = fe_mul(r, FE_UFACTOR)
    u_val = fe_ccopy(u_val, FE_ONE, is_sq)
    t1 = fe_sq(isr)
    u_val = fe_mul(u_val, FE_A)
    u_val = fe_mul(u_val, t3)
    u_val = fe_mul(u_val, t2)
    u_val = fe_mul(u_val, t1)
    u_val = fe_neg(u_val)
    return fe_tobytes(u_val)

def crypto_elligator_rev(public_key, tweak):
    t1 = fe_frombytes(public_key)
    t2 = fe_add(t1, FE_A)
    t3 = fe_mul(t1, t2)
    t3 = fe_mul_small(t3, -2)
    isr = [0]*10
    is_sq = invsqrt(isr, t3)
    if not is_sq:
        return None, -1
    t1_c = fe_copy(t1) if (tweak & 1) else t2
    t3 = fe_mul(t1_c, isr)
    t1 = fe_mul_small(t3, 2)
    t2 = fe_neg(t3)
    t3 = fe_ccopy(t3, t2, fe_isodd(t1))
    hidden = fe_tobytes(t3)
    hidden = bytearray(hidden)
    hidden[31] |= tweak & 0xC0
    return bytes(hidden), 0

def crypto_elligator_key_pair(seed):
    pk = bytearray(32)
    buf = bytearray(64)
    buf[32:64] = seed
    zero_nonce = bytes(8)
    while True:
        ct, _ = chacha20_djb(bytes(buf[32:64]), 64, buf[32:64], zero_nonce, 0)
        buf[:32] = ct[:32]
        buf[32:64] = ct[32:64]
        pk = bytearray(crypto_x25519_dirty_fast(bytes(buf[:32])))
        result, _ = crypto_elligator_rev(bytes(pk), buf[32])
        if result is not None:
            break
    return result, bytes(buf[:32])

# ========================= AEAD =========================

class AEAD_CTX:
    def __init__(self):
        self.key = b'\x00' * 32
        self.nonce = b'\x00' * 8
        self.counter = 0

def lock_auth(auth_key, ad, cipher_text):
    sizes = store64_le(len(ad)) + store64_le(len(cipher_text))
    poly_key = auth_key[:32]
    msg = ad + ZERO128[:gap(len(ad),16)] + cipher_text + ZERO128[:gap(len(cipher_text),16)] + sizes
    return poly1305(msg, poly_key)

def crypto_aead_init_x(ctx, key, nonce):
    ctx.key = chacha20_h(key, nonce[:16])
    ctx.nonce = nonce[16:24]
    ctx.counter = 0

def crypto_aead_init_djb(ctx, key, nonce):
    ctx.key = key
    ctx.nonce = nonce
    ctx.counter = 0

def crypto_aead_init_ietf(ctx, key, nonce):
    ctx.key = key
    ctx.nonce = nonce[4:12]
    ctx.counter = load32_le(nonce[0:4]) << 32

def crypto_aead_write(ctx, ad, plain_text):
    auth_key_full, _ = chacha20_djb(None, 64, ctx.key, ctx.nonce, ctx.counter)
    cipher_text, _ = chacha20_djb(plain_text, len(plain_text), ctx.key, ctx.nonce, ctx.counter + 1)
    mac = lock_auth(auth_key_full, ad, cipher_text)
    ctx.key = auth_key_full[32:64]
    return cipher_text, mac

def crypto_aead_read(ctx, ad, cipher_text, mac):
    auth_key_full, _ = chacha20_djb(None, 64, ctx.key, ctx.nonce, ctx.counter)
    real_mac = lock_auth(auth_key_full, ad, cipher_text)
    if crypto_verify16(mac, real_mac) != 0:
        return None, -1
    plain_text, _ = chacha20_djb(cipher_text, len(cipher_text), ctx.key, ctx.nonce, ctx.counter + 1)
    ctx.key = auth_key_full[32:64]
    return plain_text, 0

def crypto_aead_lock(key, nonce, ad, plain_text):
    ctx = AEAD_CTX()
    crypto_aead_init_x(ctx, key, nonce)
    ct, mac = crypto_aead_write(ctx, ad, plain_text)
    return ct, mac

def crypto_aead_unlock(key, nonce, ad, cipher_text, mac):
    ctx = AEAD_CTX()
    crypto_aead_init_x(ctx, key, nonce)
    pt, r = crypto_aead_read(ctx, ad, cipher_text, mac)
    return pt, r

# ========================= ARGON2 =========================

def _argon2_g_rounds(b):
    def G(a, b, c, d):
        a += b + ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF) * 2)
        d ^= a; d = rotr64(d, 32)
        c += d + ((c & 0xFFFFFFFF) * (d & 0xFFFFFFFF) * 2)
        b ^= c; b = rotr64(b, 24)
        a += b + ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF) * 2)
        d ^= a; d = rotr64(d, 16)
        c += d + ((c & 0xFFFFFFFF) * (d & 0xFFFFFFFF) * 2)
        b ^= c; b = rotr64(b, 63)
        return a, b, c, d
    def ROUND(v0,v1,v2,v3,v4,v5,v6,v7,v8,v9,v10,v11,v12,v13,v14,v15):
        v0,v4,v8,v12 = G(v0,v4,v8,v12)
        v1,v5,v9,v13 = G(v1,v5,v9,v13)
        v2,v6,v10,v14 = G(v2,v6,v10,v14)
        v3,v7,v11,v15 = G(v3,v7,v11,v15)
        v0,v5,v10,v15 = G(v0,v5,v10,v15)
        v1,v6,v11,v12 = G(v1,v6,v11,v12)
        v2,v7,v8,v13 = G(v2,v7,v8,v13)
        v3,v4,v9,v14 = G(v3,v4,v9,v14)
        return v0,v1,v2,v3,v4,v5,v6,v7,v8,v9,v10,v11,v12,v13,v14,v15
    for i in range(0, 128, 16):
        v = [b[i+j] for j in range(16)]
        v = ROUND(*v)
        for j in range(16):
            b[i+j] = v[j]
    for i in range(0, 16, 2):
        v = [b[i+j*16] for j in range(8)] + [b[i+1+j*16] for j in range(8)]
        v = ROUND(*v)
        for j in range(8):
            b[i+j*16] = v[j]
            b[i+1+j*16] = v[j+8]

def _extended_hash(digest_size, input_data):
    r = ((digest_size + 31) >> 5) - 2
    h = blake2b_full(64, store32_le(digest_size) + input_data)
    i_val = 1
    in_off = 32
    out_off = 32
    out = bytearray(h)
    while i_val < r:
        new_h = blake2b_full(64, out[in_off:in_off+64])
        out.extend(new_h[32:64])
        i_val += 1
        in_off += 32
        out_off += 32
    remaining = digest_size - 32 * r
    new_h = blake2b_full(remaining, out[in_off:in_off+64])
    out.extend(new_h[:remaining])
    return bytes(out[:digest_size])

def _argon2_fill_blocks(algorithm, nb_passes, nb_lanes, segment_size, blocks):
    lane_size = segment_size * 4
    constant_time = (algorithm != 0)
    for p in range(nb_passes):
        for sl in range(3):
            pass_offset = 2 if (p == 0 and sl == 0) else 0
            if sl == 2 and algorithm == 2:
                constant_time = False
            for lane in range(nb_lanes):
                index_ctr = 1
                for block_idx in range(pass_offset, segment_size):
                    lane_offset = lane * lane_size
                    segment_start = lane_offset + sl * segment_size
                    current = segment_start + block_idx
                    if block_idx == 0 and sl == 0:
                        previous = lane_offset + lane_size - 1
                    else:
                        previous = segment_start + block_idx - 1
                    if constant_time or sl >= 2:
                        index_seed = blocks[previous][0]
                    else:
                        if block_idx == pass_offset or block_idx % 128 == 0:
                            index_block = [0] * 128
                            index_block[0] = p
                            index_block[1] = lane
                            index_block[2] = sl
                            index_block[3] = nb_lanes * lane_size
                            index_block[4] = nb_passes
                            index_block[5] = algorithm
                            index_block[6] = index_ctr
                            index_ctr += 1
                            tmp_ib = list(index_block)
                            _argon2_g_rounds(index_block)
                            for k in range(128):
                                index_block[k] ^= tmp_ib[k]
                            tmp_ib = list(index_block)
                            _argon2_g_rounds(index_block)
                            for k in range(128):
                                index_block[k] ^= tmp_ib[k]
                            index_seed = index_block[block_idx % 128]
                    next_slice = ((sl + 1) % 4) * segment_size
                    window_start = 0 if p == 0 else next_slice
                    nb_segments = sl if p == 0 else 3
                    if p == 0 and sl == 0:
                        ref_lane = lane
                    else:
                        ref_lane = (index_seed >> 32) % nb_lanes
                    window_size = nb_segments * segment_size
                    if ref_lane == lane:
                        window_size += block_idx - 1 if block_idx > 0 else 0
                    elif block_idx == 0:
                        window_size += 0xFFFFFFFF
                    j1 = index_seed & 0xFFFFFFFF
                    x = (j1 * j1) >> 32
                    y = (window_size * x) >> 32
                    z = (window_size - 1) - y
                    ref = (window_start + z) % lane_size
                    ref_index = ref_lane * lane_size + ref
                    if p == 0:
                        for k in range(128):
                            blocks[current][k] = blocks[previous][k] ^ blocks[ref_index][k]
                    else:
                        for k in range(128):
                            blocks[current][k] ^= blocks[previous][k] ^ blocks[ref_index][k]
                    tmp_blk = list(blocks[current])
                    _argon2_g_rounds(tmp_blk)
                    for k in range(128):
                        blocks[current][k] ^= tmp_blk[k]

def crypto_argon2(hash_size, password, salt, key, ad, nb_blocks, nb_passes, nb_lanes, algorithm):
    segment_size = nb_blocks // nb_lanes // 4
    lane_size = segment_size * 4
    actual_blocks = lane_size * nb_lanes
    blocks = [[0]*128 for _ in range(actual_blocks)]
    h0_input = b''
    h0_input += struct.pack('<I', nb_lanes)
    h0_input += struct.pack('<I', hash_size)
    h0_input += struct.pack('<I', actual_blocks)
    h0_input += struct.pack('<I', nb_passes)
    h0_input += struct.pack('<I', 0x13)
    h0_input += struct.pack('<I', algorithm)
    h0_input += struct.pack('<I', len(password))
    h0_input += password
    h0_input += struct.pack('<I', len(salt))
    h0_input += salt
    h0_input += struct.pack('<I', len(key))
    h0_input += key
    h0_input += struct.pack('<I', len(ad))
    h0_input += ad
    initial_hash = blake2b_full(64, h0_input)
    for l in range(nb_lanes):
        for i in range(2):
            ext_input = initial_hash + store32_le(i) + store32_le(l)
            block_bytes = _extended_hash(1024, ext_input)
            words = list(struct.unpack('<128Q', block_bytes))
            blocks[l * lane_size + i] = words
    _argon2_fill_blocks(algorithm, nb_passes, nb_lanes, segment_size, blocks)
    last = list(blocks[lane_size - 1])
    for l in range(1, nb_lanes):
        idx = (l + 1) * lane_size - 1
        for k in range(128):
            last[k] ^= blocks[idx][k]
    final_block = struct.pack('<128Q', *last)
    result = _extended_hash(hash_size, final_block)
    for i in range(actual_blocks):
        for j in range(128):
            blocks[i][j] = 0
    return result

# ========================= VERIFY / WIPE =========================

def crypto_verify16(a, b):
    return 0 if a[:16] == b[:16] else -1

def crypto_verify32(a, b):
    return 0 if a[:32] == b[:32] else -1

def crypto_verify64(a, b):
    return 0 if a[:64] == b[:64] else -1

def crypto_wipe(b):
    return b'\x00' * len(b)

# ========================= CLI DISPATCHER =========================

def main():
    func = read_line()
    if func is None:
        sys.exit(1)

    if func == 'crypto_verify16':
        a = hex_decode(read_line()); b = hex_decode(read_line())
        v = crypto_verify16(a, b)
        sys.stdout.write(f"{v & 0xFFFFFFFF:02x}:\n")
        sys.stdout.flush()

    elif func == 'crypto_verify32':
        a = hex_decode(read_line()); b = hex_decode(read_line())
        v = crypto_verify32(a, b)
        sys.stdout.write(f"{v & 0xFFFFFFFF:02x}:\n")
        sys.stdout.flush()

    elif func == 'crypto_verify64':
        a = hex_decode(read_line()); b = hex_decode(read_line())
        v = crypto_verify64(a, b)
        sys.stdout.write(f"{v & 0xFFFFFFFF:02x}:\n")
        sys.stdout.flush()

    elif func == 'crypto_wipe':
        buf = hex_decode(read_line())
        print_hex(crypto_wipe(buf))

    elif func == 'crypto_chacha20_h':
        key = hex_decode(read_line()); inp = hex_decode(read_line())
        print_hex(crypto_chacha20_h_cmd(key, inp))

    elif func == 'crypto_chacha20_djb':
        key = hex_decode(read_line()); nonce = hex_decode(read_line())
        plain = hex_decode(read_line()); ctr = hex_decode(read_line())
        ct, nc = crypto_chacha20_djb_cmd(key, nonce, plain, ctr)
        print_hex(ct); print_hex(nc)

    elif func == 'crypto_chacha20_ietf':
        key = hex_decode(read_line()); nonce = hex_decode(read_line())
        plain = hex_decode(read_line()); ctr = hex_decode(read_line())
        ct, nc = crypto_chacha20_ietf_cmd(key, nonce, plain, ctr)
        print_hex(ct); print_hex(nc)

    elif func == 'crypto_chacha20_x':
        key = hex_decode(read_line()); nonce = hex_decode(read_line())
        plain = hex_decode(read_line()); ctr = hex_decode(read_line())
        ct, nc = crypto_chacha20_x_cmd(key, nonce, plain, ctr)
        print_hex(ct); print_hex(nc)

    elif func == 'crypto_poly1305':
        key = hex_decode(read_line())
        msg = hex_decode(read_line())
        print_hex(poly1305(msg, key))

    elif func == 'crypto_blake2b':
        msg = hex_decode(read_line())
        print_hex(crypto_blake2b(msg))

    elif func == 'crypto_blake2b_keyed':
        msg = hex_decode(read_line())
        key = hex_decode(read_line())
        if len(key) > 64: key = key[:64]
        print_hex(crypto_blake2b_keyed(msg, key))

    elif func == 'crypto_sha512':
        msg = hex_decode(read_line())
        print_hex(sha512(msg))

    elif func == 'crypto_sha512_hmac':
        key = hex_decode(read_line())
        msg = hex_decode(read_line())
        print_hex(sha512_hmac(key, msg))

    elif func == 'crypto_sha512_hkdf':
        ikm = hex_decode(read_line())
        salt = hex_decode(read_line())
        info = hex_decode(read_line())
        okm_hex = read_line()
        okm_size = len(okm_hex) // 2
        print_hex(sha512_hkdf(okm_size, ikm, salt, info))

    elif func == 'crypto_argon2':
        algo = struct.unpack('<I', hex_decode(read_line()))[0]
        blocks = struct.unpack('<I', hex_decode(read_line()))[0]
        passes = struct.unpack('<I', hex_decode(read_line()))[0]
        lanes = struct.unpack('<I', hex_decode(read_line()))[0]
        password = hex_decode(read_line())
        salt = hex_decode(read_line())
        key = hex_decode(read_line())
        ad = hex_decode(read_line())
        hash_hex = read_line()
        hash_size = len(hash_hex) // 2
        print_hex(crypto_argon2(hash_size, password, salt, key, ad, blocks, passes, lanes, algo))

    elif func == 'crypto_x25519':
        sk = hex_decode(read_line()); pk = hex_decode(read_line())
        print_hex(crypto_x25519(sk, pk))

    elif func == 'crypto_x25519_public_key':
        sk = hex_decode(read_line())
        print_hex(crypto_x25519_public_key(sk))

    elif func == 'crypto_x25519_inverse':
        sk = hex_decode(read_line()); pt = hex_decode(read_line())
        print_hex(crypto_x25519_inverse(sk, pt))

    elif func == 'crypto_x25519_dirty_small':
        sk = hex_decode(read_line())
        print_hex(crypto_x25519_dirty_small(sk))

    elif func == 'crypto_x25519_dirty_fast':
        sk = hex_decode(read_line())
        print_hex(crypto_x25519_dirty_fast(sk))

    elif func == 'crypto_eddsa_key_pair':
        seed = hex_decode(read_line())
        sk, pk = eddsa_key_pair(seed)
        print_hex(sk); print_hex(pk)

    elif func == 'crypto_eddsa_sign':
        sk = hex_decode(read_line()); pk = hex_decode(read_line())
        msg = hex_decode(read_line())
        fat_sk = sk[:32] + pk
        print_hex(eddsa_sign(fat_sk, msg))

    elif func == 'crypto_eddsa_check':
        sig = hex_decode(read_line()); pk = hex_decode(read_line())
        msg = hex_decode(read_line())
        r = eddsa_check(sig, pk, msg)
        print_hex(bytes([r & 0xFF]))

    elif func == 'crypto_eddsa_trim_scalar':
        inp = hex_decode(read_line())
        print_hex(crypto_eddsa_trim_scalar(inp))

    elif func == 'crypto_eddsa_reduce':
        expanded = hex_decode(read_line())
        reduced = bytearray(32)
        crypto_eddsa_reduce(reduced, expanded)
        print_hex(bytes(reduced))

    elif func == 'crypto_eddsa_mul_add':
        a = hex_decode(read_line()); b = hex_decode(read_line()); c = hex_decode(read_line())
        print_hex(crypto_eddsa_mul_add(a, b, c))

    elif func == 'crypto_eddsa_scalarbase':
        scalar = hex_decode(read_line())
        print_hex(crypto_eddsa_scalarbase(scalar))

    elif func == 'crypto_eddsa_check_equation':
        sig = hex_decode(read_line()); pk = hex_decode(read_line()); h = hex_decode(read_line())
        r = _check_equation(sig, pk, h)
        print_hex(bytes([r & 0xFF]))

    elif func == 'crypto_ed25519_key_pair':
        seed = hex_decode(read_line())
        sk, pk = ed25519_key_pair(seed)
        print_hex(sk); print_hex(pk)

    elif func == 'crypto_ed25519_sign':
        sk = hex_decode(read_line()); pk = hex_decode(read_line())
        msg = hex_decode(read_line())
        fat_sk = sk[:32] + pk
        print_hex(ed25519_sign(fat_sk, msg))

    elif func == 'crypto_ed25519_check':
        sig = hex_decode(read_line()); pk = hex_decode(read_line())
        msg = hex_decode(read_line())
        r = ed25519_check(sig, pk, msg)
        print_hex(bytes([r & 0xFF]))

    elif func == 'crypto_ed25519_ph_sign':
        sk = hex_decode(read_line()); pk = hex_decode(read_line())
        hash_val = hex_decode(read_line())
        fat_sk = sk[:32] + pk
        print_hex(ed25519_ph_sign(fat_sk, hash_val))

    elif func == 'crypto_ed25519_ph_check':
        sig = hex_decode(read_line()); pk = hex_decode(read_line())
        hash_val = hex_decode(read_line())
        r = ed25519_ph_check(sig, pk, hash_val)
        print_hex(bytes([r & 0xFF]))

    elif func == 'crypto_elligator_map':
        hidden = hex_decode(read_line())
        print_hex(crypto_elligator_map(hidden))

    elif func == 'crypto_elligator_rev':
        point = hex_decode(read_line())
        tweak_hex = read_line()
        tweak = int(tweak_hex, 16) & 0xFF
        result, r = crypto_elligator_rev(point, tweak)
        if r == 0:
            print_hex(result)
        print_hex(bytes([r & 0xFF]))

    elif func == 'crypto_elligator_key_pair':
        seed = hex_decode(read_line())
        hidden, sk = crypto_elligator_key_pair(seed)
        print_hex(hidden); print_hex(sk)

    elif func == 'crypto_eddsa_to_x25519':
        eddsa = hex_decode(read_line())
        print_hex(crypto_eddsa_to_x25519(eddsa))

    elif func == 'crypto_x25519_to_eddsa':
        x = hex_decode(read_line())
        print_hex(crypto_x25519_to_eddsa(x))

    elif func == 'crypto_aead_init_x':
        key = hex_decode(read_line()); nonce = hex_decode(read_line())
        ctx = AEAD_CTX()
        crypto_aead_init_x(ctx, key, nonce)
        print_hex(store64_le(ctx.counter) + ctx.key + ctx.nonce)

    elif func == 'crypto_aead_init_djb':
        key = hex_decode(read_line()); nonce = hex_decode(read_line())
        ctx = AEAD_CTX()
        crypto_aead_init_djb(ctx, key, nonce)
        print_hex(store64_le(ctx.counter) + ctx.key + ctx.nonce)

    elif func == 'crypto_aead_init_ietf':
        key = hex_decode(read_line()); nonce = hex_decode(read_line())
        ctx = AEAD_CTX()
        crypto_aead_init_ietf(ctx, key, nonce)
        print_hex(store64_le(ctx.counter) + ctx.key + ctx.nonce)

    elif func == 'crypto_aead_write':
        key = hex_decode(read_line()); nonce = hex_decode(read_line())
        ad = hex_decode(read_line()); pt = hex_decode(read_line())
        ctx = AEAD_CTX()
        crypto_aead_init_ietf(ctx, key, nonce)
        ct, mac = crypto_aead_write(ctx, ad, pt)
        print_hex(ct); print_hex(mac)

    elif func == 'crypto_aead_lock':
        key = hex_decode(read_line()); nonce = hex_decode(read_line())
        ad = hex_decode(read_line()); pt = hex_decode(read_line())
        ct, mac = crypto_aead_lock(key, nonce, ad, pt)
        print_hex(ct); print_hex(mac)

    elif func == 'crypto_aead_unlock':
        key = hex_decode(read_line()); nonce = hex_decode(read_line())
        ad = hex_decode(read_line()); ct = hex_decode(read_line())
        mac = hex_decode(read_line())
        pt, r = crypto_aead_unlock(key, nonce, ad, ct, mac)
        if r == 0:
            print_hex(pt)
        print_hex(bytes([r & 0xFF]))

    else:
        sys.stderr.write(f"unknown function: {func}\n")
        sys.exit(1)

# ========================= CONVERSION FUNCTIONS =========================

def crypto_eddsa_to_x25519(eddsa):
    t2 = fe_frombytes(eddsa)
    t1 = fe_add(FE_ONE, t2)
    t2 = fe_sub(FE_ONE, t2)
    inv = [0]*10
    fe_invert(inv, t2)
    t1 = fe_mul(t1, inv)
    return fe_tobytes(t1)

def crypto_x25519_to_eddsa(x25519):
    t2 = fe_frombytes(x25519)
    t1 = fe_sub(t2, FE_ONE)
    t2 = fe_add(t2, FE_ONE)
    inv = [0]*10
    fe_invert(inv, t2)
    t1 = fe_mul(t1, inv)
    return fe_tobytes(t1)

if __name__ == '__main__':
    main()
