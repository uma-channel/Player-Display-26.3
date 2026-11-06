[English](README.md) | 日本語

# Player Display for 26.3

- 26.3において、リソースパックとディスプレイエンティティのみを使用して任意のプレイヤースキンを表示します。
- [bradleyq](https://github.com/bradleyq) 氏の [Stable Player Display](https://github.com/bradleyq/stable_player_display) からフォークされています。

## 注意

- `item_display` エンティティでのみ使用してください。
- モデル内のいかなるボーンについても、**Rotation[1] NBT（ピッチ）を変更しないでください**。
- モデルはプレイヤーからの**垂直距離**で512メートルを超えて読み込むことはできません（水平距離の制限はありません）。
- アニメーションに `transformation.translation[1]` を使用する場合は、必要なYオフセットを引いてください（AJを使用している場合、スクリプトがこれを自動処理します）。
- **Minecraft バニラ**の更新にのみ対応します。Modクライアント環境で動作が破損した場合のサポートはありません。

## 使い方 (サンプルデータパック)

`pd: _` にデータを設定し、ファンクションを実行してください！

### 設定
```
data modify storage pd: _ set value {id:"example",name:"Steve",slim:false}
```

### 召喚
```
function #pd:
```

### 削除
```
function pd:remove {id:"example"}
```

> **_NOTE:_**  分割モデルの場合、追加の `right_forearm`、`left_forearm`、`lower_right_leg`、`lower_left_leg` モデルが存在します。

### List of Data Available in `_`
- id
> プレイヤーディスプレイのID。
- name
> プレイヤーディスプレイのMCID（スキン）。
- slim
> スリムモデルを使用するかどうか: True/False

---

### Slim Checker
プレイヤーのスキンがスリムかどうかを判定するには、猫愛氏の[Slim Checker](https://github.com/nea-c/SlimChecker)を使用できます。

---

## License

詳細については [LICENSE](LICENSE) を参照してください。
