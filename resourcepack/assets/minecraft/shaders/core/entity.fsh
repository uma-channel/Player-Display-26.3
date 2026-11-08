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
layout(location = 8) in vec3 spdParams; // SPD: xy = 内層UV, z = 部位番号

// SPD-BEGIN fsh_decl
// Stable Player Display: 外層(上着)の半透明フェード。
//   spdParams.xy = 内層の同位置UV, spdParams.z = 部位番号 (0 = SPD の部位ではない)
//   この行を消す(コメントアウトする)と、外層は通常の半透明描画になる。
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

vec4 calculateFinalColor(vec4 color) {
    #ifndef NO_OVERLAY
    color.rgb = mix(overlayColor.rgb, color.rgb, overlayColor.a);
    #endif

    #ifndef EMISSIVE
    color *= lightMapColor;
    #endif

    #ifdef GLINT
    vec4 glintColor = GlintAlpha * texture(GlintSampler, texCoordGlint);
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
    vec4 color = texture(Sampler0, texCoord0);

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
    if (faceVertexColor.a < texture(DissolveMaskSampler, texCoord0).a) {
        discard;
    }
    // The dissolve effect entirely replaces translucency
    faceVertexColor.a = 1.0;
    #endif

    color *= faceVertexColor * ColorModulator;

    // SPD-BEGIN fsh_block
    #ifdef SPD_OUTER_FADE
    // Stable Player Display: 外層の半透明ピクセルを「内層との混色 + 距離フェード + ディザ」で不透明に置き換える。
    // OIT は複数パス(深度範囲/透過率/累積)が同じ color.a を使うので、全パス共通の入力側(ここ)で処理する。
    if (spdParams.z > 0.5 && color.a < 1.0) {
        color.a = max(color.a, SPD_MINALPHA);
        float fade = mix(color.a, 1.0, clamp((cylindricalVertexDistance - SPD_FADEBIAS) / (SPD_FADERANGE - SPD_FADEBIAS), 0.0, 1.0));
        if (fade < spd_bayer4[int(gl_FragCoord.x) % 4][int(gl_FragCoord.y) % 4] + (0.5 / 16.0)) {
            discard;
        }
        #ifndef OIT_ALPHA_ONLY
        // 内層も同じ頂点色で照らされるものとして混ぜる(後段の光・フォグは両者に同じ変換がかかる)
        vec3 underCol = texture(Sampler0, spdParams.xy).rgb * faceVertexColor.rgb * ColorModulator.rgb;
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
    fragColor = calculateFinalColor(color);
    #endif
}
