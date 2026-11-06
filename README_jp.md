[English](README.md) | 日本語

# Player Display for 26.3

- 26.3において、リソースパックとDisplayエンティティのみを使用して任意のプレイヤースキンを表示します。
- これは[bradleyq](https://github.com/bradleyq)氏の[Stable Player Display](https://github.com/bradleyq/stable_player_display)のフォークです。

## 制限事項

- `item_display` エンティティでのみ使用してください。
- モデル内のどのボーンにおいても、**Rotation[1] NBT（ピッチ）を変更しないでください**。
- モデルはプレイヤーからの**垂直距離**が512メートルを超える場所からは読み込めません（水平方向の範囲は無制限です）。
- アニメーションに `transformation.translation[1]` を使用する場合は、必要なYオフセットを差し引いてください（AJを使用している場合、スクリプトがこれを処理します）。
- **マインクラフト バニラ**向けにのみ更新されます。MOD環境のクライアントで動作しなくなった場合はサポート対象外となります。

## 使用モード

### 生の Item Display

手動で Item Display を召喚したい場合は、以下のコマンドを使用してください（mcfunction を使用することをお勧めします）:

```
summon minecraft:item_display ~ ~1.4 ~ {Tags:["head"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,0.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
summon minecraft:item_display ~0.25 ~1.4 ~ {Tags:["arm_r"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-1024.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
summon minecraft:item_display ~-0.25 ~1.4 ~ {Tags:["arm_l"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-2048.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
summon minecraft:item_display ~ ~1.4 ~ {Tags:["torso"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-3072.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
summon minecraft:item_display ~0.125 ~0.7 ~ {Tags:["leg_r"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-4096.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
summon minecraft:item_display ~-0.125 ~0.7 ~ {Tags:["leg_l"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-5120.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
```

次に、Display にアイテムを割り当てます:

```
item replace entity @e[tag=head] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/head",minecraft:profile="jeb_"]
item replace entity @e[tag=arm_r] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/right_arm",minecraft:profile="jeb_"]
item replace entity @e[tag=arm_l] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/left_arm",minecraft:profile="jeb_"]
item replace entity @e[tag=torso] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/torso",minecraft:profile="jeb_"]
item replace entity @e[tag=leg_r] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/right_leg",minecraft:profile="jeb_"]
item replace entity @e[tag=leg_l] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/left_leg",minecraft:profile="jeb_"]
```
> **_注記:_** 分割モデルの場合、追加の `right_forearm`、`left_forearm`、`lower_right_leg`、`lower_left_leg` モデルが存在します。
