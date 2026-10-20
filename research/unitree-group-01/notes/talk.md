# 分享提纲与证据清单（Talk Outline and Evidence Checklist）

# 暂定分享结构（Provisional Talk Structure）
暂按算法同学20–30分钟组织，待你补充听众／时长后调整。
1. 问题（Problem）：机器人为什么需要理解、预测与动作三个层次？用五模型输入／输出表说明。
2. 两条路线（Two Routes）：WMA的视频预测和VLA的图文表征；明确相似目标不意味着同一基座。
3. 新路线（New Pipeline）：Qwen3-VL→ER-1→ER-Flow→MMDiT动作专家，解释光流、掩码词元、离散动作与连续动作的作用。
4. 代码落点（Code Anchors）：选一条WLA数据流讲54／60／120维、掩码、归一化和动作积分。
5. 实测（Measurements）：展示单图ER、视频WMA或单轨迹WLA的实际产物；未完成时明确标待验证。
6. 研究问题（Research Questions）：交互表征带来多少增益？少步采样如何影响动作？全身协议还缺哪些字段？

## 逐页证据检查（Slide-by-slide Evidence Check）
- 数字写“官方报告（Officially Reported）”或“本机实测（Locally Measured）”。
- 每张结构图注明简化图（Simplified Diagram），来源链接指向模型卡／代码，而非没有读过的二手文章。
- 基准可比性、开源时间和代码版本必须写清。
- 优化方向标研究假设（Research Hypothesis），避免承诺已验证提升。

通过条件：至少一个完整输入→模型→输出案例、五个模型的区分、三个带来源的关键论点、两个研究问题。幻灯片尚未制作。

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
