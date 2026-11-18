#version 330
#extension GL_ARB_separate_shader_objects : require

#ifdef GLINT
#include <minecraft:globals.glsl>
#endif
#include <minecraft:fog.glsl>
#include <minecraft:dynamictransforms.glsl>
#include <minecraft:oit.glsl>

uniform sampler2D Sampler0;

#ifdef DISSOLVE
uniform sampler2D DissolveMaskSampler;
#endif

#ifdef GLINT
uniform sampler2D GlintSampler;
#endif

layout(location = 0) in float sphericalVertexDistance;
layout(location = 1) in float cylindricalVertexDistance;
#ifdef PER_FACE_LIGHTING
layout(location = 2) in vec4 vertexPerFaceColorBack;
layout(location = 3) in vec4 vertexPerFaceColorFront;
#else
layout(location = 2) in vec4 vertexColor;
#endif

#ifndef EMISSIVE
layout(location = 4) in vec4 lightMapColor;
#endif

#ifndef NO_OVERLAY
layout(location = 5) in vec4 overlayColor;
#endif

layout(location = 6) in vec2 texCoord0;
#ifdef GLINT
layout(location = 7) in vec2 texCoordGlint;
#endif
layout(location = 8) flat in ivec2 spdPartInfo; // SPD: x = 部位番号 (0 = SPD の部位ではない), y = スリム
layout(location = 9) in vec2 spdHeadUV;         // SPD: 元の(頭の)UV

// SPD-BEGIN fsh_decl
// Stable Player Display:
//   * spd_map_uv : 頭モデルの面に張られた元のUV (spdHeadUV) から、部位 (腕/胴/脚) に対応するスキンUVを求める
//   * 外層(上着)の半透明フェード
//     SPD_OUTER_FADE の行を消す(コメントアウトする)と、外層は通常の半透明描画になる。
#define SPD_SKINRES 64

const vec4[] spd_subuvs = vec4[](
    vec4(4.0,  0.0,  8.0,  4.0 ), // 4x4x12
    vec4(8.0,  0.0,  12.0, 4.0 ),
    vec4(0.0,  4.0,  4.0,  16.0),
    vec4(4.0,  4.0,  8.0,  16.0),
    vec4(8.0,  4.0,  12.0, 16.0),
    vec4(12.0, 4.0,  16.0, 16.0),
    vec4(4.0,  0.0,  7.0,  4.0 ), // 4x3x12
    vec4(7.0,  0.0,  10.0, 4.0 ),
    vec4(0.0,  4.0,  4.0,  16.0),
    vec4(4.0,  4.0,  7.0,  16.0),
    vec4(7.0,  4.0,  11.0, 16.0),
    vec4(11.0, 4.0,  14.0, 16.0),
    vec4(4.0,  0.0,  12.0, 4.0 ), // 4x8x12
    vec4(12.0, 0.0,  20.0, 4.0 ),
    vec4(0.0,  4.0,  4.0,  16.0),
    vec4(4.0,  4.0,  12.0, 16.0),
    vec4(12.0, 4.0,  16.0, 16.0),
    vec4(16.0, 4.0,  24.0, 16.0)
);

const vec2[] spd_origins = vec2[](
    vec2(40.0, 16.0), // right arm
    vec2(40.0, 32.0),
    vec2(32.0, 48.0), // left arm
    vec2(48.0, 48.0),
    vec2(16.0, 16.0), // torso
    vec2(16.0, 32.0),
    vec2(0.0,  16.0), // right leg
    vec2(0.0,  32.0),
    vec2(16.0, 48.0), // left leg
    vec2(0.0,  48.0)
);

// SPD の部位なら true を返し、skinUV (描画する層のUV)、underUV (同じ部位の内層のUV)、outerLayer を設定する。
// SPD の部位でなければ false を返し、skinUV = texCoord0 のまま。
bool spd_map_uv(out vec2 skinUV, out vec2 underUV, out bool outerLayer) {
    skinUV = texCoord0;
    underUV = texCoord0;
    outerLayer = false;
    if (spdPartInfo.x == 0) {
        return false;
    }

    // 頭モデルのUV(ピクセル単位): 1層目は x 0-32、2層目 (外層) は x 32-64
    vec2 pixel = spdHeadUV * float(SPD_SKINRES);
    if (pixel.x < 0.0 || pixel.x >= 64.0 || pixel.y < 0.0 || pixel.y >= 16.0) {
        return false;
    }
    int layer = pixel.x >= 32.0 ? 1 : 0;
    pixel.x -= 32.0 * float(layer);

    // 頭の 8x8 の面のどれか (0=上, 1=下, 2=右, 3=前, 4=左, 5=後)
    ivec2 cell = ivec2(floor(pixel / 8.0));
    int face;
    if (cell.y == 0) {
        if (cell.x != 1 && cell.x != 2) {
            return false;
        }
        face = cell.x - 1;
    } else {
        face = cell.x + 2;
    }
    vec2 corner = (pixel - vec2(cell) * 8.0) / 8.0;   // 面の中の位置 (0-1)

    int part = spdPartInfo.x - 1;
    int bodyPart = part % 5;                          // 0=右腕 1=左腕 2=胴 3=右脚 4=左脚
    int group = part / 5;                             // 0=通常, 1=分割の下半分, 2=分割の上半分

    int subuvIndex = face;
    if (spdPartInfo.y != 0 && (bodyPart == 0 || bodyPart == 1)) {   // 細腕
        subuvIndex += 6;
    } else if (bodyPart == 2) {                                     // 胴
        subuvIndex += 12;
    }
    vec4 rect = spd_subuvs[subuvIndex];

    // 分割モデル: 側面のUV高さを半分にし、下半分の部位は下側を使う
    if (group != 0 && face >= 2) {
        rect.w -= 6.0;
        if (group == 1) {
            rect.yw += 6.0;
        }
    }

    vec2 offset = mix(rect.xy, rect.zw, corner);
    skinUV = (spd_origins[2 * bodyPart + layer] + offset) / float(SPD_SKINRES);
    underUV = (spd_origins[2 * bodyPart] + offset) / float(SPD_SKINRES);
    outerLayer = layer == 1;
    return true;
}

#define SPD_OUTER_FADE

#define SPD_FADERANGE 12.0
#define SPD_FADEBIAS 8.0
#define SPD_MINALPHA 0.25

const mat4 spd_bayer4 = mat4( 0.0 / 16.0,  8.0 / 16.0,  2.0 / 16.0, 10.0 / 16.0,
                             12.0 / 16.0,  4.0 / 16.0, 14.0 / 16.0,  6.0 / 16.0,
                              3.0 / 16.0, 11.0 / 16.0,  1.0 / 16.0,  9.0 / 16.0,
                             15.0 / 16.0,  7.0 / 16.0, 13.0 / 16.0,  5.0 / 16.0);
// SPD-END fsh_decl

#ifndef OIT_ALPHA_ONLY
layout(location = 0) out vec4 fragColor;
#endif

vec4 calculateFinalColor(vec4 color, vec2 skinUV, bool spdMapped) {
    #ifndef NO_OVERLAY
    color.rgb = mix(overlayColor.rgb, color.rgb, overlayColor.a);
    #endif

    #ifndef EMISSIVE
    color *= lightMapColor;
    #endif

    #ifdef GLINT
    // SPD: 付け替えた部位はスキンUVからグリントのUVを求める
    vec2 glintUV = texCoordGlint;
    if (spdMapped) glintUV = (TextureMat * vec4(skinUV, 0.0, 1.0)).xy;
    vec4 glintColor = GlintAlpha * texture(GlintSampler, glintUV);
    // Matches BlendFuntion.GLINT
    color.rgb += glintColor.rgb * glintColor.rgb;
    #endif

    #ifdef OIT_ACCUMULATE
    color = sampleColorForAccumulation(color);
    vec4 fogColor = vec4(FogColor.rgb * color.a, FogColor.a);
    #else
    vec4 fogColor = FogColor;
    #endif

    return apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, fogColor);
}

void main() {
    // SPD: 部位は頭のUVからスキンUVを求めて読む (SPD の部位でなければ texCoord0 のまま)
    vec2 skinUV;
    vec2 underUV;
    bool outerLayer;
    bool spdMapped = spd_map_uv(skinUV, underUV, outerLayer);
    vec2 sampleUV = skinUV;
    #ifdef APPLY_TEXTURE_MATRIX
    if (spdMapped) sampleUV = (TextureMat * vec4(skinUV, 0.0, 1.0)).xy;
    #endif
    vec4 color = texture(Sampler0, sampleUV);

    // SPD: 完全に透明なピクセルは捨てる
    if (spdMapped && color.a <= 0.0) {
        discard;
    }

    #ifdef OIT_ADDITIVE
    color.a = min(0.99, color.a);
    #endif

    #ifdef ALPHA_CUTOUT
    if (color.a < ALPHA_CUTOUT) {
        discard;
    }
    #endif

    #ifdef PER_FACE_LIGHTING
    vec4 faceVertexColor = gl_FrontFacing ? vertexPerFaceColorFront : vertexPerFaceColorBack;
    #else
    vec4 faceVertexColor = vertexColor;
    #endif

    #ifdef DISSOLVE
    if (faceVertexColor.a < texture(DissolveMaskSampler, sampleUV).a) {
        discard;
    }
    // The dissolve effect entirely replaces translucency
    faceVertexColor.a = 1.0;
    #endif

    color *= faceVertexColor * ColorModulator;

    // SPD-BEGIN fsh_block
    #ifdef SPD_OUTER_FADE
    // Stable Player Display: 外層の半透明ピクセルを「内層との混色 + 距離フェード + ディザ」で不透明に置き換える。(内層は対象外)
    // OIT は複数パス(深度範囲/透過率/累積)が同じ color.a を使うので、全パス共通の入力側(ここ)で処理する。
    if (spdMapped && outerLayer && color.a > 0.0 && color.a < 1.0) {
        color.a = max(color.a, SPD_MINALPHA);
        float fade = mix(color.a, 1.0, clamp((cylindricalVertexDistance - SPD_FADEBIAS) / (SPD_FADERANGE - SPD_FADEBIAS), 0.0, 1.0));
        if (fade < spd_bayer4[int(gl_FragCoord.x) % 4][int(gl_FragCoord.y) % 4] + (0.5 / 16.0)) {
            discard;
        }
        #ifndef OIT_ALPHA_ONLY
        // 内層も同じ頂点色で照らされるものとして混ぜる(後段の光・フォグは両者に同じ変換がかかる)
        vec3 underCol = texture(Sampler0, underUV).rgb * faceVertexColor.rgb * ColorModulator.rgb;
        vec3 trueMix = mix(underCol, color.rgb, color.a);
        color.rgb = (trueMix - (1.0 - fade) * underCol) / fade;
        #endif
        color.a = 1.0;
    }
    #endif
    // SPD-END fsh_block

    #ifdef GLINT
    color.a = max(color.a, GlintAlpha);
    #endif

    #ifdef OIT_ALPHA_ONLY
    executeAlphaOnlyPhase(gl_FragCoord.z, color.a);
    #else
    fragColor = calculateFinalColor(color, skinUV, spdMapped);
    #endif
}
