# /data modify storage pd: _ set value {id:"a",name:"jeb_",slim:true,split:true}
execute if data storage pd: _{split:true} run return run function pd:0_split
execute summon item_display run function pd:1_head with storage pd: _
execute summon item_display run function pd:1_arm_r with storage pd: _
execute summon item_display run function pd:1_arm_l with storage pd: _
execute summon item_display run function pd:1_torso with storage pd: _
execute summon item_display run function pd:1_leg_r with storage pd: _
execute summon item_display run function pd:1_leg_l with storage pd: _
