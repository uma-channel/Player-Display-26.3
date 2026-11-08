#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aj-convert.py のテスト。

注意: ここで作る擬似書き出しは、Animated Java 1.11 のソース (datapackCompiler の main.mcb /
boneDispatch.ts / index.ts) から読み取った出力形式を再現したものです。実際の AJ が書き出した
データパックで確かめたものではありません。AJ の出力形式が変わった場合は、まずこのテストの
フィクスチャを実物に合わせて更新してください。

    python tests/test_aj_convert.py
"""
import importlib.util
import os
import random
import re
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("aj_convert", os.path.join(HERE, "..", "aj-convert.py"))
aj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aj)

BID = "aj:player_display"
PREFIX = "aj.player_display"
LIST_RE = re.compile(r"transformation\s*:\s*\[([^\]]*)\]")


def matrix(rng, ty):
    v = [round(rng.uniform(-1, 1), 4) for _ in range(16)]
    v[7] = ty
    return "[" + ",".join("%sf" % x for x in v) + "]"


def passenger(name, with_ws=False):
    tr = "translation:[ 0f , 0f , 0f ]" if with_ws else "translation:[0f,0f,0f]"
    return (
        '{Tags:["%(p)s.node.%(n)s","%(p)s.bone.%(n)s","%(p)s.display_node.%(n)s"],height:48f,width:48f,'
        'teleport_duration:1,interpolation_duration:1,'
        'transformation:{%(tr)s,left_rotation:[0f,0f,0f,1f],scale:[0f,0f,0f],right_rotation:[0f,0f,0f,1f]},'
        'id:"minecraft:item_display",item:{id:"minecraft:white_dye",count:1,components:{"minecraft:item_model":'
        '"aj:blueprint/player_display/%(n)s","minecraft:custom_model_data":{strings:["default"]}}},item_display:"head"}'
    ) % dict(p=PREFIX, n=name, tr=tr)


def make_pack(root, bones, extra_bone="extra_node"):
    """AJ 1.11 風の書き出しを root に作る。戻り値: 元の行列 {(file, 行番号, 名前): [16個の文字列]}"""
    rng = random.Random(7)
    fdir = os.path.join(root, "data", "aj", "function", "player_display")
    os.makedirs(os.path.join(fdir, "zzz"))
    os.makedirs(os.path.join(fdir, "animations", "walk_cycle", "zzz", "frames"))
    with open(os.path.join(root, "pack.mcmeta"), "w") as f:
        f.write('{"pack":{"description":"t","min_format":121,"max_format":121}}')

    # ---- summon: ボーン + 変換対象外のノード + ロケーター。CustomName に括弧入りの文字列
    pas = [passenger(b, with_ws=(i == 3)) for i, b in enumerate(bones)]
    pas.append(passenger(extra_bone))
    pas.append('{Tags:["%s.node.loc","%s.locator.loc"],id:"minecraft:marker"}' % (PREFIX, PREFIX))
    summon = (
        "data modify storage aj:player_display args set value {variant:'',animation:'',frame:0}\n"
        "execute unless entity @s run say [ { not a bone } ]\n"
        'summon minecraft:item_display ~ ~ ~ {Tags:["aj.global.entity","%s.root"],teleport_duration:0,'
        "Passengers:[%s],CustomName:'{\"text\":\"Root {x} ] , [ \"}',}\n"
        "function aj:player_display/zzz/set_default_pose\n"
    ) % (PREFIX, ",".join(pas))
    with open(os.path.join(fdir, "summon.mcfunction"), "w") as f:
        f.write(summon)

    # ---- ポーズ (マクロ形式)
    for fname, interp in (("set_default_pose", -1), ("apply_default_pose", 0)):
        lines = []
        for b in bones + [extra_bone]:
            lines.append("$data merge entity $(%s) {transformation: %s, start_interpolation: %d}\n" % (b, matrix(rng, round(rng.uniform(-5, 5), 3)), interp))
        with open(os.path.join(fdir, "zzz", fname + ".mcfunction"), "w") as f:
            f.write("".join(lines))

    # ---- フレーム (関数形式。ボーンごとの仕分け)
    fr = os.path.join(fdir, "animations", "walk_cycle", "zzz", "frames")
    for n in range(4):
        lines = []
        for b in bones + [extra_bone]:
            lines.append(
                "execute if entity @s[tag=%s.node.%s] run return run data merge entity @s "
                "{transformation: %s,start_interpolation: 0,interpolation_duration: 1}\n" % (PREFIX, b, matrix(rng, round(rng.uniform(-30, 30), 4))))
        with open(os.path.join(fr, "%d_bones_0.mcfunction" % n), "w") as f:
            f.write("".join(lines))
        with open(os.path.join(fr, "%d_bones.mcfunction" % n), "w") as f:  # グループ仕分けのみ (行列なし)
            f.write("execute if entity @s[tag=%s.node_group.0] run return run function aj:player_display/animations/walk_cycle/zzz/frames/%d_bones_0\n" % (PREFIX, n))
        with open(os.path.join(fr, "%d.mcfunction" % n), "w") as f:
            f.write("execute on passengers run function aj:player_display/animations/walk_cycle/zzz/frames/%d_bones\n" % n)

    # ---- ストレージ形式 (use_storage_for_animation)
    frames = []
    for n in range(3):
        ent = ",".join("%s:{transformation:%s,start_interpolation:0}" % (b, matrix(rng, round(rng.uniform(-9, 9), 3))) for b in bones + [extra_bone])
        frames.append('"%d":{%s}' % (n, ent))
    with open(os.path.join(fdir, "animations", "walk_cycle", "zzz", "store.mcfunction"), "w") as f:
        f.write("data modify storage aj:player_display/animations walk_cycle merge value {%s}\n" % ",".join(frames))
    return fdir


def num(text):
    return Decimal(text.strip().rstrip("fF"))


def read_text(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def read_all(root):
    out = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, root)] = read_text(p)
    return out


def lists_with_names(text):
    """行内の transformation リストを、直前の名前 (macro / tag / key) とともに列挙。"""
    res = []
    for line in text.splitlines():
        for m in LIST_RE.finditer(line):
            pre = line[:m.start()]
            name = None
            for pat in (r"\$data merge entity \$\((\w+)\)", r"\.node\.(\w+)\]", r"(\w+):\{$"):
                mm = re.search(pat, pre)
                if mm:
                    name = mm.group(1)
                    break
            res.append((name, [x.strip() for x in m.group(1).split(",")]))
    return res


class ConvertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_convert(self, *extra, bones=None, expect=0):
        bones = bones or list(aj.DEFAULT_OFFSETS)
        make_pack(self.tmp, bones)
        before = read_all(self.tmp)
        rc = aj.main([BID, "--datapack", self.tmp] + list(extra))
        self.assertEqual(rc, expect)
        return before, read_all(self.tmp)

    # ---- 行列の検証: ボーンは添字 7 だけが offset 分ずれ、他は一切変わらない
    def check_lists(self, before, after, offsets):
        n_changed = 0
        for path in before:
            if path.endswith("summon.mcfunction") or not path.endswith(".mcfunction"):
                continue
            b, a = lists_with_names(before[path]), lists_with_names(after[path])
            self.assertEqual(len(b), len(a), path)
            for (nb, vb), (na, va) in zip(b, a):
                self.assertEqual(nb, na)
                self.assertEqual(len(va), 16)
                for i in range(16):
                    if nb in offsets and i == 7:
                        want = Decimal(vb[i].rstrip("f")) + Decimal(offsets[nb])
                        self.assertEqual(Decimal(va[i].rstrip("f")), want, "%s %s" % (path, nb))
                        if offsets[nb]:
                            n_changed += 1
                    else:
                        self.assertEqual(va[i], vb[i], "%s %s idx%d" % (path, nb, i))
        return n_changed

    def test_default_full(self):
        before, after = self.run_convert("-pn=jeb_")
        off = aj.DEFAULT_OFFSETS
        changed = self.check_lists(before, after, off)
        # ポーズ2ファイル + フレーム4 + ストレージ3 フレーム分のボーン (head=0 は値が変わらない)
        self.assertEqual(changed, 5 * (2 + 4 + 3))

        s = after["data/aj/function/player_display/summon.mcfunction"]
        # 他の行は無変更
        for line in before["data/aj/function/player_display/summon.mcfunction"].splitlines():
            if not line.startswith("summon "):
                self.assertIn(line, s)
        for name, o in off.items():
            m = re.search(r'\{Tags:\["%s\.node\.%s".*?item_display:"[^"]*"\}' % (re.escape(PREFIX), name), s)
            self.assertIsNotNone(m, name)
            p = m.group(0)
            self.assertIn('item_display:"thirdperson_righthand"', p)
            self.assertIn('id:"minecraft:player_head"', p)
            self.assertIn('"minecraft:profile":{name:"jeb_"}', p)
            tm = re.search(r"transformation:\{translation:\[\s*([^,\]]+),\s*([^,\]]+),\s*([^,\]\s]+)\s*\]", p)
            self.assertEqual(num(tm.group(2)), Decimal(o), name)
            self.assertEqual(num(tm.group(1)), 0)
            self.assertEqual(num(tm.group(3)), 0)
            self.assertIn('"minecraft:item_model":"aj:blueprint/player_display/%s"' % name, p)  # 既存コンポーネントは残る
        # 対象外ノード・ロケーター・ルート部分は 1 文字も変わらない
        for orig in re.findall(r'\{Tags:\["[^"]*(?:extra_node|loc)".*?(?:\}\}\}|id:"minecraft:marker"\})', before["data/aj/function/player_display/summon.mcfunction"]):
            self.assertIn(orig.split(",item_display")[0], s)
        self.assertIn("CustomName:'{\"text\":\"Root {x} ] , [ \"}',}", s)
        self.assertIn('Tags:["aj.global.entity","aj.player_display.root"],teleport_duration:0,Passengers:[', s)
        self.assertEqual(s.count('item_display:"thirdperson_righthand"'), 6)
        self.assertEqual(s.count('item_display:"head"'), 1)  # extra_node

        # 変更しなかったファイル (グループ仕分け・フレーム入口) はバイト単位で同一
        for path in before:
            if path.endswith("_bones.mcfunction") or re.search(r"/\d\.mcfunction$", path) or path == "pack.mcmeta":
                self.assertEqual(before[path], after[path], path)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, aj.MARKER)))

    def test_no_player_name_makes_air(self):
        _, after = self.run_convert()
        s = after["data/aj/function/player_display/summon.mcfunction"]
        self.assertEqual(s.count('id:"minecraft:air"'), 6)
        self.assertNotIn("minecraft:profile", s)

    def test_split_offsets(self):
        bones = list(aj.SPLIT_OFFSETS)
        before, after = self.run_convert("-split", "-pn=Steve", bones=bones)
        self.check_lists(before, after, aj.SPLIT_OFFSETS)
        s = after["data/aj/function/player_display/summon.mcfunction"]
        self.assertEqual(s.count('item_display:"thirdperson_righthand"'), 11)
        self.assertIn("-10240.0f", s)

    def test_dry_run_changes_nothing(self):
        before, after = self.run_convert("--dry-run", "-pn=jeb_")
        self.assertEqual(before, after)

    def test_second_run_refused(self):
        _, after = self.run_convert("-pn=jeb_")
        rc = aj.main([BID, "--datapack", self.tmp, "-pn=jeb_"])
        self.assertEqual(rc, 1)
        self.assertEqual(after, read_all(self.tmp))

    def test_wrong_prefix_changes_nothing(self):
        make_pack(self.tmp, list(aj.DEFAULT_OFFSETS))
        before = read_all(self.tmp)
        rc = aj.main([BID, "--datapack", self.tmp, "--tag-prefix", "nope.nope"])
        self.assertEqual(rc, 1)
        self.assertEqual(before, read_all(self.tmp))

    def test_bad_inputs(self):
        make_pack(self.tmp, list(aj.DEFAULT_OFFSETS))
        before = read_all(self.tmp)
        self.assertEqual(aj.main([BID, "--datapack", self.tmp, "-pn=bad name!"]), 1)
        self.assertEqual(aj.main(["aj:missing", "--datapack", self.tmp]), 1)
        self.assertEqual(aj.main([BID, "--datapack", os.path.join(self.tmp, "nowhere")]), 1)
        self.assertEqual(before, read_all(self.tmp))

    def test_plain_id_resolves_to_aj_namespace(self):
        make_pack(self.tmp, list(aj.DEFAULT_OFFSETS))
        self.assertEqual(aj.main(["player_display", "--datapack", self.tmp, "--dry-run"]), 0)

    def test_crlf_preserved(self):
        make_pack(self.tmp, list(aj.DEFAULT_OFFSETS))
        p = os.path.join(self.tmp, "data/aj/function/player_display/zzz/set_default_pose.mcfunction")
        t = read_text(p).replace("\n", "\r\n")
        with open(p, "w", newline="") as fh:
            fh.write(t)
        self.assertEqual(aj.main([BID, "--datapack", self.tmp]), 0)
        self.assertEqual(read_text(p).count("\r\n"), t.count("\r\n"))

    def test_number_formatting(self):
        self.assertEqual(aj.fmt_float(Decimal("-1024")), "-1024.0f")
        self.assertEqual(aj.fmt_float(Decimal("0.3123") + Decimal(-1024)), "-1023.6877f")
        self.assertEqual(aj.fmt_float(Decimal("1024") + Decimal(-1024)), "0.0f")
        self.assertEqual(aj.shift_num(" 1.5f", -1024), " -1022.5f")
        self.assertEqual(aj.shift_num("2", -1), "1.0f")


if __name__ == "__main__":
    unittest.main(verbosity=2)
