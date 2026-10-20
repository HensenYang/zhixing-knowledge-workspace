# 公开内容与复现缺口（Public Artifacts and Reproduction Gaps）

# 证据分层（Evidence Levels）
- 官方方法／结果（Official Claim）：官方主页、模型卡、README，能证明“官方这样报告”，不能代替独立实测。
- 代码证据（Code Evidence）：固定提交的类、配置与函数；可确认当前实现，不能单凭静态阅读保证安装成功。
- 本地实验（Local Measurement）：固定版本、输入和种子，保存日志和产物。本组当前还没有模型 GPU 实测。
- 研究假设（Research Hypothesis）：优化和融合建议，必须有对照实验。

## 已识别的缺口（Identified Gaps）
1. WMA：原始视频基座的唯一预训练权重来源和充分量化消融尚需进一步确认；代码继承 DynamiCrafter 不等于同名完整权重直接可替换。
2. VLA：官方脚本存在作者本机绝对路径；动作常量与发布 YAML 在维数／块长度上不一致；当前发布配置的 `QwenFM` 与框架注册名 `unifolm_vla` 也需要实际加载核验。它们是静态兼容性风险，本轮没有伪造运行报错。[发布配置](https://huggingface.co/unitreerobotics/UnifoLM-VLA-Libero/blob/f86b8c27ad4ad046f61de8e10d1388202735d719/config.yaml)；[注册与框架](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/src/unifolm_vla/model/framework/unifolm_vla.py)；[平台常量](https://github.com/unitreerobotics/unifolm-vla/blob/ff6c39aeb0454cfb95418c66aef40ca777f935c1/src/unifolm_vla/rlds_dataloader/constants.py)
3. ER-Flow：当前公开文件未找到完整独立 VQ-VAE／RVQ 解码器发布包，暂不能保证离散输出到物理动作的端到端复现。[权重文件树](https://huggingface.co/unitreerobotics/UnifoLM-ER-Flow/tree/f6dea62ca3fb42a633723b80d7f4b38b321f010e)
4. WLA：HF Base 模型卡几乎为空，应以固定版本 GitHub 技术文档、权重配置补齐；当前服务协议 Dex1 专用，并非全身手指／底盘通用。[Base 模型卡](https://huggingface.co/unitreerobotics/UnifoLM-WLA-1.0-Base/blob/dedc0612c4a921446db3a8cb0864bb7f7433329e/README.md)；[服务器适配器](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/model_server/unifolm_wla_action_adapter.py)
5. 微调数据混合：文档明确当前按样本数量采样，配置里的 `weight` 并未生效；不要将统计量“等任务合并”误当训练采样“等任务权重”。[训练数据说明](https://github.com/unitreerobotics/unifolm-wla/blob/0a1aa87be8f775c7883fcd27216e3666ac18a8c5/docs/train_action_expert_en.md)

## 性能比较边界（Performance Comparison Limits）
ER 的空间问答分数、VLA 的 LIBERO 成功率、WMA 的视频预测误差和 WLA 的离线动作误差测量不同能力，不应放在同一排行里。真机视频不能直接给出统计成功率。

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
