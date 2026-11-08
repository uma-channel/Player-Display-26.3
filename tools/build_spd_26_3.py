#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stable Player Display (bradleyq / erkko68 fork, CC0) -> Minecraft Java 26.3 完全移植ビルドスクリプト

入力
  --spd      stable_player_display-1.4.1.zip (元の配布物)
  --shaders  バニラ 26.3 のシェーダー。次のいずれか
               * ディレクトリ (assets/minecraft/shaders もしくは その中身の core/ include/ を含むもの)
               * それらを含む zip
             (misode/mcmeta の `26.3-assets` タグ、または client jar から取り出せる)
  --out      出力先 (既定: ./out)

出力 (out/stable_player_display-26.3/)
  resourcepack/            通常モデル用 (6パーツ)
  resourcepack_split/      分割モデル用 (11パーツ)
  animated-java-resources/ aj-convert.py / blueprint / sample_datapack (26.3 形式)
  README.md, LICENSE ...
  ../stable_player_display_26_3.zip, ..._split.zip, ..._sample_datapack.zip

シェーダーは「バニラ 26.3 の entity.vsh / entity.fsh を機械的にパッチ」して作る。
バニラ側が想定と違えば、黙って壊れた物を作らず失敗する。
"""
import argparse, json, os, re, shutil, sys, zipfile

# 26.3 公式 (misode/mcmeta 26.3-summary の version.json): resource 97.1 / data 121.0
RESOURCE_FORMAT = 97
DATA_FORMAT = 121

# 26.3 の items/player_head.json の transformation (バニラの値そのまま)
#   left_rotation (1,0,0,0) = X軸まわり 180度 (上下・前後を反転)
PLAYER_HEAD_TRANSFORMATION = {
    "translation": [0.5, 0.0, 0.5],
    "left_rotation": [1.0, 0.0, 0.0, 0.0],
    "scale": [1.0, 1.0, 1.0],
    "right_rotation": [0.0, 0.0, 0.0, 1.0],
}

DEFAULT_PARTS = ["head", "right_arm", "left_arm", "torso", "right_leg", "left_leg"]
SPLIT_PARTS = DEFAULT_PARTS + ["right_forearm", "left_forearm", "waist", "lower_right_leg", "lower_left_leg"]

MODEL_NS = "animated_java:blueprint/player_display/"
SLIM_NS = "animated_java:blueprint/player_display/slim/"

# ---------------------------------------------------------------------------
# GLSL
# ---------------------------------------------------------------------------
# --- 頂点シェーダー: SPD の部位展開 (元 1.4.1 の entity.vsh と同じロジック) -------------
VSH_DECL = r'''
// SPD-BEGIN decl
// =====================================================================
// Stable Player Display (bradleyq, CC0) -- Minecraft 26.3 port
//   * 部位は Position.y に載せた -1024*k のオフセットで判別する
//       default : head=0, right_arm=1, left_arm=2, torso=3, right_leg=4, left_leg=5
//       split   : + right_forearm=6, left_forearm=7, waist=8, lower_right_leg=9, lower_left_leg=10
//   * ヘッドモデルの頂点を、各部位(腕/胴/脚)の形とスキンUVへ付け替える
//   * 外層(上着)の半透明フェード用に、内層の同位置UVと部位番号を spdParams で fsh に渡す
//   * 頂点番号は gl_VertexIndex (26.x のコンパイラは gl_VertexID を未定義として拒否する)
// =====================================================================
uniform sampler2D Sampler0;

#define SPD_SPLITMODEL @SPLIT@
#if SPD_SPLITMODEL == 1
#define SPD_MAXPART 10
#else
#define SPD_MAXPART 5
#endif

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

// pos / uv を SPD の部位用に書き換える。SPD の部位でなければ何もしない。
//   uvUnder : 外層の頂点に対応する内層(同じ部位の1層目)のUV (fsh の半透明フェード用)
//   partOut : 部位番号 (0 = SPD の部位ではない / 頭)
void spd_apply(inout vec3 pos, inout vec2 uv, out vec2 uvUnder, out float partOut) {
    partOut = 0.0;
    uvUnder = vec2(0.0);

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
    partOut = float(partId);
    partId -= 1;

    vec4 samp1 = textureLod(Sampler0, SPD_SLIMCHECK0, 0.0);
    vec4 samp2 = textureLod(Sampler0, SPD_SLIMCHECK1, 0.0);
    bool slim = samp1.a == 0.0 || (((samp1.r + samp1.g + samp1.b) == 0.0) && ((samp2.r + samp2.g + samp2.b) == 0.0) && samp1.a == 1.0 && samp2.a == 1.0);
    int partIdMod = partId % 5;
    int outerLayer = (gl_VertexIndex / 24) % 2;
    int vertexId = gl_VertexIndex % 4;
    int faceId = (gl_VertexIndex % 24) / 4;
    ivec2 faceIdTmp = ivec2(round(uv * float(SPD_SKINRES)));

    // 付け替え先の部位のUV原点 (UVout = 描画する層, UVout2 = 内層)
    vec2 UVout = spd_origins[2 * partIdMod + outerLayer];
    vec2 UVout2 = spd_origins[2 * partIdMod];

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

#if SPD_SPLITMODEL == 1
    // 分割モデル: 側面のUV高さを半分にし、下半分の部位は下側を使う
    if (faceId >= 2) {
        subuv.w -= 6.0;
        if (partId >= 5) {
            subuv.yw += 6.0;
        }
    }
#endif

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
    UVout2 += offset;
    UVout /= float(SPD_SKINRES);
    UVout2 /= float(SPD_SKINRES);

    pos.y += SPD_SPACING * float(partId + 1);
    uv = UVout;
    uvUnder = UVout2;
}
// SPD-END decl
'''

# --- フラグメントシェーダー: 外層(上着)の半透明フェード (元 1.4.1 の entity.fsh と同じ計算) ---
FSH_DECL = r'''
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
'''

FSH_BLOCK = r'''
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
'''


def replace_once(text, old, new, label, count=1):
    n = text.count(old)
    if n != count:
        raise SystemExit("バニラのシェーダーが想定と違う (%s): %d 個見つかった (期待 %d)。\n  探した文字列:\n%s"
                         % (label, n, count, old))
    return text.replace(old, new)


def patch_entity_vsh(src, split):
    out = src
    decl = VSH_DECL.replace("@SPLIT@", "1" if split else "0")
    out = replace_once(out, "#include <minecraft:sample_lightmap.glsl>\n",
                       "#include <minecraft:sample_lightmap.glsl>\n" + decl, "vsh include")
    out = replace_once(
        out,
        "layout(location = 6) out vec2 texCoord0;\n#ifdef GLINT\nlayout(location = 7) out vec2 texCoordGlint;\n#endif\n",
        "layout(location = 6) out vec2 texCoord0;\n#ifdef GLINT\nlayout(location = 7) out vec2 texCoordGlint;\n#endif\n"
        "layout(location = 8) out vec3 spdParams; // SPD: xy = 内層UV, z = 部位番号\n",
        "vsh varyings")
    out = replace_once(
        out,
        "void main() {\n    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);\n\n"
        "    sphericalVertexDistance = fog_spherical_distance(Position);\n"
        "    cylindricalVertexDistance = fog_cylindrical_distance(Position);\n",
        "void main() {\n    vec3 pos = Position;\n    vec2 uv0 = UV0;\n    vec2 spdUnderUV;\n    float spdPart;\n"
        "    spd_apply(pos, uv0, spdUnderUV, spdPart);\n    spdParams = vec3(spdUnderUV, spdPart);\n\n"
        "    gl_Position = ProjMat * ModelViewMat * vec4(pos, 1.0);\n\n"
        "    sphericalVertexDistance = fog_spherical_distance(pos);\n"
        "    cylindricalVertexDistance = fog_cylindrical_distance(pos);\n",
        "vsh main head")
    out = replace_once(out, "    texCoord0 = UV0;\n", "    texCoord0 = uv0;\n", "vsh texCoord0")
    out = replace_once(out, "(TextureMat * vec4(UV0, 0.0, 1.0)).xy", "(TextureMat * vec4(uv0, 0.0, 1.0)).xy",
                       "vsh texture matrix", count=2)

    # 検査: Position / UV0 は「宣言」と「コピー」でのみ現れること
    for i, line in enumerate(out.split("\n"), 1):
        if re.search(r"\bPosition\b", line) and not ("in vec3 Position" in line or "vec3 pos = Position" in line
                                                     or line.lstrip().startswith("//") or "Position.y" in line):
            raise SystemExit("Position の参照が残っています (line %d): %s" % (i, line))
        if re.search(r"\bUV0\b", line) and not ("in vec2 UV0" in line or "vec2 uv0 = UV0" in line):
            raise SystemExit("UV0 の参照が残っています (line %d): %s" % (i, line))
    if out.count("{") != out.count("}"):
        raise SystemExit("波括弧の数が合いません (vsh)")
    return out


def patch_entity_fsh(src):
    out = src
    out = replace_once(
        out,
        "layout(location = 6) in vec2 texCoord0;\n#ifdef GLINT\nlayout(location = 7) in vec2 texCoordGlint;\n#endif\n",
        "layout(location = 6) in vec2 texCoord0;\n#ifdef GLINT\nlayout(location = 7) in vec2 texCoordGlint;\n#endif\n"
        "layout(location = 8) in vec3 spdParams; // SPD: xy = 内層UV, z = 部位番号\n" + FSH_DECL,
        "fsh varyings")
    out = replace_once(out, "    color *= faceVertexColor * ColorModulator;\n",
                       "    color *= faceVertexColor * ColorModulator;\n" + FSH_BLOCK, "fsh color")
    if out.count("{") != out.count("}"):
        raise SystemExit("波括弧の数が合いません (fsh)")
    return out


# ---------------------------------------------------------------------------
def read_vanilla_shaders(path):
    """--shaders から core/entity.vsh と core/entity.fsh を取り出す。"""
    want = ("core/entity.vsh", "core/entity.fsh")
    found = {}
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), path).replace(os.sep, "/")
                for w in want:
                    if rel.endswith(w):
                        found[w] = open(os.path.join(root, f), encoding="utf-8").read()
    else:
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                for w in want:
                    if n.endswith(w):
                        found[w] = z.read(n).decode("utf-8")
    missing = [w for w in want if w not in found]
    if missing:
        raise SystemExit("--shaders に %s が見つかりません" % ", ".join(missing))
    return found["core/entity.vsh"], found["core/entity.fsh"]


def special(base, transformation):
    return {
        "type": "minecraft:special",
        "base": base,
        "model": {"type": "minecraft:player_head"},
        "transformation": transformation,
    }


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def build_resourcepack(spd_root, z, rp_name, split, vsh_src, fsh_src, out_dir):
    """元の resourcepack(_split) をコピーし、シェーダー・アイテム・pack.mcmeta を 26.3 用に置き換える。"""
    parts = SPLIT_PARTS if split else DEFAULT_PARTS
    dest = os.path.join(out_dir, rp_name)
    prefix = spd_root + rp_name + "/"
    for n in z.namelist():
        if not n.startswith(prefix) or n.endswith("/"):
            continue
        rel = n[len(prefix):]
        # 置き換える物は元のものをコピーしない
        if rel.startswith("assets/minecraft/shaders/") or rel.startswith("assets/animated_java/items/") or rel == "pack.mcmeta":
            continue
        p = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(z.read(n))

    # 元に存在した item 定義と、こちらの part 一覧が一致していることを確認
    orig_items = sorted(os.path.basename(n)[:-5] for n in z.namelist()
                        if n.startswith(prefix + "assets/animated_java/items/") and n.endswith(".json"))
    if orig_items != sorted(parts):
        raise SystemExit("%s: 元の items %s と想定の部位 %s が違う" % (rp_name, orig_items, sorted(parts)))
    # モデルも全部あること
    for p_ in parts:
        for ns in ("", "slim/"):
            f = os.path.join(dest, "assets/animated_java/models/blueprint/player_display/%s%s.json" % (ns, p_))
            if not os.path.exists(f):
                raise SystemExit("モデルが見つかりません: " + f)

    items = os.path.join(dest, "assets/animated_java/items/blueprint/player_display")
    tr = PLAYER_HEAD_TRANSFORMATION
    for part in parts:
        # 通常のパス: custom_model_data の文字列 "slim" で細腕モデルへ切り替える (SPD 本来の方式)
        write_json(os.path.join(items, part + ".json"), {"model": {
            "type": "minecraft:select",
            "property": "minecraft:custom_model_data",
            "cases": [{"when": "slim", "model": special(SLIM_NS + part, tr)}],
            "fallback": special(MODEL_NS + part, tr),
        }})
        # slim/ のパス: item_model に直接 Slim を指定できる (Raw Item Displays 向け)
        write_json(os.path.join(items, "slim", part + ".json"), {"model": special(SLIM_NS + part, tr)})

    sh = os.path.join(dest, "assets/minecraft/shaders/core")
    write_text(os.path.join(sh, "entity.vsh"), patch_entity_vsh(vsh_src, split))
    write_text(os.path.join(sh, "entity.fsh"), patch_entity_fsh(fsh_src))

    write_json(os.path.join(dest, "pack.mcmeta"), {"pack": {
        "description": "Stable Player Display %s (Minecraft 26.3)" % ("Split Model RP" if split else "RP"),
        "min_format": RESOURCE_FORMAT, "max_format": RESOURCE_FORMAT,
    }})
    return dest


# --- ルートテーブル: 26.3 で `functions` -> `modifier`、`function` -> `type` に変わった -------------
def convert_loot_table(old):
    """1.21.x 形式のルートテーブルを 26.3 形式へ。"""
    new = {"type": "minecraft:generic", "pools": []}   # 型指定なしだった元の挙動 (全パラメータ可) と同じ
    for pool in old["pools"]:
        np_ = {k: v for k, v in pool.items() if k != "entries"}
        np_["entries"] = []
        for e in pool["entries"]:
            ne = {k: v for k, v in e.items() if k not in ("functions", "conditions")}
            if "functions" in e:
                mods = []
                for f in e["functions"]:
                    m = {"type": f["function"]}
                    m.update({k: v for k, v in f.items() if k not in ("function", "conditions")})
                    if "conditions" in f:
                        raise SystemExit("conditions を持つ関数は未対応")
                    mods.append(m)
                ne["modifier"] = mods if len(mods) != 1 else mods[0]
            if "conditions" in e:
                raise SystemExit("conditions を持つエントリは未対応")
            np_["entries"].append(ne)
        new["pools"].append(np_)
    return new


def build_sample_datapack(spd_root, z, out_dir):
    src = spd_root + "animated-java-resources/sample_datapack/"
    dest = os.path.join(out_dir, "animated-java-resources", "sample_datapack")
    for n in z.namelist():
        if not n.startswith(src) or n.endswith("/"):
            continue
        rel = n[len(src):]
        p = os.path.join(dest, rel)
        if rel == "pack.mcmeta":
            write_json(p, {"pack": {"description": "Stable Player Display sample datapack (26.3)",
                                    "min_format": DATA_FORMAT, "max_format": DATA_FORMAT}})
        elif rel.startswith("data/minecraft/loot_table/") and rel.endswith(".json"):
            write_json(p, convert_loot_table(json.loads(z.read(n).decode("utf-8"))))
        else:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(z.read(n))
    return dest


def retarget_blueprint(data, name):
    """ブループリントの書き出し先バージョンを 26.3 にする (他は 1 バイトも変えない)。"""
    text = data.decode("utf-8")
    pat = re.compile(r'("target_minecraft_version"\s*:\s*)"[^"]*"')
    if len(pat.findall(text)) != 1:
        raise SystemExit("%s: target_minecraft_version が 1 個ではありません" % name)
    return pat.sub(r'\1"26.3"', text).encode("utf-8")


def write_ajmeta(pack_dir, blueprint_id="aj:player_display"):
    """assets.ajmeta を AJ 1.10+ の形式 (rigs[<blueprint_id>].versionedFiles) で書く。
    旧形式 ({"player_display": {"files": [...]}}) は ID が aj:player_display に変わったため一致しなくなる。"""
    base = os.path.join(pack_dir, "assets", "animated_java")
    files = []
    for root, _, fs in os.walk(base):
        for f in sorted(fs):
            files.append(os.path.relpath(os.path.join(root, f), pack_dir).replace(os.sep, "/"))
    files.sort()
    write_json(os.path.join(pack_dir, "assets.ajmeta"),
               {"formatVersion": "1.0.0", "rigs": {blueprint_id: {"versionedFiles": files, "coreFiles": []}}})


def zip_dir(src, zip_path):
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src):
            for f in sorted(files):
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, src).replace(os.sep, "/"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spd", required=True, help="stable_player_display-1.4.1.zip")
    ap.add_argument("--shaders", required=True, help="バニラ 26.3 のシェーダー (ディレクトリ or zip)")
    ap.add_argument("--out", default="out")
    ap.add_argument("--static", default=None,
                    help="手書きファイル(aj-convert.py, README.md 等)を置いたディレクトリ。release へそのままコピー")
    a = ap.parse_args()

    vsh_src, fsh_src = read_vanilla_shaders(a.shaders)
    release = os.path.join(a.out, "stable_player_display-26.3")
    if os.path.isdir(release):
        shutil.rmtree(release)
    os.makedirs(release)

    with zipfile.ZipFile(a.spd) as z:
        lic = [n for n in z.namelist() if n.endswith("/LICENSE")]
        if not lic:
            raise SystemExit("--spd に LICENSE が見つかりません (SPD 1.4.1 の zip ではない?)")
        spd_root = lic[0][:-len("LICENSE")]

        rp = build_resourcepack(spd_root, z, "resourcepack", False, vsh_src, fsh_src, release)
        rps = build_resourcepack(spd_root, z, "resourcepack_split", True, vsh_src, fsh_src, release)
        sample = build_sample_datapack(spd_root, z, release)

        # 変更しないファイル
        for n in z.namelist():
            if n.endswith("/"):
                continue
            rel = n[len(spd_root):]
            if rel in ("LICENSE",) or rel.startswith("assets/") and not rel.startswith("assets/minecraft") \
                    or rel.startswith("animated-java-resources/") and (rel.endswith(".ajblueprint")):
                p = os.path.join(release, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                data = z.read(n)
                if rel.endswith(".ajblueprint"):
                    data = retarget_blueprint(data, rel)
                with open(p, "wb") as f:
                    f.write(data)

    write_ajmeta(rp)
    write_ajmeta(rps)

    if a.static:
        for root, _, files in os.walk(a.static):
            for f in files:
                srcp = os.path.join(root, f)
                rel = os.path.relpath(srcp, a.static)
                dst = os.path.join(release, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(srcp, dst)

    zip_dir(rp, os.path.join(a.out, "stable_player_display_26_3.zip"))
    zip_dir(rps, os.path.join(a.out, "stable_player_display_26_3_split.zip"))
    zip_dir(sample, os.path.join(a.out, "stable_player_display_26_3_sample_datapack.zip"))
    zip_dir(release, os.path.join(a.out, "stable_player_display-26.3.zip"))
    print("OK:", release)
    for n in sorted(os.listdir(a.out)):
        if n.endswith(".zip"):
            print("  ", n, os.path.getsize(os.path.join(a.out, n)), "bytes")


if __name__ == "__main__":
    main()
