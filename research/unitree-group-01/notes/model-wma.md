# UnifoLM-WMA-0

# 定位与基座（Role and Backbone）
世界模型—动作架构（World-Model–Action, WMA）以视频生成先验适配机器人交互。官方给出基础版（Base，Open-X 适配）和双模式版（Dual，下游五项宇树数据集适配）。[权重与训练阶段](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/README.md)

代码采用潜空间视频扩散（Latent Video Diffusion）：变分自编码器（AutoencoderKL）压缩图像；冻结的开放对比图文编码器（Frozen OpenCLIP）编码文本及图像；重采样器（Resampler）产生图像条件；带时序卷积与注意力的 WMAModel 去噪视频潜变量。动作路径使用条件一维 U-Net（Conditional 1D U-Net）。[结构配置](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/configs/inference/base_model_inference.yaml)
仓库致谢 DynamiCrafter、Diffusion Policy、ACT 和 HPT；这证明代码来源／方法关联，不能据此断言每个致谢项目都构成独立运行模块。[代码来源说明](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/README.md)

## 运行拆解（Execution Walkthrough）
1. 基础视频：`run_base_model_inference.sh` → `base_model_inference.py` → `LatentVisualDiffusion`。输入图像与指令，输出未来视频；脚本当前设置批量 1、320×512、16 帧、16 次 DDIM 采样。[基础入口](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/scripts/run_base_model_inference.sh)
2. 交互循环：`run_world_model_interaction.sh` → `world_model_interaction.py`。读取 CSV 指令、图像、HDF5 状态及统计量；归一化与统一维度后，决策模式先产生动作，仿真模式再以动作预测视频／状态，预测观测回填队列进入下一轮。[真实调用顺序](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/scripts/evaluation/world_model_interaction.py#L566-L647)
3. 真机链路是模型服务与机器人客户端；没有机器人时完成基础视频和模型内交互即可，不能将模型内生成结果当成真实物理环境反馈。[部署入口](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/scripts/run_real_eval_server.sh)

## 融合技术（Integrated Techniques）
视频扩散先验（Video Diffusion Prior）、图文条件（Image/Text Conditioning）、扩散动作策略（Diffusion Action Policy）、时序注意力（Temporal Attention）、状态／动作条件投影（State/Action Projection）。它属于学得的交互仿真器，不等价于 MuJoCo 的刚体动力学仿真。

## 优势与待验证优化（Strengths and Testable Improvements）
优势：未来视觉信息与动作生成可共享；可以直接观察模型对接触和物体变化的预测。研究假设：减少采样步数、混合精度、条件缓存可降低耗时，但必须同时测视觉质量与动作误差；长程生成要测漂移、物体恒常性和动作敏感性，不能只比较“视频更好看”。源码提供采样与双模式接口，不意味着具备已公开的树搜索／奖励规划器。[采样实现](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/src/unifolm_wma/models/samplers/ddim.py)

## 阅读问题（Reading Questions）
哪一次调用使用真实观测，哪一次使用预测观测？视频去噪次数与动作头更新次数是否相同？怎样验证“输入动作变了，预测结果也合理地变了”？

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
