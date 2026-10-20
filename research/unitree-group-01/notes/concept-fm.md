# 流匹配（Flow Matching）

学习将噪声运送到数据的速度场。当前动作头的线性路径可写作 x_t=(1-t)ε+t·a，目标速度 a-ε；推理积分速度场。此处 t 是生成时间，不是机器人控制时间。

[定义／实现出处（Definition / Implementation）](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/src/unifolm_vla/model/modules/action_model/DiT_ActionHeader.py)

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
