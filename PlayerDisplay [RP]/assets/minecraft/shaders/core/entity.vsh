#version 330
#extension GL_ARB_separate_shader_objects : require

#if defined(PER_FACE_LIGHTING) || !defined(NO_CARDINAL_LIGHTING)
#include <minecraft:light.glsl>
#endif
#include <minecraft:fog.glsl>
#include <minecraft:dynamictransforms.glsl>
#include <minecraft:projection.glsl>
#include <minecraft:sample_lightmap.glsl>

// =====================================================================
// Stable Player Display (bradleyq, CC0) -- ported to Minecraft 26.x
//   * 部位は translation.y に入れた -1024*k のオフセットで判別する (head=0, arm_r=1, arm_l=2, torso=3, leg_r=4, leg_l=5)
//   * ヘッドモデルの頂点を、各部位(腕/胴/脚)の形とスキンUVへ付け替える
//   * 26.x では OIT/PER_FACE_LIGHTING 等の派生シェーダーがあるので、ALPHA_CUTOUT などの define には依存しない
// =====================================================================
uniform sampler2D Sampler0;

#define SPD_SPACING 1024.0
#define SPD_MAXRANGE (0.5 * SPD_SPACING)
#define SPD_SKINRES 64
#define SPD_FACERES 8

#define SPD_SLIMCHECK0 vec2(54.0 / float(SPD_SKINRES), 20.0 / float(SPD_SKINRES))
#define SPD_SLIMCHECK1 vec2(55.0 / float(SPD_SKINRES), 20.0 / float(SPD_SKINRES))

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

const int[] spd_faceremap = int[](0, 0, 1, 1, 2, 3, 4, 5);

// pos / uv を SPD の部位用に書き換える。部位でなければ何もしない。
void spd_apply(inout vec3 pos, inout vec2 uv) {
    // 世界の投影(GUIではない)・64x64のプレイヤースキン・手持ち描画ではない(フォグが有効)
    ivec2 dim = textureSize(Sampler0, 0);
    if (!(abs(ProjMat[2][3]) > 10e-6 && dim.x == SPD_SKINRES && dim.y == SPD_SKINRES
          && FogRenderDistanceEnd > FogRenderDistanceStart)) {
        return;
    }

    int partId = -int((pos.y - SPD_MAXRANGE) / SPD_SPACING);
    if (partId < 1 || partId > 5) {
        return;                      // 0 = 通常の頭 / 範囲外 = SPD の部位ではない
    }
    partId -= 1;

    vec4 samp1 = textureLod(Sampler0, SPD_SLIMCHECK0, 0.0);
    vec4 samp2 = textureLod(Sampler0, SPD_SLIMCHECK1, 0.0);
    bool slim = samp1.a == 0.0 || (((samp1.r + samp1.g + samp1.b) == 0.0) && ((samp2.r + samp2.g + samp2.b) == 0.0) && samp1.a == 1.0 && samp2.a == 1.0);
    int partIdMod = partId % 5;
    int outerLayer = (gl_VertexIndex / 24) % 2;
    int vertexId = gl_VertexIndex % 4;
    int faceId = (gl_VertexIndex % 24) / 4;
    ivec2 faceIdTmp = ivec2(round(uv * float(SPD_SKINRES)));

    // 付け替え先の部位のUV原点
    vec2 UVout = spd_origins[2 * partIdMod + outerLayer];

    // 元の(頭)の面のUV原点を探す
    if ((faceId != 1 && vertexId >= 2) || (faceId == 1 && vertexId <= 1)) {
        faceIdTmp.y -= SPD_FACERES;
    }
    if (vertexId == 0 || vertexId == 3) {
        faceIdTmp.x -= SPD_FACERES;
    }

    // 頭のUV原点から面番号を求める
    faceIdTmp /= SPD_FACERES;
    faceId = (faceIdTmp.x % 4) + 4 * faceIdTmp.y;
    faceId = spd_faceremap[faceId];
    int subuvIndex = faceId;

    if (slim && (partIdMod == 0 || partIdMod == 1)) {   // 細腕
        subuvIndex += 6;
    } else if (partIdMod == 2) {                        // 胴
        subuvIndex += 12;
    }

    vec4 subuv = spd_subuvs[subuvIndex];
    vec2 offset = vec2(0.0);

    // 部位内のUVオフセット
    if (faceId == 1) {
        if (vertexId == 0)      offset += subuv.zw;
        else if (vertexId == 1) offset += subuv.xw;
        else if (vertexId == 2) offset += subuv.xy;
        else                    offset += subuv.zy;
    } else {
        if (vertexId == 0)      offset += subuv.zy;
        else if (vertexId == 1) offset += subuv.xy;
        else if (vertexId == 2) offset += subuv.xw;
        else                    offset += subuv.zw;
    }

    UVout += offset;
    UVout /= float(SPD_SKINRES);

    pos.y += SPD_SPACING * float(partId + 1);
    uv = UVout;
}

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

void main() {
    vec3 pos = Position;
    vec2 uv0 = UV0;
    spd_apply(pos, uv0);

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

    texCoord0 = uv0;

#ifdef APPLY_TEXTURE_MATRIX
    texCoord0 = (TextureMat * vec4(uv0, 0.0, 1.0)).xy;
#endif

#ifdef GLINT
    texCoordGlint = (TextureMat * vec4(uv0, 0.0, 1.0)).xy;
#endif
}
