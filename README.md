English | [日本語](README_jp.md)

# Player Display for 26.3

- Display any player skin using only a resource pack and display entities on 26.3.
- Forked from [Stable Player Display](https://github.com/bradleyq/stable_player_display) by [bradleyq](https://github.com/bradleyq)

## Limitations

- Use only with `item_display` entities.
- **Do NOT modify the Rotation[1]** NBT (pitch) of any bone in the model.
- The model cannot be loaded from more than 512 meters **vertical distance** from the player (unlimited horizontal range).
- If using `transformation.translation[1]` for animations, subtract the required y-offset (if you are using AJ, the script handles this).
- Will only be updated for **Minecraft Vanilla**, if it breaks in a modded client, you are out of luck.

## Usage [Sample Datapack](PlayerDisplay [DP] sample)

Set data in `pd: _` and run the function!

### Display Settings
```
data modify storage pd: _ set value {id:"example",name:"Steve",slim:false}
```

### Summon Player Display
```
function #pd:
```

### Remove Player Display
```
function pd:remove {id:"example"}
```

> **_NOTE:_**  For split models, there are additional `right_forearm`, `left_forearm`, `lower_right_leg`, and `lower_left_leg` models.

### List of Data Available in `_`
- id
> ID of player display.
- name
> MCID (Skin) of player display
- slim
> Whether to use slim model: True/False

---

### Slim Checker
You can use [Slim Checker by NeAc](https://github.com/nea-c/SlimChecker) to determine whether a player's skin is slim.

---

## License

See [LICENSE](LICENSE) for details.
