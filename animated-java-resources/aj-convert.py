#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stable Player Display 26.3 -- Animated Java 変換スクリプト (CC0)

Animated Java (AJ) 1.11 以降が書き出したデータパックを、SPD 用に書き換えます。
  * 各ボーンの Y 位置に部位ごとのオフセット (-1024 * 部位番号) を足す
      - summon の Passengers (初期 translation)
      - zzz/set_default_pose / zzz/apply_default_pose
      - アニメーションの全フレーム (関数形式 / ストレージ形式の両方)
  * ボーンのアイテムを player_head にして item_display を thirdperson_righthand にする
    (-pn を指定しない場合、アイテムは air。スキンはルートテーブルで入れる)

使い方 (データパックのルート = pack.mcmeta があるフォルダ で実行):
    python aj-convert.py aj:player_display
    python aj-convert.py aj:player_display -pn=jeb_ -split
    python aj-convert.py aj:player_display --dry-run

  [blueprint_id]   AJ の Blueprint ID (既定の名前空間は aj)。"player_display" だけでも可。
  -pn=NAME         スキンを借りるプレイヤー名 (既定: なし)
  -split           分割モデル (ひじ・腰・ひざ付き) のオフセットを使う
  --dry-run        ファイルを書き換えず、何が変わるかだけ表示する
  --force          変換済みの印があっても実行する (二重適用に注意)
  --tag-prefix P   タグの接頭辞を直接指定 (既定: Blueprint ID の ':' と '/' を '.' にしたもの)
  --datapack DIR   データパックのルート (既定: カレントディレクトリ)

必要なもの: Python 3.8 以上のみ (nbtlib は不要)。
同じ書き出しに対して 2 回実行しないでください (オフセットが二重に加算されます)。
2 回目は、印のファイル spd_aj_convert.json を見つけて停止します。
"""
import argparse
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation

VERSION = "26.3.0"
MARKER = "spd_aj_convert.json"

DEFAULT_OFFSETS = {
    "head": 0, "right_arm": -1024, "left_arm": -2048,
    "torso": -3072, "right_leg": -4096, "left_leg": -5120,
}
SPLIT_OFFSETS = {
    "head": 0, "right_arm": -1024, "right_forearm": -6144,
    "left_arm": -2048, "left_forearm": -7168, "torso": -3072,
    "waist": -8192, "right_leg": -4096, "lower_right_leg": -9216,
    "left_leg": -5120, "lower_left_leg": -10240,
}
ITEM_DISPLAY = "thirdperson_righthand"
PLAYER_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")


class ConvertError(Exception):
    pass


# --------------------------------------------------------------------------- SNBT の字句処理
def scan_string(s, i):
    """s[i] が引用符。閉じ引用符の次の位置を返す。"""
    q = s[i]
    i += 1
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == q:
            return i + 1
        i += 1
    raise ConvertError("閉じていない文字列があります")


def match_bracket(s, i):
    """s[i] が { か [。対応する閉じ括弧の位置を返す (文字列内の括弧は無視)。"""
    pairs = {"{": "}", "[": "]"}
    stack = []
    while i < len(s):
        c = s[i]
        if c in "\"'":
            i = scan_string(s, i)
            continue
        if c in pairs:
            stack.append(pairs[c])
        elif c in "}]":
            if not stack or stack.pop() != c:
                raise ConvertError("括弧の対応が取れません")
            if not stack:
                return i
        i += 1
    raise ConvertError("閉じていない括弧があります")


def list_items(s, open_idx):
    """s[open_idx] == '[' のリストの、直下の要素の (start, end) を順に返す。"""
    close = match_bracket(s, open_idx)
    i = open_idx + 1
    while i < close:
        while i < close and s[i] in " \t\r\n,":
            i += 1
        if i >= close:
            break
        start = i
        if s[i] in "{[":
            end = match_bracket(s, i) + 1
        elif s[i] in "\"'":
            end = scan_string(s, i)
        else:
            end = i
            while end < close and s[end] != ",":
                end += 1
        yield start, end
        i = end


# --------------------------------------------------------------------------- 数値
NUM_RE = re.compile(r"^(\s*)([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)([fFdDbBsSlL]?)(\s*)$")


def parse_num(text):
    m = NUM_RE.match(text)
    if not m:
        raise ConvertError("数値として読めません: %r" % text)
    try:
        return m.group(1), Decimal(m.group(2)), m.group(4)
    except InvalidOperation:
        raise ConvertError("数値として読めません: %r" % text)


def fmt_float(d):
    t = format(d.normalize(), "f")
    if "." not in t:
        t += ".0"
    if t in ("-0.0", "+0.0"):
        t = "0.0"
    return t + "f"


def shift_num(text, offset):
    """'0.5f' のような要素に offset を足した文字列 (前後の空白は保持)。"""
    lead, val, trail = parse_num(text)
    return lead + fmt_float(val + Decimal(offset)) + trail


def shift_list_index(body, index, offset, expect_len=None):
    """'a, b, c' 形式のリスト本体の index 番目に offset を足す。"""
    parts = body.split(",")
    if expect_len is not None and len(parts) != expect_len:
        raise ConvertError("要素数が %d ではありません (%d)" % (expect_len, len(parts)))
    parts[index] = shift_num(parts[index], offset)
    return ",".join(parts)


MATRIX_RE = re.compile(r"(transformation\s*:\s*\[)([^\]]*)(\])")


def shift_matrix_in(text, offset):
    """text 内の最初の transformation:[16 個] の Y 移動 (添字 7) に offset を足す。(新text, 変更あり)"""
    m = MATRIX_RE.search(text)
    if not m:
        return text, False
    body = shift_list_index(m.group(2), 7, offset, 16)
    return text[:m.start(2)] + body + text[m.end(2):], True


# --------------------------------------------------------------------------- summon の Passengers
def edit_passenger(p, name, offset, player_name):
    """Passenger 1 体分の SNBT を書き換える。"""
    # (1) transformation の translation の Y (複合タグ形式) か、行列形式の添字 7
    mc = re.search(r"transformation\s*:\s*\{", p)
    if mc:
        open_idx = mc.end() - 1
        close = match_bracket(p, open_idx)
        inner = p[open_idx:close + 1]
        mt = re.search(r"(translation\s*:\s*\[)([^\]]*)(\])", inner)
        if not mt:
            raise ConvertError("%s: translation が見つかりません" % name)
        body = shift_list_index(mt.group(2), 1, offset, 3)
        inner = inner[:mt.start(2)] + body + inner[mt.end(2):]
        p = p[:open_idx] + inner + p[close + 1:]
    else:
        p, ok = shift_matrix_in(p, offset)
        if not ok:
            raise ConvertError("%s: transformation が見つかりません" % name)

    # (2) item_display
    mi = re.search(r"item_display\s*:\s*([\"'])(.*?)\1", p)
    if mi:
        p = p[:mi.start()] + 'item_display:"%s"' % ITEM_DISPLAY + p[mi.end():]
    else:
        p = p[:-1] + ',item_display:"%s"}' % ITEM_DISPLAY

    # (3) item (id と profile)
    mi = re.search(r"\bitem\s*:\s*\{", p)
    if not mi:
        raise ConvertError("%s: item が見つかりません" % name)
    o = mi.end() - 1
    c = match_bracket(p, o)
    item = p[o:c + 1]
    mid = re.search(r"\bid\s*:\s*([\"'])[^\"']*\1", item)
    if not mid:
        raise ConvertError("%s: item の id が見つかりません" % name)
    new_id = "minecraft:player_head" if player_name else "minecraft:air"
    item = item[:mid.start()] + 'id:"%s"' % new_id + item[mid.end():]
    if player_name:
        prof = '"minecraft:profile":{name:"%s"}' % player_name
        mcomp = re.search(r"\bcomponents\s*:\s*\{", item)
        if mcomp:
            q = mcomp.end()
            empty = item[q:].lstrip().startswith("}")
            item = item[:q] + prof + ("" if empty else ",") + item[q:]
        else:
            item = item[:-1] + ",components:{%s}}" % prof
    return p[:o] + item + p[c + 1:]


def convert_summon_line(line, prefix, offsets, player_name):
    """summon minecraft:item_display ... Passengers:[...] の行を書き換える。(新line, 変更したボーン名のリスト)"""
    mp = re.search(r"Passengers\s*:\s*\[", line)
    if not mp:
        return line, []
    open_idx = mp.end() - 1
    changed = []
    out = []
    last = 0  # 行頭から出力する (Passengers より前の部分も残す)
    for start, end in list(list_items(line, open_idx)):
        p = line[start:end]
        if not p.startswith("{"):
            continue
        tm = re.search(r"Tags\s*:\s*\[([^\]]*)\]", p)
        name = None
        if tm:
            for kind in ("bone", "node"):
                mt = re.search(r"[\"']%s\.%s\.(\w+)[\"']" % (re.escape(prefix), kind), tm.group(1))
                if mt:
                    name = mt.group(1)
                    break
        if name is None or name not in offsets:
            continue
        out.append(line[last:start])
        out.append(edit_passenger(p, name, offsets[name], player_name))
        last = end
        changed.append(name)
    out.append(line[last:])
    return "".join(out), changed


# --------------------------------------------------------------------------- ポーズ / フレーム / ストレージ
POSE_RE = re.compile(r"^\s*\$data merge entity \$\((\w+)\)")
FRAME_TAG_RE = None  # prefix 確定後に作る
STORAGE_RE = re.compile(r"(\b[A-Za-z_]\w*)(\s*:\s*\{\s*)(transformation\s*:\s*\[)([^\]]*)(\])")


def convert_pose_line(line, offsets):
    m = POSE_RE.match(line)
    if not m or m.group(1) not in offsets:
        return line, None
    new, ok = shift_matrix_in(line, offsets[m.group(1)])
    return (new, m.group(1)) if ok else (line, None)


def convert_frame_line(line, prefix, offsets):
    if "data merge entity" not in line or "transformation" not in line:
        return line, None
    m = re.search(r"tag=%s\.node\.(\w+)\]" % re.escape(prefix), line)
    if not m or m.group(1) not in offsets:
        return line, None
    new, ok = shift_matrix_in(line, offsets[m.group(1)])
    return (new, m.group(1)) if ok else (line, None)


def convert_storage_line(line, offsets):
    names = []

    def repl(m):
        n = m.group(1)
        if n not in offsets:
            return m.group(0)
        names.append(n)
        return m.group(1) + m.group(2) + m.group(3) + shift_list_index(m.group(4), 7, offsets[n], 16) + m.group(5)

    return STORAGE_RE.sub(repl, line), names


# --------------------------------------------------------------------------- ファイル走査
def convert_text(text, prefix, offsets, player_name, stats, where):
    out = []
    for line in text.splitlines(keepends=True):
        s = line.lstrip()
        if s.startswith("summon minecraft:item_display") and "Passengers" in line:
            new, names = convert_summon_line(line, prefix, offsets, player_name)
            stats["summon_bones"] += len(names)
            if names:
                stats["summon_lines"] += 1
            line = new
        elif s.startswith("$data merge entity $("):
            new, name = convert_pose_line(line, offsets)
            if name:
                stats["pose_lines"] += 1
            line = new
        elif s.startswith("data modify storage") and "merge value" in line:
            new, names = convert_storage_line(line, offsets)
            stats["storage_bones"] += len(names)
            line = new
        elif "data merge entity @s" in line and ".node." in line:
            new, name = convert_frame_line(line, prefix, offsets)
            if name:
                stats["frame_lines"] += 1
            line = new
        out.append(line)
    return "".join(out)


def find_function_dir(root, blueprint_id):
    if ":" in blueprint_id:
        ns, path = blueprint_id.split(":", 1)
        candidates = [(ns, path)]
    else:
        candidates = [("aj", blueprint_id)]
    for ns, path in candidates:
        for fdir in ("function", "functions"):
            d = os.path.join(root, "data", ns, fdir, *path.split("/"))
            if os.path.isdir(d):
                return d, "%s:%s" % (ns, path)
    if ":" not in blueprint_id:  # 他の名前空間を探す
        data = os.path.join(root, "data")
        if os.path.isdir(data):
            for ns in sorted(os.listdir(data)):
                for fdir in ("function", "functions"):
                    d = os.path.join(data, ns, fdir, *blueprint_id.split("/"))
                    if os.path.isfile(os.path.join(d, "summon.mcfunction")):
                        return d, "%s:%s" % (ns, blueprint_id)
    found = []
    data = os.path.join(root, "data")
    if os.path.isdir(data):
        for dp, _, fs in os.walk(data):
            if "summon.mcfunction" in fs:
                found.append(os.path.relpath(dp, data))
    raise ConvertError(
        "Blueprint のフォルダが見つかりません: %s\n  探した場所: %s/data/<名前空間>/function/<パス>/\n  summon.mcfunction があるフォルダ: %s"
        % (blueprint_id, root, ", ".join(found) or "(なし)"))


def run(args):
    root = os.path.abspath(args.datapack)
    if not os.path.isfile(os.path.join(root, "pack.mcmeta")):
        raise ConvertError("%s に pack.mcmeta がありません。データパックのルートで実行するか --datapack で指定してください" % root)
    if args.player_name and not PLAYER_NAME_RE.match(args.player_name):
        raise ConvertError("プレイヤー名は英数字とアンダースコアの 1〜16 文字にしてください: %r" % args.player_name)

    fdir, bid = find_function_dir(root, args.blueprint)
    prefix = args.tag_prefix or bid.replace(":", ".").replace("/", ".")
    offsets = SPLIT_OFFSETS if args.split else DEFAULT_OFFSETS
    marker = os.path.join(root, MARKER)

    print("aj-convert %s" % VERSION)
    print("  Blueprint : %s  (%s)" % (bid, os.path.relpath(fdir, root)))
    print("  タグ接頭辞: %s   モード: %s   スキン: %s" % (prefix, "split" if args.split else "default", args.player_name or "なし"))
    if os.path.exists(marker) and not args.force:
        raise ConvertError("このデータパックは変換済みです (%s)。二重に適用するとオフセットが壊れます。\n  再書き出ししたデータパックに対して実行してください。意図的な場合のみ --force" % MARKER)

    stats = dict(summon_lines=0, summon_bones=0, pose_lines=0, frame_lines=0, storage_bones=0)
    pending = []  # (path, 新しい内容)  -- 全部変換して検査してから、まとめて書き込む
    for dp, _, fs in os.walk(fdir):
        for f in sorted(fs):
            if not f.endswith(".mcfunction"):
                continue
            path = os.path.join(dp, f)
            with open(path, "r", encoding="utf-8", newline="") as fh:
                text = fh.read()
            try:
                new = convert_text(text, prefix, offsets, args.player_name, stats, path)
            except ConvertError as e:
                raise ConvertError("%s: %s" % (os.path.relpath(path, root), e))
            if new != text:
                pending.append((path, new))

    print("  summon     : %d 行 / ボーン %d 体" % (stats["summon_lines"], stats["summon_bones"]))
    print("  ポーズ     : %d 行" % stats["pose_lines"])
    print("  フレーム   : %d 行 (関数形式)  /  ボーン %d 件 (ストレージ形式)" % (stats["frame_lines"], stats["storage_bones"]))
    print("  変更ファイル: %d" % len(pending))

    problems = []
    if stats["summon_bones"] == 0:
        problems.append("summon の Passengers にボーンが見つかりません (タグ接頭辞 %r を確認)" % prefix)
    if stats["pose_lines"] == 0:
        problems.append("zzz/set_default_pose にボーンの行が見つかりません")
    if problems:
        raise ConvertError("変換対象が見つかりませんでした (ファイルは書き換えていません)。\n  - " + "\n  - ".join(problems)
                           + "\n  AJ の書き出し形式が想定と違う可能性があります。")

    if not args.dry_run:
        for path, new in pending:
            tmp = path + ".spdtmp"
            with open(tmp, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
            os.replace(tmp, path)

    if args.dry_run:
        print("  (dry-run: 何も書き換えていません)")
        return
    with open(marker, "w", encoding="utf-8") as fh:
        json.dump({"tool": "aj-convert", "version": VERSION, "blueprint_id": bid,
                   "split": bool(args.split), "player_name": args.player_name or "",
                   "offsets": offsets}, fh, indent=2)
    print("完了。")


def parse_args(argv):
    ap = argparse.ArgumentParser(add_help=True, description="SPD 26.3 用 Animated Java 変換")
    ap.add_argument("blueprint")
    ap.add_argument("-pn", "--player-name", dest="player_name", default="")
    ap.add_argument("-split", "--split", dest="split", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--tag-prefix", default=None)
    ap.add_argument("--datapack", default=".")
    # 旧形式の -pn=NAME も受け付ける
    argv = [("--player-name=" + a[4:]) if a.startswith("-pn=") else a for a in argv]
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(args)
    except ConvertError as e:
        print("エラー: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
