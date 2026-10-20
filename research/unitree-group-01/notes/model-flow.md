# UnifoLM-ER-Flow

# 从 ER-1 到 ER-Flow（From ER-1 to ER-Flow）
官方将它描述为 ER-1 增加交互中心世界建模（Interaction-centric World Modeling）和离散动作学习（Discrete Action Learning）。模型卡显示为 4B 级别，架构仍属 Qwen3-VL。[模型卡](https://huggingface.co/unitreerobotics/UnifoLM-ER-Flow/blob/f6dea62ca3fb42a633723b80d7f4b38b321f010e/README.md)；[架构配置](https://huggingface.co/unitreerobotics/UnifoLM-ER-Flow/blob/f6dea62ca3fb42a633723b80d7f4b38b321f010e/config.json)

## 两条表征路径（Two Representation Paths）
1. 动态区域：用光流（Optical Flow）提取未来场景变化区域；向量量化变分自编码器（Vector-Quantized Variational Autoencoder, VQ-VAE）将其编码为定长离散掩码词元（Mask Tokens）；VLM 根据当前图像与任务／动作条件预测未来变化。
2. 动作：将动作分成末端位姿、末端关节、下肢关节，各自用残差向量量化（Residual Vector Quantization, RVQ）离散编码；词元按相同时间步对齐后共同学习。
这是对变化区域的预测，不等于 WMA 的完整 RGB 视频生成。ER-Flow 名称中的 Flow 不应与动作专家的流匹配（Flow Matching）混淆。[两条路径的官方说明](https://huggingface.co/unitreerobotics/UnifoLM-ER-Flow/blob/f6dea62ca3fb42a633723b80d7f4b38b321f010e/README.md)

## 如何运行与目前公开边界（Execution and Public Boundary）
可按 Qwen3-VL 类接口加载权重进行词元生成／表征使用；真正还原动态掩码或物理动作需要对应 VQ-VAE／RVQ 解码器、词表与统计量。当前核对的 HF 文件树与 WLA 代码树未找到完整独立 RVQ／动态区域解码器发布包，不能承诺下载 ER-Flow 权重即可跑通完整演示。先将其作为 WLA 的表征基座使用。[文件树](https://huggingface.co/unitreerobotics/UnifoLM-ER-Flow/tree/f6dea62ca3fb42a633723b80d7f4b38b321f010e)；[动作专家训练文档](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/docs/train_action_expert_en.md)

## 优势与待验证优化（Strengths and Testable Improvements）
紧凑变化表征可以把感知、交互预测与动作语义联系起来。研究假设：动态掩码的学习可能增强动作相关表征，但需同规模、同数据的消融（Ablation）验证，不能把 ER-Flow→WLA 的成功自动归因于光流。重点测码本重建误差（Codebook Reconstruction Error）、小物体接触遗漏、离散／连续动作对齐和跨本体迁移。

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
