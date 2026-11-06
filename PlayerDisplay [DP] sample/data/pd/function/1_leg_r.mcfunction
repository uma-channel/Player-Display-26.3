execute at @s run tp @s ~0.125 ~0.7 ~
$data merge entity @s {Tags:["pd","pd_$(id)","pd_leg_r"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-4096.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}

execute if data storage pd: {slim:true} run item replace entity @s hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/slim/right_leg"]

execute if data storage pd: {slim:false} run item replace entity @s hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/right_leg"]

data modify entity @s item.components.minecraft:profile.name set from storage pd: _.name
