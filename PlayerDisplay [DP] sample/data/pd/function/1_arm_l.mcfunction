execute at @s run tp @s ~-0.25 ~1.4 ~
$data merge entity @s {Tags:["pd","pd_$(id)","pd_arm_l"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-2048.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}

execute if data storage pd: _{slim:true} run item replace entity @s hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/slim/left_arm"]

execute if data storage pd: _{slim:false} run item replace entity @s hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/left_arm"]

data modify entity @s item.components.minecraft:profile.name set from storage pd: _.name
