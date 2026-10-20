# 权重下载预算（Weight Download Budget）

# 官方权重文件预算（Official Weight File Budget）

| 模型（Model） | 权重合计（GiB） | 类型（Format） | 固定版本（Revision） |
|---|---:|---|---|
| UnifoLM-ER-1 | 8.27 | .safetensors | [dfb321b4317a](https://huggingface.co/unitreerobotics/UnifoLM-ER-1/tree/dfb321b4317a011ce80622b9305b5dbb6513241b) |
| UnifoLM-ER-Flow | 9.01 | .safetensors | [f6dea62ca3fb](https://huggingface.co/unitreerobotics/UnifoLM-ER-Flow/tree/f6dea62ca3fb42a633723b80d7f4b38b321f010e) |
| UnifoLM-VLA-Base | 17.68 | .pt | [06fee5014922](https://huggingface.co/unitreerobotics/UnifoLM-VLA-Base/tree/06fee5014922ba6791cfe48d1e4aefac995dd8a2) |
| UnifoLM-VLA-Libero | 17.68 | .pt | [f86b8c27ad4a](https://huggingface.co/unitreerobotics/UnifoLM-VLA-Libero/tree/f86b8c27ad4ad046f61de8e10d1388202735d719) |
| UnifoLM-VLM-Base | 15.45 | .safetensors | [da121034eb56](https://huggingface.co/unitreerobotics/UnifoLM-VLM-Base/tree/da121034eb5681c085a17001853a0267632a796f) |
| UnifoLM-WLA-1.0-Base | 11.60 | .safetensors | [dedc0612c4a9](https://huggingface.co/unitreerobotics/UnifoLM-WLA-1.0-Base/tree/dedc0612c4a921446db3a8cb0864bb7f7433329e) |
| UnifoLM-WMA-0-Base | 9.72 | .ckpt | [b7bb75323e8c](https://huggingface.co/unitreerobotics/UnifoLM-WMA-0-Base/tree/b7bb75323e8c614fb9b0d25905d07a0fc11e1793) |
| UnifoLM-WMA-0-Dual | 15.57 | .ckpt | [88e73c19d72b](https://huggingface.co/unitreerobotics/UnifoLM-WMA-0-Dual/tree/88e73c19d72bead94da3d7fc2433ade6d468167c) |

这是模型仓库内权重文件的磁盘合计，不是运行显存，不能用它判断4090一定能运行。VLA官方推理还读取VLM目录，磁盘需同时考虑两个发布包；模型加载过程中可能额外占用CPU内存。数据、环境和下载缓存另计。
本轮仅下载约1MB级文本资料，没有下载上表权重。

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
