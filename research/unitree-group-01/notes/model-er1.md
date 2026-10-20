# UnifoLM-ER-1

# 基座与能力（Backbone and Capabilities）
具身推理器（Embodied Reasoner, ER）建立于 Qwen3-VL-4B，官方称使用超过 500 万条空间／具身样本，并与通用图文数据共同训练（Co-training）。任务包含点预测、检测、多图推理、二维轨迹、三维检测与空间问答。[官方模型卡](https://huggingface.co/unitreerobotics/UnifoLM-ER-1/blob/dfb321b4317a011ce80622b9305b5dbb6513241b/README.md)
输出是语言与结构化表述，不能把 ER-1 本身等同于能直接控制 G1 的完整动作策略。架构配置声明 `Qwen3VLForConditionalGeneration`。[发布架构配置](https://huggingface.co/unitreerobotics/UnifoLM-ER-1/blob/dfb321b4317a011ce80622b9305b5dbb6513241b/config.json)

## 运行方式（Execution）
图像 + 提问 → 聊天模板（Chat Template）与视觉处理器 → 生成（Generate）→ 文本／点／框输出 → 检查格式与空间正确性。使用与仓库版本兼容的 Transformers 与 Qwen 处理器；具体输入方式参考官方 Qwen3-VL 示例。[上游推理示例](https://github.com/QwenLM/Qwen3-VL)
无机器人首个小实验：同一张桌面图，分别问“杯子在盘子的哪一侧？”、“拿取杯子会遇到什么遮挡？”，记录答案、失败例和显存。之后改变颜色／位置／措辞，检验定位与语言理解能否分开评估。

## 优势与优化假设（Strengths and Hypotheses）
4B 级别适合先探索具身空间推理。官方 16 项基准中七项开源领先是其测试汇总，不代表每个基准都领先；BLINK 列仅平均相对深度与空间关系两个子任务。[基准与脚注](https://huggingface.co/unitreerobotics/UnifoLM-ER-1/blob/dfb321b4317a011ce80622b9305b5dbb6513241b/README.md)
待测：短输出与图像词元预算对定位质量、延迟的影响；结构化格式验证与坐标校准；以后再测试量化（Quantization），先保留全精度基线，避免把数值变化与提示词变化混在一起。

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
