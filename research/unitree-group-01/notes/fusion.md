# 可验证的模型融合方向（Testable Model Integration）

# 已经实现的融合（Implemented Integration）
- WMA：图文条件 + 视频预测 + 动作扩散头。[配置](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/configs/inference/base_model_inference.yaml)
- VLA：空间增强 VLM 特征 + 状态 + 流匹配动作头。[框架](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/src/unifolm_vla/model/framework/unifolm_vla.py)
- ER-Flow：视觉、语言、未来动态区域与离散动作共同学习。[模型卡](https://huggingface.co/unitreerobotics/UnifoLM-ER-Flow/blob/f6dea62ca3fb42a633723b80d7f4b38b321f010e/README.md)
- WLA：ER-Flow 基座 + MMDiT 连续动作专家 + 统一动作／状态掩码。[框架](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/unifolm_wla/model/framework/VLM4A/QwenMMDiT.py)

## 第一组可做的研究假设（Research Hypotheses）
| 方向 | 如何组合（Integration） | 对照与测量（Control / Measurement） |
|---|---|---|
| 世界模型评价动作 | VLA 给候选动作，WMA 预测结果，用明确的目标距离或接触指标排序 | 同一任务比较原策略与重排序；先证明动作／坐标／图像协议一致。不能称为官方现成模块。 |
| 基座表征比较 | 在相同小数据上比较 ER-1 与 ER-Flow，动作专家结构相同 | 控制训练步数、数据、种子；对比动作误差与推理成本，检验交互预训练增益。 |
| 轻量动作适配 | 冻结主干，对动作头做 LoRA 与全量头微调对照 | 峰值显存、延迟、误差和失败类型；利用官方现有微调入口。 |

权重融合（Weight Merging）要求架构、参数形状与语义兼容，不能把 Qwen2.5-VL 与 Qwen3-VL 或视频 U-Net 直接相加。先做接口对齐或特征蒸馏（Feature Distillation），后者仍需实际训练验证。这些是本组提出的研究方向，不是宇树已经发布的性能结论。

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
