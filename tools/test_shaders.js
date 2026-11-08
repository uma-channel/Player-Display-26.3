// Stable Player Display 26.3 シェーダー検証 (Chromium の WebGL2 を使う)
//
//   node test_shaders.js <vanilla shaders dir> <release dir> <original 1.4.1 vsh>
//
// 1. compile : 通常版/分割版の vsh + fsh を、複数の define の組み合わせでコンパイル・リンクする
//              (バニラ同士が通る組み合わせでのみ、改変版にも通ることを要求する)
// 2. uv      : 部位展開(spd_apply)の出力を、元 1.4.1 の実装と全頂点・全部位・全スキン種別で比較する
// 3. fade    : 外層フェード(fsh)の出力を、元 1.4.1 の計算と比較する
//
// 注意: WebGL2 は GLSL ES 3.00 であり、Minecraft 26.3 のコンパイラ(desktop GLSL 330 / Vulkan 系)とは別物。
//       文法・型・リンクの検査であり、実機での描画を保証するものではない。
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [VAN, REL, ORIG_VSH] = process.argv.slice(2);
if (!VAN || !REL || !ORIG_VSH) { console.error('usage: node test_shaders.js <vanilla shaders dir> <release dir> <orig vsh>'); process.exit(2); }

// ---------------------------------------------------------------- include / ES 変換
const incDir = path.join(VAN, 'include');
const INC = {};
for (const f of fs.readdirSync(incDir)) INC[f] = fs.readFileSync(path.join(incDir, f), 'utf8');
// ES 3.00 では ivec2 / float が書けないため、等価な ES 版に差し替える (検査対象は SPD の追加部分)
INC['sample_lightmap.glsl'] = `#ifndef MINECRAFT_SAMPLE_LIGHTMAP_GLSL
#define MINECRAFT_SAMPLE_LIGHTMAP_GLSL
vec4 sample_lightmap(sampler2D lightMap, ivec2 uv) {
    return texture(lightMap, clamp((vec2(uv) / 256.0) + 0.5 / 16.0, vec2(0.5 / 16.0), vec2(15.5 / 16.0)));
}
#endif
`;
// OIT は複数パスの内部実装が ES 非互換なので、関数シグネチャだけ同じスタブにする
INC['oit.glsl'] = `#ifndef MINECRAFT_OIT_GLSL
#define MINECRAFT_OIT_GLSL
#ifdef OIT
layout(location = 0) out vec4 oitStubOut;
vec4 sampleColorForAccumulation(vec4 color) { return vec4(color.rgb * color.a, color.a); }
void executeAlphaOnlyPhase(float deviceDepth, float alpha) { oitStubOut = vec4(alpha); }
#else
void executeAlphaOnlyPhase(float deviceDepth, float alpha) {}
#endif
#endif
`;

function expand(src) {
  return src.replace(/^#include <minecraft:([a-z_]+\.glsl)>[ \t]*$/gm, (m, name) => {
    if (!(name in INC)) throw new Error('missing include ' + name);
    return expand(INC[name]);
  });
}

// `const T[] name = T[](a, b, ...)` -> `const T[N] name = T[N](a, b, ...)`
function fixUnsizedArrays(s) {
  return s.replace(/const\s+(\w+)\[\]\s+(\w+)\s*=\s*\1\[\]\(/g, (m, T, name, off) => {
    let i = off + m.length, depth = 1, commas = 0, any = false;
    while (depth > 0) {
      const c = s[i++];
      if (c === '(') depth++;
      else if (c === ')') depth--;
      else if (c === ',' && depth === 1) commas++;
      else if (!/\s/.test(c) && depth >= 1) any = true;
    }
    const n = commas + 1;
    return `const ${T}[${n}] ${name} = ${T}[${n}](`;
  });
}

function toES(src, stage, defines) {
  let s = expand(src);
  s = s.replace(/^#version 330[ \t]*$/m, '');
  s = s.replace(/^#extension .*$/mg, '');
  s = s.replace(/\bgl_VertexIndex\b/g, 'gl_VertexID');
  const lay = stage === 'vs' ? /^layout\(location\s*=\s*\d+\)\s+out\s/mg : /^layout\(location\s*=\s*\d+\)\s+in\s/mg;
  s = s.replace(lay, (m) => m.replace(/layout\(location\s*=\s*\d+\)\s+/, ''));
  s = fixUnsizedArrays(s);
  const defs = defines.map(d => '#define ' + d.replace('=', ' ')).join('\n');
  return '#version 300 es\nprecision highp float;\nprecision highp int;\nprecision highp sampler2D;\n' + defs + '\n' + s;
}

// ---------------------------------------------------------------- テスト対象
const read = (p) => fs.readFileSync(p, 'utf8');
const vanVsh = read(path.join(VAN, 'core/entity.vsh'));
const vanFsh = read(path.join(VAN, 'core/entity.fsh'));
const packs = {
  default: { vsh: read(path.join(REL, 'resourcepack/assets/minecraft/shaders/core/entity.vsh')), fsh: read(path.join(REL, 'resourcepack/assets/minecraft/shaders/core/entity.fsh')), split: false, maxPart: 5 },
  split:   { vsh: read(path.join(REL, 'resourcepack_split/assets/minecraft/shaders/core/entity.vsh')), fsh: read(path.join(REL, 'resourcepack_split/assets/minecraft/shaders/core/entity.fsh')), split: true, maxPart: 10 },
};
const origVsh = read(ORIG_VSH);

// 実際のパイプラインに近い define の組み合わせ (名前はログ上のパイプライン名から)
const OIT_BASE = ['OIT', 'OIT_COEFF_COUNT=8', 'OIT_COEFF_ATTACHMENT_COUNT=2', 'OIT_WAVELET_RANK=2'];
const VARIANTS = {
  'entity_solid': [],
  'entity_cutout': ['ALPHA_CUTOUT=0.1'],
  'entity_cutout_no_cull': ['ALPHA_CUTOUT=0.1', 'NO_CARDINAL_LIGHTING'],
  'entity_translucent_cull': ['ALPHA_CUTOUT=0.0'],
  'entity_translucent_emissive': ['EMISSIVE', 'NO_OVERLAY'],
  'entity_solid_glint': ['GLINT', 'APPLY_TEXTURE_MATRIX', 'NO_CARDINAL_LIGHTING'],
  'entity_cutout_dissolve': ['ALPHA_CUTOUT=0.1', 'DISSOLVE'],
  'per_face_lighting': ['PER_FACE_LIGHTING', 'ALPHA_CUTOUT=0.1'],
  'oit_accumulate_entity': [...OIT_BASE, 'OIT_ACCUMULATE'],
  'oit_accumulate_additive_emissive': [...OIT_BASE, 'OIT_ACCUMULATE', 'OIT_ADDITIVE', 'EMISSIVE'],
  'oit_transmittance_entity': [...OIT_BASE, 'OIT_TRANSMITTANCE', 'OIT_ALPHA_ONLY'],
  'oit_depth_bounds_entity_emissive': [...OIT_BASE, 'OIT_DEPTH_BOUNDS', 'OIT_ALPHA_ONLY', 'EMISSIVE'],
};

// ---------------------------------------------------------------- UV 等価性テスト用シェーダー
function between(src, a, b) {
  const i = src.indexOf(a), j = src.indexOf(b);
  if (i < 0 || j < 0) throw new Error('marker not found: ' + a);
  return src.slice(i, j + b.length);
}
// 元の vsh から main 内の SPD 部分 (partId != 0 の分岐) を関数に移植する
const origMacros = between(origVsh, '#define SPACING 1024.0', 'const int[] faceremap = int[](0, 0, 1, 1, 2, 3, 4, 5);');
function uvTestVsh(pack) {
  const decl = between(pack.vsh, '// SPD-BEGIN decl', '// SPD-END decl').replace('uniform sampler2D Sampler0;', '');
  return `
uniform sampler2D Sampler0;
uniform mat4 ProjMat;
uniform float FogRenderDistanceStart;
uniform float FogRenderDistanceEnd;
in vec3 Position;
in vec2 UV0;
out vec4 oA; out vec4 oB; out vec4 oC; out vec4 oD;
// ---- 移植版 (生成された entity.vsh から抜き出し) ----
${decl}
// ---- 元 1.4.1 ----
#define SPLITMODEL ${pack.split ? 1 : 0}
${origMacros}
void orig(vec3 Pos, vec2 UVin, out vec3 wpos, out vec2 t0, out vec2 t1, out float part) {
    ivec2 dim = textureSize(Sampler0, 0);
    part = 0.0;
    t0 = UVin; t1 = vec2(0.0); wpos = Pos;
    if (abs(ProjMat[2][3]) > 10e-6 && dim.x == SKINRES && dim.y == SKINRES && FogRenderDistanceEnd > FogRenderDistanceStart) {
        int partId = -int((Pos.y - MAXRANGE) / SPACING);
        part = float(partId);
        if (partId != 0) {
            partId -= 1;
            vec4 samp1 = texture(Sampler0, SLIMCHECK0);
            vec4 samp2 = texture(Sampler0, SLIMCHECK1);
            bool slim = samp1.a == 0.0 || (((samp1.r + samp1.g + samp1.b) == 0.0) && ((samp2.r + samp2.g + samp2.b) == 0.0) && samp1.a == 1.0 && samp2.a == 1.0);
            int partIdMod = partId % 5;
            int outerLayer = (gl_VertexID / 24) % 2;
            int vertexId = gl_VertexID % 4;
            int faceId = (gl_VertexID % 24) / 4;
            ivec2 faceIdTmp = ivec2(round(UVin * float(SKINRES)));
            vec2 UVout = origins[2 * partIdMod + outerLayer];
            vec2 UVout2 = origins[2 * partIdMod];
            if ((faceId != 1 && vertexId >= 2) || (faceId == 1 && vertexId <= 1)) { faceIdTmp.y -= FACERES; }
            if (vertexId == 0 || vertexId == 3) { faceIdTmp.x -= FACERES; }
            faceIdTmp /= FACERES;
            faceId = (faceIdTmp.x % 4) + 4 * faceIdTmp.y;
            faceId = faceremap[faceId];
            int subuvIndex = faceId;
            if (slim && (partIdMod == 0 || partIdMod == 1)) { subuvIndex += 6; }
            else if (partIdMod == 2) { subuvIndex += 12; }
            vec4 subuv = subuvs[subuvIndex];
            vec2 offset = vec2(0.0);
#if SPLITMODEL == 1
            if (faceId >= 2) {
                subuv.w -= 6.0;
                if (partId >= 5) { subuv.yw += 6.0; }
            }
#endif
            if (faceId == 1) {
                if (vertexId == 0) { offset += subuv.zw; }
                else if (vertexId == 1) { offset += subuv.xw; }
                else if (vertexId == 2) { offset += subuv.xy; }
                else { offset += subuv.zy; }
            } else {
                if (vertexId == 0) { offset += subuv.zy; }
                else if (vertexId == 1) { offset += subuv.xy; }
                else if (vertexId == 2) { offset += subuv.xw; }
                else { offset += subuv.zw; }
            }
            UVout += offset; UVout2 += offset;
            UVout /= float(SKINRES); UVout2 /= float(SKINRES);
            vec3 w = Pos; w.y += SPACING * float(partId + 1);
            wpos = w; t0 = UVout; t1 = UVout2;
        }
    }
}
void main() {
    vec3 p = Position; vec2 u = UV0; vec2 under; float pt;
    spd_apply(p, u, under, pt);
    vec3 wp; vec2 t0; vec2 t1; float part;
    orig(Position, UV0, wp, t0, t1, part);
    oA = vec4(p, pt); oB = vec4(u, under);
    oC = vec4(wp, part); oD = vec4(t0, t1);
    gl_Position = vec4(0.0);
}
`;
}

// ---------------------------------------------------------------- フェード等価性テスト用シェーダー
function fadeTestFsh(pack) {
  const decl = between(pack.fsh, '// SPD-BEGIN fsh_decl', '// SPD-END fsh_decl');
  let block = between(pack.fsh, '// SPD-BEGIN fsh_block', '// SPD-END fsh_block').replace(/discard;/g, 'return vec4(-1.0);');
  return `
uniform sampler2D Sampler0;
uniform vec4 uOuter;       // 外層のテクセル (rgba)
uniform vec2 uUnderUV;
uniform float uPart;
uniform float uCyl;
out vec4 o;
${decl}
vec4 mine() {
    vec4 ColorModulator = vec4(1.0);
    vec4 faceVertexColor = vec4(1.0);
    vec4 color = uOuter * faceVertexColor * ColorModulator;
    vec3 spdParams = vec3(uUnderUV, uPart);
    float cylindricalVertexDistance = uCyl;
${block}
    return color;
}
// ---- 元 1.4.1 (光・フォグなしの条件) ----
#define FADERANGE 12.0
#define FADEBIAS 8.0
#define MINALPHA 0.25
const mat4 bayer4 = mat4( 0.0 / 16.0,  8.0 / 16.0,  2.0 / 16.0, 10.0 / 16.0,
                         12.0 / 16.0,  4.0 / 16.0, 14.0 / 16.0,  6.0 / 16.0,
                          3.0 / 16.0, 11.0 / 16.0,  1.0 / 16.0,  9.0 / 16.0,
                         15.0 / 16.0,  7.0 / 16.0, 13.0 / 16.0,  5.0 / 16.0);
vec4 orig() {
    vec4 fragColor = uOuter;
    float part = uPart;
    float cylindricalVertexDistance = uCyl;
    vec2 texCoord1 = uUnderUV;
    if (part > 1.0 - 10e-6 && fragColor.a < 1.0) {
        fragColor.a = max(fragColor.a, MINALPHA);
        vec3 underCol = texture(Sampler0, texCoord1).rgb;
        vec3 trueMix = mix(underCol, fragColor.rgb, fragColor.a);
        float fade = mix(fragColor.a, 1.0, clamp((cylindricalVertexDistance - FADEBIAS) / (FADERANGE - FADEBIAS), 0.0, 1.0));
        fragColor = vec4((trueMix - (1.0 - fade) * underCol) / fade,  fade);
        if (fragColor.a < bayer4[int(gl_FragCoord.x) % 4][int(gl_FragCoord.y) % 4] + (0.5 / 16.0)) {
            return vec4(-1.0);
        } else {
            fragColor.a = 1.0;
        }
    }
    return fragColor;
}
uniform int uMode;
void main() { o = uMode == 0 ? mine() : orig(); }
`;
}

// ---------------------------------------------------------------- ブラウザ側
const PAGE_JS = `
window.GL = (() => {
  const c = document.createElement('canvas'); c.width = 16; c.height = 16;
  const gl = c.getContext('webgl2', { antialias: false, preserveDrawingBuffer: true });
  return gl;
})();
window.compileLink = (vs, fs) => {
  const gl = window.GL;
  const out = { ok: true, log: '' };
  const mk = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { out.ok = false; out.log += (type === gl.VERTEX_SHADER ? '[vs] ' : '[fs] ') + gl.getShaderInfoLog(s); return null; } return s; };
  const v = mk(gl.VERTEX_SHADER, vs), f = mk(gl.FRAGMENT_SHADER, fs);
  if (!v || !f) return out;
  const p = gl.createProgram(); gl.attachShader(p, v); gl.attachShader(p, f); gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) { out.ok = false; out.log += '[link] ' + gl.getProgramInfoLog(p); }
  return out;
};
window.info = () => { const gl = window.GL; return gl ? { ok: true, r: gl.getParameter(gl.RENDERER), v: gl.getParameter(gl.VERSION), float: !!gl.getExtension('EXT_color_buffer_float') } : { ok: false }; };

// ---- UV 等価性: 全頂点 x 全部位 x スキン種別 ----
window.runUv = (vsSrc, maxPart, seeds) => {
  const gl = window.GL;
  const fsSrc = '#version 300 es\\nprecision highp float;\\nout vec4 c; void main(){ c = vec4(1.0); }';
  const mkS = (t, s) => { const x = gl.createShader(t); gl.shaderSource(x, s); gl.compileShader(x);
    if (!gl.getShaderParameter(x, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(x)); return x; };
  const prog = gl.createProgram();
  gl.attachShader(prog, mkS(gl.VERTEX_SHADER, vsSrc)); gl.attachShader(prog, mkS(gl.FRAGMENT_SHADER, fsSrc));
  gl.transformFeedbackVaryings(prog, ['oA', 'oB', 'oC', 'oD'], gl.INTERLEAVED_ATTRIBS);
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
  gl.useProgram(prog);
  const locP = gl.getAttribLocation(prog, 'Position'), locU = gl.getAttribLocation(prog, 'UV0');
  const N = 48;
  const tf = gl.createBuffer(); gl.bindBuffer(gl.TRANSFORM_FEEDBACK_BUFFER, tf); gl.bufferData(gl.TRANSFORM_FEEDBACK_BUFFER, N * 16 * 4, gl.DYNAMIC_READ);
  gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER, 0, tf);
  const uvb = gl.createBuffer();
  const mkTex = (kind) => {
    const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    const d = new Uint8Array(64 * 64 * 4);
    for (let i = 0; i < 64 * 64; i++) { d[i*4] = 200; d[i*4+1] = 100; d[i*4+2] = 50; d[i*4+3] = 255; }
    for (let y = 19; y <= 20; y++) for (let x = 52; x <= 57; x++) { const o = (y*64+x)*4;
      if (kind === 'slimA') { d[o+3] = 0; } else if (kind === 'slimB') { d[o] = 0; d[o+1] = 0; d[o+2] = 0; d[o+3] = 255; } }
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, 64, 64, 0, gl.RGBA, gl.UNSIGNED_BYTE, d);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  };
  const tex32 = (() => { const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, 32, 32, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(32*32*4).fill(255));
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST); return t; })();
  const texs = { classic: mkTex('classic'), slimA: mkTex('slimA'), slimB: mkTex('slimB') };
  const uni = (n) => gl.getUniformLocation(prog, n);
  const proj = (persp) => { const m = new Float32Array(16); m[0] = m[5] = m[10] = 1; m[15] = 1; if (persp) { m[11] = -1; } return m; };
  gl.enable(gl.RASTERIZER_DISCARD);
  let rng = seeds;
  const rnd = () => { rng = (rng * 1664525 + 1013904223) >>> 0; return rng / 4294967296; };
  const res = { draws: 0, vertices: 0, mismatch: 0, examples: [], modified: 0, gated: 0, gatedBad: 0, outOfRangeBad: 0 };
  const run = (partId, texKind, opts) => {
    opts = opts || {};
    gl.bindTexture(gl.TEXTURE_2D, opts.tex32 ? tex32 : texs[texKind]);
    gl.uniformMatrix4fv(uni('ProjMat'), false, proj(opts.persp !== false));
    gl.uniform1f(uni('FogRenderDistanceStart'), 50); gl.uniform1f(uni('FogRenderDistanceEnd'), opts.fogOff ? 50 : 100);
    gl.uniform1i(uni('Sampler0'), 0);
    // 頂点ごとの UV0: 面ごとにランダムなタイルを選び、元の分岐が想定する角に置く
    const uv = new Float32Array(N * 2);
    const tiles = {};
    for (let i = 0; i < N; i++) {
      const outer = Math.floor(i / 24) % 2, face = Math.floor((i % 24) / 4), vid = i % 4;
      const key = outer + ':' + face;
      if (!(key in tiles)) tiles[key] = [Math.floor(rnd() * 8), Math.floor(rnd() * 2)];
      const [tx, ty] = tiles[key];
      const x = tx * 8 + ((vid === 0 || vid === 3) ? 8 : 0);
      const y = ty * 8 + (((face !== 1 && vid >= 2) || (face === 1 && vid <= 1)) ? 8 : 0);
      uv[i*2] = x / 64; uv[i*2+1] = y / 64;
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, uvb); gl.bufferData(gl.ARRAY_BUFFER, uv, gl.STREAM_DRAW);
    gl.enableVertexAttribArray(locU); gl.vertexAttribPointer(locU, 2, gl.FLOAT, false, 0, 0);
    gl.disableVertexAttribArray(locP);
    const py = partId === 0 ? 3.0 : -1024 * partId + 7.0;
    gl.vertexAttrib3f(locP, 0.25, py, -0.5);
    gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER, 0, tf);
    gl.beginTransformFeedback(gl.POINTS); gl.drawArrays(gl.POINTS, 0, N); gl.endTransformFeedback();
    const out = new Float32Array(N * 16); gl.bindBuffer(gl.TRANSFORM_FEEDBACK_BUFFER, tf); gl.getBufferSubData(gl.TRANSFORM_FEEDBACK_BUFFER, 0, out);
    res.draws++;
    for (let i = 0; i < N; i++) {
      const o = out.subarray(i * 16, i * 16 + 16);   // A(p,pt) B(u,under) C(wp,part) D(t0,t1)
      const mine = [o[0], o[1], o[2], o[4], o[5], o[6], o[7]];   // p, u, under
      const orig = [o[8], o[9], o[10], o[12], o[13], o[14], o[15]];
      res.vertices++;
      const mpt = o[3], opt = o[11];
      const inRange = partId >= 1 && partId <= maxPart;
      const gated = opts.tex32 || opts.persp === false || opts.fogOff;
      if (gated) {
        // ゲート外: 両方とも何も変えない
        res.gated++;
        const unchanged = Math.abs(o[1] - py) < 1e-6 && Math.abs(o[4] - uv[i*2]) < 1e-6 && mpt === 0;
        if (!unchanged || Math.abs(o[9] - py) > 1e-6) res.gatedBad++;
      } else if (inRange) {
        let bad = false;
        for (let k = 0; k < 7; k++) if (Math.abs(mine[k] - orig[k]) > 1e-6) bad = true;
        if (mpt !== opt) bad = true;
        if (Math.abs(o[1] - py) > 1e-6) res.modified++;
        if (bad) { res.mismatch++; if (res.examples.length < 4) res.examples.push({ partId, texKind, i, mine, orig, mpt, opt }); }
      } else {
        // 範囲外 (0 または MAXPART 超): 移植版は何も変えない
        const unchanged = Math.abs(o[1] - py) < 1e-6 && Math.abs(o[4] - uv[i*2]) < 1e-6 && Math.abs(o[5] - uv[i*2+1]) < 1e-6 && mpt === 0;
        if (!unchanged) res.outOfRangeBad++;
      }
    }
  };
  for (const texKind of ['classic', 'slimA', 'slimB'])
    for (let pid = 0; pid <= maxPart + 3; pid++)
      for (let rep = 0; rep < 6; rep++) run(pid, texKind);
  run(3, 'classic', { tex32: true }); run(3, 'classic', { persp: false }); run(3, 'classic', { fogOff: true });
  return res;
};

// ---- フェード等価性 ----
window.runFade = (fsSrc, cases) => {
  const gl = window.GL;
  const vs = '#version 300 es\\nin vec2 a; void main(){ gl_Position = vec4(a, 0.0, 1.0); }';
  const mkS = (t, s) => { const x = gl.createShader(t); gl.shaderSource(x, s); gl.compileShader(x);
    if (!gl.getShaderParameter(x, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(x)); return x; };
  const prog = gl.createProgram(); gl.attachShader(prog, mkS(gl.VERTEX_SHADER, vs)); gl.attachShader(prog, mkS(gl.FRAGMENT_SHADER, fsSrc));
  gl.bindAttribLocation(prog, 0, 'a'); gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
  gl.useProgram(prog);
  const ext = gl.getExtension('EXT_color_buffer_float');
  const fbo = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
  const rt = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, rt);
  gl.texImage2D(gl.TEXTURE_2D, 0, ext ? gl.RGBA32F : gl.RGBA8, 16, 16, 0, gl.RGBA, ext ? gl.FLOAT : gl.UNSIGNED_BYTE, null);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, rt, 0);
  // スキン代わりのテクスチャ (内層の色を UV から引く)
  const skin = gl.createTexture(); gl.bindActiveTexture; gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, skin);
  const sd = new Uint8Array(64 * 64 * 4);
  for (let y = 0; y < 64; y++) for (let x = 0; x < 64; x++) { const o = (y*64+x)*4; sd[o] = (x * 4) & 255; sd[o+1] = (y * 4) & 255; sd[o+2] = ((x + y) * 3) & 255; sd[o+3] = 255; }
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, 64, 64, 0, gl.RGBA, gl.UNSIGNED_BYTE, sd);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.uniform1i(gl.getUniformLocation(prog, 'Sampler0'), 1);
  const vb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, vb);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  gl.viewport(0, 0, 16, 16);
  const u = (n) => gl.getUniformLocation(prog, n);
  const res = { cases: 0, pixels: 0, mismatch: 0, discarded: 0, kept: 0, modifiedColor: 0, ext: !!ext, examples: [] };
  const read = (mode, c) => {
    gl.uniform4f(u('uOuter'), c.outer[0], c.outer[1], c.outer[2], c.outer[3]);
    gl.uniform2f(u('uUnderUV'), c.under[0], c.under[1]); gl.uniform1f(u('uPart'), c.part); gl.uniform1f(u('uCyl'), c.cyl);
    gl.uniform1i(u('uMode'), mode);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    if (ext) { const d = new Float32Array(16*16*4); gl.readPixels(0, 0, 16, 16, gl.RGBA, gl.FLOAT, d); return d; }
    const d8 = new Uint8Array(16*16*4); gl.readPixels(0, 0, 16, 16, gl.RGBA, gl.UNSIGNED_BYTE, d8); return Float32Array.from(d8, v => v / 255);
  };
  for (const c of cases) {
    const a = read(0, c), b = read(1, c);
    res.cases++;
    for (let i = 0; i < 256; i++) {
      res.pixels++;
      const aa = a.subarray(i*4, i*4+4), bb = b.subarray(i*4, i*4+4);
      const tol = ext ? 2e-5 : 1.5 / 255;
      let bad = false;
      for (let k = 0; k < 4; k++) if (Math.abs(aa[k] - bb[k]) > tol) bad = true;
      if (aa[3] < 0 || (!ext && false)) res.discarded++; else res.kept++;
      if (bad) { res.mismatch++; if (res.examples.length < 4) res.examples.push({ c, i, mine: Array.from(aa), orig: Array.from(bb) }); }
    }
  }
  return res;
};
`;

// ---------------------------------------------------------------- 実行
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage();
  await page.setContent('<html><body></body></html>');
  await page.evaluate(PAGE_JS);
  const info = await page.evaluate(() => window.info());
  if (!info.ok) { console.error('WebGL2 が使えません'); process.exit(2); }
  console.log('WebGL2:', info.r, '|', info.v, '| float RT:', info.float);

  let failures = 0;
  const fail = (m) => { failures++; console.log('  FAIL', m); };

  // ---------- 1. compile / link
  console.log('\n[1] compile / link  (variant x {vanilla, default, split, patched-vsh+vanilla-fsh})');
  const hdr = ['variant'.padEnd(34), 'vanilla', 'default', 'split', 'fallback(no fsh)'];
  console.log(hdr.join('  '));
  for (const [name, defs] of Object.entries(VARIANTS)) {
    const run = (vsh, fsh) => page.evaluate(([v, f]) => window.compileLink(v, f), [toES(vsh, 'vs', defs), toES(fsh, 'fs', defs)]);
    const van = await run(vanVsh, vanFsh);
    const row = [name.padEnd(34), (van.ok ? 'ok' : 'SKIP').padEnd(7)];
    if (!van.ok) { row.push('-'.padEnd(7), '-'.padEnd(5), '-'); console.log(row.join('  ') + '   (バニラ自体が ES スタブで通らない: ' + van.log.split('\n')[0].slice(0, 90) + ')'); continue; }
    const d = await run(packs.default.vsh, packs.default.fsh);
    const s = await run(packs.split.vsh, packs.split.fsh);
    const fb = await run(packs.default.vsh, vanFsh);
    row.push((d.ok ? 'ok' : 'FAIL').padEnd(7), (s.ok ? 'ok' : 'FAIL').padEnd(5), fb.ok ? 'ok' : 'FAIL');
    console.log(row.join('  '));
    if (!d.ok) fail(name + ' default: ' + d.log.slice(0, 600));
    if (!s.ok) fail(name + ' split: ' + s.log.slice(0, 600));
    if (!fb.ok) fail(name + ' fallback: ' + fb.log.slice(0, 600));
  }

  // ---------- 2. UV 等価性
  console.log('\n[2] 部位展開 (spd_apply) vs 元 1.4.1');
  for (const [pname, pack] of Object.entries(packs)) {
    const vs = toES(uvTestVsh(pack), 'vs', []).replace(/^#version 300 es/, '#version 300 es');
    await page.evaluate((m) => { window.__maxPart = m; }, pack.maxPart);
    let r;
    try { r = await page.evaluate(([v, seed]) => window.runUv(v, window.__maxPart, seed), [vs, 12345]); }
    catch (e) { fail(pname + ' uv test error: ' + e.message.slice(0, 800)); continue; }
    console.log(`  ${pname.padEnd(8)} draws=${r.draws} vertices=${r.vertices}  不一致=${r.mismatch}  位置変更あり=${r.modified}  ゲート外の誤変更=${r.gatedBad}  範囲外の誤変更=${r.outOfRangeBad}`);
    if (r.mismatch || r.gatedBad || r.outOfRangeBad || r.modified === 0) { fail(pname + ' uv: ' + JSON.stringify(r.examples).slice(0, 800)); }
  }

  // ---------- 3. フェード等価性
  console.log('\n[3] 外層フェード (fsh) vs 元 1.4.1  (光・フォグなしの条件で一致するか)');
  const cases = [];
  let seed = 777; const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  for (const part of [0, 1, 3, 10]) for (const cyl of [0, 5, 8, 9, 10, 11.5, 12, 30]) for (let k = 0; k < 8; k++) {
    const alphas = [0.02, 0.1, 0.25, 0.4, 0.6, 0.8, 0.95, 1.0];
    cases.push({ part, cyl, outer: [rnd(), rnd(), rnd(), alphas[k]], under: [Math.floor(rnd() * 64) / 64 + 0.5 / 64, Math.floor(rnd() * 64) / 64 + 0.5 / 64] });
  }
  const fadeFs = toES(fadeTestFsh(packs.default), 'fs', []);
  let fr;
  try { fr = await page.evaluate(([f, c]) => window.runFade(f, c), [fadeFs, cases]); }
  catch (e) { fail('fade test error: ' + e.message.slice(0, 800)); fr = null; }
  if (fr) {
    console.log(`  cases=${fr.cases} pixels=${fr.pixels}  不一致=${fr.mismatch}  (float RT: ${fr.ext})`);
    if (fr.mismatch) fail('fade: ' + JSON.stringify(fr.examples).slice(0, 900));
  }

  await browser.close();
  console.log(failures ? `\nRESULT: ${failures} 件の失敗` : '\nRESULT: すべて成功');
  process.exit(failures ? 1 : 0);
})();
