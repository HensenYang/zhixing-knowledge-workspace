# 动作与状态数据字典（Action and State Data Dictionary）

# 先分清数据空间（Separate Data Spaces）
WLA 的动作向量54维、状态向量60维；120维是状态和掩码拼接后的投影器输入。动作包括双臂末端相对位姿、手部及下身相关模块，缺失模块用掩码表示。默认目标采样率30Hz、动作块30点，约覆盖0到29/30秒。[官方数据处理规范](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/docs/robot_action_state_processing.md)

## 读一条轨迹的六个问题（Six Questions for an Episode）
1. 每张相机图像对应哪个角色，图像顺序是否与提示词中的角色一致？
2. 指令（Instruction）是一段轨迹共享，还是每个时间点不同？
3. 当前状态（Current State）和未来动作（Future Actions）如何对齐？
4. 哪些动作维度有效，位姿是绝对还是相对？
5. 使用哪个统计量文件，恢复物理单位后是否合理？
6. 预测误差统计是在相对表征还是物理位姿中计算？
多视角角色顺序、状态掩码拼接与动作掩码传递可以从框架逐字段跟踪。[批次到模型的适配代码](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/unifolm_wla/model/framework/VLM4A/QwenMMDiT.py)

## 记录模板（Recording Template）
| 字段（Field） | 形状（Shape） | 单位／坐标系（Units / Frame） | 来源文件（Source） | 检查结果（Check） |
|---|---|---|---|---|
| 图像（Images） | 待填 | 相机视角 | 待填 | 待填 |
| 状态（State） | 待填 | 待填 | 待填 | 待填 |
| 动作（Actions） | 待填 | 待填 | 待填 | 待填 |
| 有效性掩码（Validity Masks） | 待填 | 布尔 | 待填 | 待填 |

本表是学习作业模板，尚未冒充已读取真实数据的结果。

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
