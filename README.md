English | [日本語](README_ja.md)

# (Stable) Player Display 26.3

This is a port of [bradleyq/stable_player_display](https://github.com/bradleyq/stable_player_display) to **Minecraft JE 26.3**, based on [erkko68's AJ-compatible fork 1.4.1](https://github.com/erkko68/stable_player_display).
It supports exports from Animated Java (AJ) 1.11.

# Verification Status

- Verified working in Minecraft JE 26.3 with the [sample datapack](sample_datapack), [resourcepack](resourcepack), and [resourcepack_split](resourcepack_split).
- AJ has been verified only with testing tools.

## Included Files

| Path | Description |
|---|---|
| `resourcepack/` | Resource pack (Standard model) |
| `resourcepack_split/` | Resource pack (Split model: includes elbows, waist, knees) |
| `animated-java-resources/aj-convert.py` | Conversion script for AJ exported datapacks |
| `animated-java-resources/player.ajblueprint` / `player_split.ajblueprint` | AJ blueprints (Preset export target set to 26.3) |
| `animated-java-resources/sample_datapack/` | Loot tables and functions for skin updating |
| `animated-java-resources/tests/` | Tests for `aj-convert.py` |
| `tools/` | Build scripts and shader tests used during porting |

## Limitations

- Exclusively for `item_display` entities.
- **Do not change** the bone's **`Rotation[1]` (Pitch)**.
- Models will break if placed **512m or more vertically** away from the player (horizontal distance is unlimited).
- If using `transformation.translation[1]` in animations, subtract the part's offset (if using AJ, `aj-convert.py` handles this automatically).
- Vanilla only; MOD environments are not supported.
- Incompatible with other packs that replace `core/entity.vsh` / `core/entity.fsh`.

## Resource Pack Installation

Enable **either** `resourcepack` or `resourcepack_split` as your resource pack (do not enable both).

## How to Use

### [Sample Datapack](sample_datapack)

#### Settings
```mcfunction
data modify storage pd: _ set value {id:"example",name:"Alex",slim:true,split:true}
```

#### Summon
```mcfunction
function #pd:
```

#### Remove
```mcfunction
function pd:remove {id:"example"}
```

#### Available parameters in `_`
- id
> The ID for the player display. (Required)
- name
> The MCID (skin) used for the player display. (Optional)
- slim
> Whether to use the slim model: True/False (Default: false)
- split
> Whether to use the split model: True/False (Default: false)

**For details, please check the [sample_datapack](sample_datapack).**

## Slim Checker 26.3

You can check whether a player's skin is slim using [Slim Checker](https://github.com/uma-channel/Slim-Checker-26.3).

## Animated Java: Datapack

Applies to **AJ 1.11 or later** (26.3 compatible version).

1. Open `animated-java-resources/player.ajblueprint` (or `player_split.ajblueprint` for split mode) in AJ and export it. Keep the Blueprint ID as `aj:player_display` (the tags and samples below assume this name).
   **"Use Storage for Animations" conversion is now supported** (was unsupported in 1.4.1).
2. Run the conversion script at the root of the exported datapack (next to the `data` folder).
   ```py
   python aj-convert.py aj:player_display -pn=jeb_
   python aj-convert.py aj:player_display -pn=jeb_ -split      # Split model
   python aj-convert.py aj:player_display --dry-run            # Preview without modifying files
   python aj-convert.py aj:player_display --force              # Force run even if converted (beware of double application)
   ```
   | Option | Description |
   |---|---|
   | `-pn=NAME` | Player name to borrow the skin from. If omitted, items default to `air` (configured later in-game). |
   | `-split` | Uses offset for the split model. |
   | `--dry-run` | Shows target count without modifying any files. |
   | `--force` | Executes even if already marked as converted (**Caution: Avoid double application**). |
   | `--tag-prefix P` | Directly specifies the tag prefix (Default replaces `:` and `/` in Blueprint ID with `.`). |
   | `--datapack DIR` | Datapack root path (Default is the current directory). |

   The script only requires **Python 3.8+** (no longer requires `nbtlib` as in older versions).
   If no conversion targets are found, it will stop with an error without overwriting anything. After conversion, `spd_aj_convert.json` is generated at the root to prevent re-execution on the same export.
3. Delete the resource pack exported alongside by AJ, as it is unnecessary (use the PD resource pack instead).

### Animated Java: Plugin Mode (Unsupported)

Like the original SPD, plugin mode script conversion is unsupported. On the side importing the blueprint, add the offsets listed in the table below to the bone's Y translation, set `item_display` to `thirdperson_righthand`, and set `item_model`.

## Part Offsets

| Part | Y Offset |
|---|---|
| head | 0 |
| right_arm | -1024 |
| left_arm | -2048 |
| torso | -3072 |
| right_leg | -4096 |
| left_leg | -5120 |
| right_forearm (Split) | -6144 |
| left_forearm (Split) | -7168 |
| waist (Split) | -8192 |
| lower_right_leg (Split) | -9216 |
| lower_left_leg (Split) | -10240 |

## Split Model

A model with added arm and leg joints and an independent waist. Use `resourcepack_split`, `player_split.ajblueprint`, and `aj-convert.py -split` **together as a set**.

## About AJ 1.11 Variants

The 1.4.1 README mentioned "switching models via Slim variants". In AJ 1.11 (for 1.21.4+), **the current texture of the texture slot is placed into `custom_model_data.strings`** of the bone item rather than the variant name. Therefore, switching variants does not change SPD's Slim selection. Please specify Slim via the loot tables mentioned above (setting `custom_model_data` directly) or via `item_model`.

## Troubleshooting

- **Model is invisible**: Skipping steps is the most common cause. Check resource pack activation, press F3+T, check `item_model` paths, `profile` (skin), `translation[1]` offsets, and ensure `item_display:"thirdperson_righthand"` is set.
- **Inverted up/down or front/back, or misplaced position**: Check the item's `transformation` definition (ensure `left_rotation` is set to `[1,0,0,0]`).
- **Body appears, but skin mapping is incorrect**: Vertex ordering of the head model in 26.3 might differ from older versions. Please submit a report with a screenshot reproducing the issue (we will fix `spd_apply()` based on the vertex order).
- **Outer layer disappears or flickers**: Related to Order-Independent Transparency (OIT) processing. Please submit a report.
- **`aj-convert.py` stops with an error**: Please read the error message carefully. "No conversion targets found" means the Blueprint ID, tag prefix (`--tag-prefix`), or export format differs from what was expected.
- **Reports "Already converted"**: This is a safety feature to prevent breaking the files by running it twice on the same export. Run the script on a freshly re-exported datapack.
- **Model distorts after editing pivots**: You must manually adjust the `translation` of each part in the resource pack.

## Submitting Reports

Please include your AJ version, commands/options used, full console log, and screenshots.

Please note that response or resolution is not guaranteed.

## Credits and Licenses

- **[bradleyq](https://github.com/bradleyq/stable_player_display)**: Original Author
- **[erkko68](https://github.com/erkko68/stable_player_display)**: AJ-compatible Fork Author
- **Resonance#3633**: Custom Models and Templates
- **[sireroo](https://github.com/sireroo)**: Inspiration

For further details, please refer to [LICENSE](LICENSE).
