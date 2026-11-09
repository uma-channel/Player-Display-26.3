[English](README.md) | 日本語

# (Stable) Player Display 26.3

[bradleyq/stable_player_display](https://github.com/bradleyq/stable_player_display) を、
[erkko68 の AJ 対応フォーク 1.4.1](https://github.com/erkko68/stable_player_display) を土台に **Minecraft JE 26.3** へ移植したものです。

Animated Java (AJ) 1.11 の書き出しに対応しています。

# 動作確認状況

- Minecraft JE 26.3 にて [sample datapack](sample_datapack) 及び [resourcepack](resourcepack) 、 [resourcepack_split](resourcepack_split) の動作確認済み。
- AJ は テスト用のツールでのみ動作確認済み。

## 同梱物

| パス | 内容 |
|---|---|
| `resourcepack/` | リソースパック (通常モデル) |
| `resourcepack_split/` | リソースパック (分割モデル: ひじ・腰・ひざ付き) |
| `animated-java-resources/aj-convert.py` | AJ 書き出しデータパックの変換スクリプト |
| `animated-java-resources/player.ajblueprint` / `player_split.ajblueprint` | AJ 用ブループリント (書き出し先を 26.3 に設定済み) |
| `animated-java-resources/sample_datapack/` | スキン更新用のルートテーブルと関数 |
| `animated-java-resources/tests/` | `aj-convert.py` のテスト |
| `tools/` | 移植に使ったビルドスクリプトとシェーダーのテスト |

## 制限

- `item_display` エンティティ専用です。
- ボーンの **`Rotation[1]` (ピッチ) は変更しないでください**。
- プレイヤーから**垂直方向に 512m 以上**離れると崩れます (水平方向は無制限)。
- アニメーションで `transformation.translation[1]` を使う場合は、部位のオフセットを引いてください (AJ なら `aj-convert.py` が処理します)。
- バニラ専用です。MOD 環境は対象外です。
- `core/entity.vsh` / `core/entity.fsh` を差し替える他のパックとは競合します。

## リソースパック導入

`resourcepack` か `resourcepack_split` の**どちらか一方**をリソースパックとして有効にします (両方は不可)。

## 使い方

### [Sample Datapack](sample_datapack)

#### 設定
```mcfunction
data modify storage pd: _ set value {id:"example",name:"Alex",slim:true,split:true}
```

#### 召喚
```mcfunction
function #pd:
```

#### 削除
```mcfunction
function pd:remove {id:"example"}
```

#### `_`に入れられる設定
- id
> プレイヤーディスプレイのID。(必須)
- name
> プレイヤーディスプレイに使うMCID(スキン)。(任意)
- slim
> スリムモデルを使うかどうか: True/False (デフォルトはfalse)
- split
> 分割モデルを使うかどうか: True/False (デフォルトはfalse) 

**詳しくは[sample_datapack](sample_datapack)を覗いてください。** 

## Slim Checker 26.3

[Slim Checker](https://github.com/uma-channel/Slim-Checker-26.3) を使用してプレイヤーのスキンがスリムかどうかをチェックできます。

## Animated Java: データパック

対象は **AJ 1.11 以降**です (26.3 対応版)。

1. `animated-java-resources/player.ajblueprint` (分割版は `player_split.ajblueprint`) を AJ で開き、書き出します。Blueprint ID は `aj:player_display` のままにしてください (後述のタグ・サンプルがこの名前を前提にしています)。
   **「Use Storage for Animations」も変換に対応しました** (1.4.1 では非対応でした)。
2. 書き出したデータパックのルート (`data` フォルダの隣) で変換します。
   ```py
   python aj-convert.py aj:player_display -pn=jeb_
   python aj-convert.py aj:player_display -pn=jeb_ -split      # 分割モデル
   python aj-convert.py aj:player_display --dry-run            # 書き換えずに確認だけ
   ```
   | オプション | 内容 |
   |---|---|
   | `-pn=NAME` | スキンを借りるプレイヤー名。省略するとアイテムは `air` (ゲーム内で後から設定) |
   | `-split` | 分割モデルのオフセットを使う |
   | `--dry-run` | 何も書き換えず、変換対象の件数だけ表示 |
   | `--force` | 変換済みの印があっても実行 (**二重適用に注意**) |
   | `--tag-prefix P` | タグ接頭辞を直接指定 (既定は Blueprint ID の `:` `/` を `.` にしたもの) |
   | `--datapack DIR` | データパックのルート (既定はカレントディレクトリ) |

   スクリプトは **Python 3.8 以上だけ**で動きます (旧版で必要だった `nbtlib` は不要)。
   変換対象が見つからない場合は、何も書き換えずにエラーで止まります。変換後はルートに `spd_aj_convert.json` を作り、同じ書き出しへの再実行を止めます。
3. AJ が一緒に書き出したリソースパックは不要なので削除します (PD のリソースパックを使います)。

### Animated Java: プラグインモード (未対応)

元の SPD と同じく、スクリプトは対応していません。ブループリントを読み込む側で、ボーンの Y 移動に下表のオフセットを足し、`item_display` を `thirdperson_righthand` にして、`item_model` を設定してください。

## 部位オフセット

| 部位 | Y オフセット |
|---|---|
| head | 0 |
| right_arm | -1024 |
| left_arm | -2048 |
| torso | -3072 |
| right_leg | -4096 |
| left_leg | -5120 |
| right_forearm (分割) | -6144 |
| left_forearm (分割) | -7168 |
| waist (分割) | -8192 |
| lower_right_leg (分割) | -9216 |
| lower_left_leg (分割) | -10240 |

## 分割モデル

腕・脚に関節を足し、腰を独立させたモデルです。`resourcepack_split` と `player_split.ajblueprint`、`aj-convert.py -split` を**セットで**使います。

## AJ 1.11 のバリアントについて

1.4.1 の README には「Slim バリアントでモデルを切り替える」とありました。AJ 1.11 は 1.21.4 以降で、ボーンのアイテムの `custom_model_data.strings` に**バリアント名ではなくテクスチャスロットの現在のテクスチャ**を入れます。そのため、バリアントを切り替えても SPD の Slim 選択は変わりません。Slim は上記のルートテーブル (`custom_model_data` を直接設定) か `item_model` で指定してください。

## 困ったとき

- **モデルが見えない**: 手順の飛ばしが最も多い原因です。リソースパックの有効化、F3+T、`item_model` のパス、`profile` (スキン)、`translation[1]` のオフセット、`item_display:"thirdperson_righthand"` を確認してください。
- **上下・前後が逆、位置がずれる**: アイテム定義の `transformation` を確認します (`left_rotation` が `[1,0,0,0]` であること)。
- **体は出るがスキンの貼り方がおかしい**: 26.3 の頭モデルの頂点順が旧版と違う可能性があります。再現した状態のスクリーンショットを添えて報告してください (頂点順から `spd_apply()` を直します)。
- **外層だけ消える/ちらつく**: 半透明処理 (OIT) まわりです。報告してください。
- **`aj-convert.py` がエラーで止まる**: メッセージをよく読んでください。「変換対象が見つかりません」は、Blueprint ID・タグ接頭辞 (`--tag-prefix`)・書き出しの形式のどれかが想定と違います。
- **変換済みと言われる**: 同じ書き出しに 2 回かけると壊れるための安全装置です。再書き出ししたデータパックに実行してください。
- **ピボットを編集したらモデルが歪む**: リソースパックの各パーツの `translation` を手で合わせる必要があります。

## 報告するとき

AJ のバージョン、使ったコマンドやオプション、ログ全文、スクリーンショットを添えてください。

ただし、必ずしも対応するとは限りません。

## クレジットとライセンス

- **[bradleyq](https://github.com/bradleyq/stable_player_display)**: 原作者
- **[erkko68](https://github.com/erkko68/stable_player_display)**: AJ 対応フォーク
- **Resonance#3633**: カスタムモデルとテンプレート
- **[sireroo](https://github.com/sireroo)**: 着想

詳細については [LICENSE](LICENSE) を参照してください。
