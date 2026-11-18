#version 330
#extension GL_ARB_separate_shader_objects : require

#if defined(PER_FACE_LIGHTING) || !defined(NO_CARDINAL_LIGHTING)
#include <minecraft:light.glsl>
#endif
#include <minecraft:fog.glsl>
#include <minecraft:dynamictransforms.glsl>
#include <minecraft:projection.glsl>
#include <minecraft:sample_lightmap.glsl>

// SPD-BEGIN decl
// =====================================================================
// Stable Player Display (bradleyq, CC0) -- Minecraft 26.3 port
//   * 部位は Position.y に載せた -1024*k のオフセットで判別する
//       通常モデル      : head=0, right_arm=1, left_arm=2, torso=3, right_leg=4, left_leg=5
//       分割モデルの下半分: right_forearm=6, left_forearm=7, waist=8, lower_right_leg=9, lower_left_leg=10
//       分割モデルの上半分: right_arm=11, left_arm=12, torso=13, right_leg=14, left_leg=15
//       (分割モデルの head は通常と同じ 0。通常/分割は同じリソースパックで共存する)
//   * ここでは位置のオフセットを戻し、部位番号とスリム判定、元の(頭の)UV を fsh に渡すだけ。
//     スキンUVへの付け替えは fsh の spd_map_uv で、ピクセルごとに頭のUVから行う
//     (頂点番号に依存しないので、頂点の並びや反転の影響を受けない)
// =====================================================================
uniform sampler2D Sampler0;

// 部位番号は 5 個ずつ 3 グループ: 1-5 = 通常 / 6-10 = 分割の下半分 / 11-15 = 分割の上半分
#define SPD_MAXPART 15

#define SPD_SPACING 1024.0
#define SPD_MAXRANGE (0.5 * SPD_SPACING)
#define SPD_SKINRES 64

#define SPD_SLIMCHECK0 vec2(54.0 / float(SPD_SKINRES), 20.0 / float(SPD_SKINRES))
#define SPD_SLIMCHECK1 vec2(55.0 / float(SPD_SKINRES), 20.0 / float(SPD_SKINRES))

// pos を元の位置へ戻し、部位情報 (x = 部位番号, y = スリムなら 1) を作る。
// SPD の部位でなければ何もしない (partInfo = 0)。
void spd_apply(inout vec3 pos, out ivec2 partInfo) {
    partInfo = ivec2(0);

    // ワールドの投影(GUIではない)・64x64のプレイヤースキン・手持ち描画ではない(フォグが有効)
    ivec2 dim = textureSize(Sampler0, 0);
    if (!(abs(ProjMat[2][3]) > 10e-6 && dim.x == SPD_SKINRES && dim.y == SPD_SKINRES
          && FogRenderDistanceEnd > FogRenderDistanceStart)) {
        return;
    }

    int partId = -int((pos.y - SPD_MAXRANGE) / SPD_SPACING);
    if (partId < 1 || partId > SPD_MAXPART) {
        return;                      // 0 = 通常の頭 / 範囲外 = SPD の部位ではない
    }

    vec4 samp1 = textureLod(Sampler0, SPD_SLIMCHECK0, 0.0);
    vec4 samp2 = textureLod(Sampler0, SPD_SLIMCHECK1, 0.0);
    bool slim = samp1.a == 0.0 || (((samp1.r + samp1.g + samp1.b) == 0.0) && ((samp2.r + samp2.g + samp2.b) == 0.0) && samp1.a == 1.0 && samp2.a == 1.0);

    partInfo = ivec2(partId, slim ? 1 : 0);
    pos.y += SPD_SPACING * float(partId);
}
// SPD-END decl

layout(location = 0) in vec3 Position;
layout(location = 1) in vec4 Color;
layout(location = 2) in vec2 UV0;
layout(location = 3) in ivec2 UV1;
layout(location = 4) in ivec2 UV2;
layout(location = 5) in vec3 Normal;

#if !defined(NO_OVERLAY) && !defined(OIT_ALPHA_ONLY)
uniform sampler2D Sampler1;
#endif

#if !defined(EMISSIVE) && !defined(OIT_ALPHA_ONLY)
uniform sampler2D Sampler2;
#endif

layout(location = 0) out float sphericalVertexDistance;
layout(location = 1) out float cylindricalVertexDistance;

#ifdef PER_FACE_LIGHTING
layout(location = 2) out vec4 vertexPerFaceColorBack;
layout(location = 3) out vec4 vertexPerFaceColorFront;
#else
layout(location = 2) out vec4 vertexColor;
#endif

#ifndef EMISSIVE
layout(location = 4) out vec4 lightMapColor;
#endif

#ifndef NO_OVERLAY
layout(location = 5) out vec4 overlayColor;
#endif

layout(location = 6) out vec2 texCoord0;
#ifdef GLINT
layout(location = 7) out vec2 texCoordGlint;
#endif
layout(location = 8) flat out ivec2 spdPartInfo; // SPD: x = 部位番号 (0 = SPD の部位ではない), y = スリム
layout(location = 9) out vec2 spdHeadUV;         // SPD: 元の(頭の)UV

void main() {
    vec3 pos = Position;
    spd_apply(pos, spdPartInfo);
    spdHeadUV = UV0;

    gl_Position = ProjMat * ModelViewMat * vec4(pos, 1.0);

    sphericalVertexDistance = fog_spherical_distance(pos);
    cylindricalVertexDistance = fog_cylindrical_distance(pos);

#ifdef PER_FACE_LIGHTING
    vec2 light = minecraft_compute_light(Light0_Direction, Light1_Direction, Normal);
    vertexPerFaceColorBack = minecraft_mix_light_separate(-light, Color);
    vertexPerFaceColorFront = minecraft_mix_light_separate(light, Color);
#elif defined(NO_CARDINAL_LIGHTING)
    vertexColor = Color;
#else
    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, Normal, Color);
#endif

#if !defined(EMISSIVE) && !defined(OIT_ALPHA_ONLY)
    lightMapColor = sample_lightmap(Sampler2, UV2);
#endif

#if !defined(NO_OVERLAY) && !defined(OIT_ALPHA_ONLY)
    overlayColor = texelFetch(Sampler1, UV1, 0);
#endif

    texCoord0 = UV0;

#ifdef APPLY_TEXTURE_MATRIX
    texCoord0 = (TextureMat * vec4(UV0, 0.0, 1.0)).xy;
#endif

#ifdef GLINT
    texCoordGlint = (TextureMat * vec4(UV0, 0.0, 1.0)).xy;
#endif
}
