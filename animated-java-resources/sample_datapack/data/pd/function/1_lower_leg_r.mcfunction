execute at @s run tp @s ~0.125 ~0.7 ~
$data merge entity @s {Tags:["pd","pd_$(id)","pd_lower_leg_r"],item_display:"thirdperson_righthand",view_range:0.6f,transformation:{translation:[0.0f,-4096.0f,0.0f],left_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f]}}

execute if data storage pd: _{slim:true} run item replace entity @s hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/slim/lower_right_leg"]

execute unless data storage pd: _{slim:true} run item replace entity @s hotbar.0 with minecraft:player_head[minecraft:item_model="animated_java:blueprint/player_display/lower_right_leg"]

# Set Slim Model from Custom Model Data
# execute if data storage pd: _{slim:true} run data modify entity @s item.components."minecraft:custom_model_data".strings set value ["slim"]

data modify entity @s item.components.minecraft:profile.name set from storage pd: _.name
