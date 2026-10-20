# 五模型对比与发布状态（Comparison and Release Status）

# 五模型对比（Model Comparison）
| 模型 | 主干／基座（Backbone） | 学习与输出（Learning and Output） | 首要用途（Primary Use） |
|---|---|---|---|
| UnifoLM-WMA-0 | 视频潜扩散结构（Video Latent Diffusion），继承 DynamiCrafter 代码 | 预测视频／状态；与扩散动作头联合做决策或仿真 | 观察未来交互，探索世界模型辅助动作 |
| UnifoLM-VLA-0 | Qwen2.5-VL-7B → UnifoLM-VLM-Base | 图文与状态条件 → DiT 流匹配连续动作块 | 指令驱动操作与 LIBERO 仿真 |
| UnifoLM-ER-1 | Qwen3-VL-4B | 图像和问题 → 语言、点／框等结构化理解 | 具身推理（Embodied Reasoning） |
| UnifoLM-ER-Flow | ER-1 的继续训练版本 | 动态区域掩码词元与离散动作词元 | 交互中心世界建模与表征对齐 |
| UnifoLM-WLA-1.0 | ER-Flow + MMDiT 动作专家，官方称约 6B | 多视角图像、语言与状态 → 连续动作块 | 跨末端执行器与全身操作 |

表格综合各模型笔记中的代码证据；查看模型卡片获得逐项引用。WMA 与 VLA 是同一家族的不同技术路线，当前公开资料不足以证明它们之间是逐个权重继承；ER-1 → ER-Flow → WLA 则有明确的官方方法说明。

## 发布时间线（Release Timeline）
- 2025-09-15：WMA 训练、推理、权重；2025-09-22：部署代码。[WMA 发布记录](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/README.md)
- 2026-01-29：VLA 训练、推理与权重。[VLA 发布记录](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/README.md)
- 2026-09-11：ER-1、ER-Flow 权重；09-20：WLA 结构和动作专家训练；09-28：WLA-1.0-Base、微调与当前已提供的 LoRA 入口。[WLA 英文发布记录](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/README.md)

## 研究边界（Evidence Boundaries）
开源权重不等于完整原始预训练配方公开，项目展示也不等于独立复现。当前检索到的五模型官方引用以项目／仓库的杂项引用（Miscellaneous Citation）为主；没有把上游论文误标为这些模型本身的学术论文。中文和英文文档存在更新差异，优先核对固定版本英文文档与实际文件。

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
