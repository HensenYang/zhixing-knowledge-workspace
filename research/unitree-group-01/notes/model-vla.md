# UnifoLM-VLA-0

# 基座与训练阶段（Backbone and Training Stages）
官方说明以 Qwen2.5-VL-7B 进行多任务继续预训练（Continued Pretraining），覆盖空间定位、任务分解、轨迹与动力学信息；约 340 小时清洗真机数据用于离散动作预训练，得到增强的视觉语言基座，再连接动作头。官方展示 12 类真机任务。[方法与官方评测](https://unigen-x.github.io/unifolm-vla.github.io/)
加载器实际使用 `Qwen2_5_VLForConditionalGeneration`；发布的 UnifoLM-VLM-Base 配置显示隐藏维数 3584，训练模板中的占位维数不能取代实际模型配置。[主干接口](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/src/unifolm_vla/model/modules/vlm/QWen2_5.py)；[发布基座配置](https://huggingface.co/unitreerobotics/UnifoLM-VLM-Base/blob/da121034eb5681c085a17001853a0267632a796f/config.json)

## 实现与张量路径（Implementation and Tensor Flow）
图像、指令 → 处理器（Processor）形成 `input_ids / pixel_values / image_grid_thw` → VLM 最后一层特征 `[B,L,H]` → 动作头，同时输入本体状态（Proprioceptive State）→ 归一化动作块 `[B,T,D]`。[框架的 forward / predict_action](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/src/unifolm_vla/model/framework/unifolm_vla.py)
动作头是扩散 Transformer（Diffusion Transformer, DiT）实现的流匹配（Flow Matching）。训练取高斯噪声与真实动作线性插值，回归速度 `action - noise`；推理从噪声迭代积分得到连续动作。不是把语言生成的自然语言指令直接交给电机。[动作头](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/src/unifolm_vla/model/modules/action_model/DiT_ActionHeader.py)
状态先归一化，输出根据所选 `unnorm_key` 和统计量反归一化；动作单位、夹爪语义与环境接口仍需对齐。[推理与后处理](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/experiments/LIBERO/unifolm_vla_inference.py)

## 本地运行路线（Local Execution Route）
首选无机器人路径：UnifoLM-VLM-Base + UnifoLM-VLA-Libero + LIBERO。修改脚本中的绝对路径、仿真任务组、统计量键、试验次数，再从一个任务的一次试验开始。[LIBERO 启动脚本](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/scripts/eval_scripts/run_eval_libero.sh)
必须检查平台常量：动作头实际引用 `ACTION_DIM / PROPRIO_DIM / NUM_ACTIONS_CHUNK`；当前 LIBERO 常量为 7／8／8，而发布 YAML 还写有 `action_horizon:16` 等字段。先严格验证权重形状与实际输出，不要按模板猜动作维数。[平台常量](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/src/unifolm_vla/rlds_dataloader/constants.py)；[发布配置](https://huggingface.co/unitreerobotics/UnifoLM-VLA-Libero/blob/f86b8c27ad4ad046f61de8e10d1388202735d719/config.yaml)

## 优势、证据限制与优化（Strengths, Limits and Optimization）
优势：通用图文与空间表征连接连续动作，适合指令条件多任务操作。官方 LIBERO 平均成绩为 98.7%，这是官方表格数值，未在本机复现；比较项并非本轮统一重跑，不能直接推出任何部署场景都同样领先。
待实验：冻结主干、少步动作采样、图像词元预算、动作块执行长度对延迟和成功率的影响。长动作块会减少调用频率，也可能降低纠错频率；不能只以吞吐量作为优化指标。

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
