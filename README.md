# Player Display for 26.3

Display any player skin using only a resource pack and display entities on 26.3.

## Limitations

- Use only with `item_display` entities.
- **Do NOT modify the Rotation[1]** NBT (pitch) of any bone in the model.
- The model cannot be loaded from more than 512 meters **vertical distance** from the player (unlimited horizontal range).
- If using `transformation.translation[1]` for animations, subtract the required y-offset (if you are using AJ, the script handles this).
- Will only be updated for **Minecraft Vanilla**, if it breaks in a modded client, you are out of luck.

## Use Modes

### Raw Item Displays

If you want to manually summon item displays, use the following commands (it is recommended to use a function):

```
summon minecraft:item_display ~ ~1.4 ~ {Tags:["head"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,0.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
summon minecraft:item_display ~0.25 ~1.4 ~ {Tags:["arm_r"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-1024.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
summon minecraft:item_display ~-0.25 ~1.4 ~ {Tags:["arm_l"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-2048.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
summon minecraft:item_display ~ ~1.4 ~ {Tags:["torso"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-3072.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
summon minecraft:item_display ~0.125 ~0.7 ~ {Tags:["leg_r"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-4096.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
summon minecraft:item_display ~-0.125 ~0.7 ~ {Tags:["leg_l"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-5120.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}
```

Then populate the displays:

```
item replace entity @e[tag=head] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/head",minecraft:profile="jeb_"]
item replace entity @e[tag=arm_r] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/right_arm",minecraft:profile="jeb_"]
item replace entity @e[tag=arm_l] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/left_arm",minecraft:profile="jeb_"]
item replace entity @e[tag=torso] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/torso",minecraft:profile="jeb_"]
item replace entity @e[tag=leg_r] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/right_leg",minecraft:profile="jeb_"]
item replace entity @e[tag=leg_l] hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/left_leg",minecraft:profile="jeb_"]
```
> **_NOTE:_**  For split models, there are additional `right_forearm`, `left_forearm`, `lower_right_leg`, and `lower_left_leg` models.

