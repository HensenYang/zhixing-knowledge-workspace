# UnifoLM-WLA-1.0

# 基座与规模（Backbone and Scale）
官方路线为 ER-Flow 多模态基座 + 多模态扩散 Transformer（Multimodal Diffusion Transformer, MMDiT）动作专家。公开介绍称约 6B 参数、约 2500 小时真机数据、64 项任务，包含桌面与全身操作、二指夹爪与五指手；这是官方体系的描述，不代表每条开源接口均已支持所有硬件。[官方项目方法](https://unigen-x.github.io/unifolm-wla.github.io/)
基座属于 Qwen3-VL 系列，不要因仓库致谢 Qwen-Image 就写成“整套模型以 Qwen-Image 为视觉语言基座”。致谢说明组件来源，权重配置和实际 VLM 加载器决定基座。[VLM 加载器](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/unifolm_wla/model/modules/vlm/QWen3.py)

## 实现拆解（Implementation Walkthrough）
多视角图像与语言 → Qwen3-VL 处理；60 维状态与60维掩码拼成120维，机器人状态投影器（Robot State Projector）映射进基座表征；特征与带噪动作送入双流联合注意力（Double-stream Joint Attention）的 MMDiT；流匹配预测速度，经积分生成动作块。[框架](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/unifolm_wla/model/framework/VLM4A/QwenMMDiT.py)；[MMDiT 结构](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/unifolm_wla/model/modules/action_model/DiT_modules/mmdit.py)
动作头的损失按有效自由度掩码计算，无效维度在训练与推理输入中置零；框架还屏蔽助理轮次词元，减少离散目标向连续动作头泄漏。[动作头与掩码](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/unifolm_wla/model/modules/action_model/MMDiT_ActionHeader.py)；[框架中的助理掩码](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/unifolm_wla/model/framework/VLM4A/QwenMMDiT.py)
发布 Base 配置为 54 维动作、30 个时间点、4 步采样；投影器输入120维不表示机器人有120个物理关节。[发布权重配置](https://huggingface.co/unitreerobotics/UnifoLM-WLA-1.0-Base/blob/dedc0612c4a921446db3a8cb0864bb7f7433329e/config.yaml)

## 运行与训练（Execution and Training）
无机器人首选本地轨迹评估（Local Episode Evaluation）：读数据集、权重配置与统计量，逐动作块预测，反归一化并还原相对位姿，然后对比预测和真实动作。它是离线误差评估，不是闭环成功率。[评估脚本](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/examples/unifolm_wla/eval_files/unitree/eval_local_episode.py)
随后可以冻结 VLM，仅微调动作专家与状态投影器；当前官方示例为单卡24GB、批量1、梯度累积8。LoRA 也有独立入口，不能保证任意数据、图像尺寸与环境都一定适配4090。[冻结配置](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/unifolm_wla/config/training/mmdit_finetune_frozen_vlm.yaml)；[LoRA 配置](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/unifolm_wla/config/training/mmdit_lora_frozen_vlm.yaml)
当前服务器适配器仅覆盖 Dex1 双指夹爪字段，缺少 WBT 手指与底盘字段；全身服务需要扩展协议，不能仅替换权重。[适配器](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/model_server/unifolm_wla_action_adapter.py)

## 优势与优化方向（Strengths and Optimization Directions）
统一动作空间与有效性掩码支持不同本体／末端数据共享；表征预训练与动作专家训练可分阶段进行。待验证：不同动作模态损失权重、码本先验对连续控制的价值、冻结／LoRA／全量微调对质量与成本的取舍、少步采样与动作时延鲁棒性、真实闭环中的分布偏移。当前训练框架返回动作损失，不可未经检查就宣称公开微调默认重跑了全部 ER 预训练任务。[实际训练输出](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/unifolm_wla/model/framework/VLM4A/QwenMMDiT.py)

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
