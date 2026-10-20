# 向量量化与残差量化（VQ-VAE and RVQ）

VQ-VAE 将连续潜变量映射到码本索引；RVQ 分阶段量化残差。ER-Flow 用前者编码动态区域、后者编码三类动作。完整解码还需要对应码本与解码器。

[定义／实现出处（Definition / Implementation）](https://arxiv.org/abs/1711.00937)

核对日期（Verified on）：2026-10-01。官方结果与本地实测分开记录；阅读状态不代表你已掌握。
