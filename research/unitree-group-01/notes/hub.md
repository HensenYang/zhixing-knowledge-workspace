# 第一组研究：宇树开源模型（Unitree Open Models）

# 学习目标（Learning Objectives）
你已有 PyTorch 训练经验，本组从模型输入、输出与训练目标切入，数学和机器人基础按需要补齐。目标是能讲清五个模型、追踪一条推理路径，并用实际结果支撑分享。

## 执行顺序与完成条件（Sequence and Completion Gates）
1. **模型全景（Model Landscape）**：读“对比与发布状态”，画出 WMA 与 VLA 两条路线，再画 ER-1 → ER-Flow → WLA 的有出处演进关系。通过条件：用五句话分别描述五个模型的输入、输出与用途。
2. **数据与动作（Data and Actions）**：读动作空间与归一化笔记，解释 54 维动作、60 维状态、120 维投影器输入的区别。通过条件：能解释哪些维度无效、动作属于哪个坐标系。
3. **代码拆解（Code Walkthrough）**：按各模型笔记的入口、主干、头、后处理顺序读代码。通过条件：对每个模型完成一张张量流转表，而非只背结构名。
4. **离线复现（Offline Reproduction）**：先 ER-1 单图问答，再 WMA 单段视频；最后 WLA 一条本地轨迹。VLA 的 LIBERO 仿真作为第二条动作策略验证路径。通过条件：保存配置、版本、输出、峰值显存和耗时；失败也要记录。
5. **研究分享（Research Talk）**：制作讲解提纲，区分官方宣称、代码观察和自己的实验。通过条件：每个性能数字都能回到原始来源；至少讲清两项尚未解决的问题。

## 今天的第一项任务（First Task）
打开“任务 01”，先填五模型输入／输出表。暂不下载大权重，先完成源码阅读和环境盘点。

## 当前进度（Current Status）
已完成资料收集、文本源码核对与框架录入。模型 GPU 推理、训练和机器人实验均尚未执行；任务默认待学习，实验默认待运行。

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。


## 工作台阅读入口（Workspace Reading Links）

- [五模型对比与发布状态（Comparison and Release Status）](http://127.0.0.1:5174/knowledge/541b6304-a4fe-4968-a5c6-6733ad8f2705)
- [UnifoLM-WMA-0](http://127.0.0.1:5174/knowledge/92b040ee-fd9e-4907-bf61-b3ccd0432b5a)
- [UnifoLM-VLA-0](http://127.0.0.1:5174/knowledge/13df8d24-5e4d-497f-99bf-0f5fd4ac3d98)
- [UnifoLM-ER-1](http://127.0.0.1:5174/knowledge/86c34369-899c-42f3-902f-7d827df37c22)
- [UnifoLM-ER-Flow](http://127.0.0.1:5174/knowledge/440d6f02-3941-4690-abae-9d868a4af023)
- [UnifoLM-WLA-1.0](http://127.0.0.1:5174/knowledge/82ade9dc-62d9-4469-8db4-b257926d41e5)
- [动作与状态数据字典（Action and State Data Dictionary）](http://127.0.0.1:5174/knowledge/96f770db-5611-4ef0-8e9f-b6284e94f379)
- [4090 离线复现路线与资源预算（Offline Runbook and Budget）](http://127.0.0.1:5174/knowledge/fbc007ec-cd7b-4da6-a834-b8559bc99731)
- [公开内容与复现缺口（Public Artifacts and Reproduction Gaps）](http://127.0.0.1:5174/knowledge/ce27eef6-84e9-42b0-9e6a-0c0b22e76b67)
- [分享提纲与证据清单（Talk Outline and Evidence Checklist）](http://127.0.0.1:5174/knowledge/f33ef413-c514-47c2-8ef2-c287416a2a17)
- [任务01：五模型输入输出对照（Input / Output Comparison）](http://127.0.0.1:5174/knowledge/08ca08a3-2927-43fe-a60c-d8f4cc3489d8)
- [研究画布（Study Canvas）](http://127.0.0.1:5174/canvases/a47b61eb-1a85-4ba1-a263-172c8b7662bd)
