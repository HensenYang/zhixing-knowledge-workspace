# 冻结主干与低秩适配（Frozen Backbone and LoRA）

冻结 VLM 减少训练开销；LoRA 训练低秩增量。当前 WLA 示例在动作头注入 LoRA，与“对所有 VLM 权重做 LoRA”不是同一设置。

[定义／实现出处（Definition / Implementation）](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/unifolm_wla/config/training/mmdit_lora_frozen_vlm.yaml)

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
