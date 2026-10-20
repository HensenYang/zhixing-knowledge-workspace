# 4090 离线复现路线与资源预算（Offline Runbook and Budget）

# 环境隔离（Environment Isolation）
你目前使用 Windows、RTX4090，先保持工作台 Python 环境独立。依据官方 Bash、FlashAttention 与数据依赖，建议模型实验采用 Linux／WSL2 独立环境；这是部署建议，不是本轮已完成安装。[NVIDIA WSL2 指南](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)
| 项目 | 当前官方依赖（Pinned Dependencies） |
|---|---|
| WMA | Python严格3.10.18，PyTorch2.3.1，Transformers4.40.1 |
| VLA | README建议Python3.10.18／CUDA12.4；依赖PyTorch2.5.1／Transformers4.52.3 |
| WLA | Python>=3.12,<3.14，PyTorch2.8.0，Transformers5.5.3，uv管理 |
出处：[WMA依赖](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/pyproject.toml)、[VLA依赖](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/pyproject.toml)、[WLA依赖](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/pyproject.toml)。不要把这三套依赖混装，也不要以最新版覆盖固定版本后称为原始复现。

## 执行次序（Execution Order）
1. 环境盘点：WSL版本、驱动、可用显存、磁盘；记录到实验配置。
2. ER-1：只取一张小图、短输出，检查模型与处理器兼容，然后测显存／延迟。
3. WMA Base：先基础视频脚本的一个提示，保留默认16帧与16步；Dual交互脚本默认50步且一轮有两次生成，不能拿两者总耗时直接比较。[基础脚本](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/scripts/run_base_model_inference.sh)、[交互脚本](https://github.com/unitreerobotics/unifolm-world-model-action/blob/3e198de68de55f93f24b3ad623dd499390aaee45/scripts/run_world_model_interaction.sh)
4. WLA Base：只取 Dex1 一项数据、一条轨迹，从官方离线评估入口比较预测和真实动作；确认54维掩码与统计量。[评估入口](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/examples/unifolm_wla/eval_files/unitree/eval_local_episode.py)
5. VLA LIBERO：先检查常量／权重兼容，再一次仿真试验；之后才扩大任务数和尝试微调。

## WLA 离线命令示意（Offline Command Example）
下面是后续 Linux 环境中的官方入口形式，需先完成权重／单任务数据下载、路径及数据配置；本轮尚未执行。
```bash
python -m examples.unifolm_wla.eval_files.unitree.eval_local_episode \
  --ckpt_path /path/UnifoLM-WLA-1.0-Base/checkpoints/model.safetensors \
  --data_config_path unifolm_wla/dataloader/multi_source_dataset/configs/unitree.yaml \
  --episode_idx 0 --save_dir results/episode_0
```
命令出处：[官方评估文档](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/docs/train_action_expert_en.md)。大数据集先按任务选择，再决定是否完整下载。

## 资源记录规则（Resource Accounting）
“权重文件体积”是磁盘下载量，既不等于GPU显存，也不包括激活、缓存、优化器和数据。另见自动生成的权重预算表；4090可行性目前是待实测。ER约4B、WLA约6B的BF16权重理论量级分别约8GB／12GB，只能作为初估；实际峰值显存必须记录。

## 实验最小记录（Minimum Experiment Record）
commit、权重revision、输入文件哈希、动作统计量、种子、精度、分辨率／词元数、动作块、采样步数、预热次数、重复次数、加载耗时、稳定推理耗时、峰值显存、输出路径、失败日志。加载、预热与稳定推理时间分开统计。

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
