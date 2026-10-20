"""Build bilingual, source-linked research notes and a knowledge graph bundle."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATE='2026-10-01'
GROUP='unitree-group-01'
REPOS={'wma':'unifolm-world-model-action','vla':'unifolm-vla','wla':'unifolm-wla'}
SHAS={key:json.loads((ROOT/'sources'/repo/'commit.json').read_text())['sha'] for key,repo in REPOS.items()}
objects=[];relations=[]
def source(repo,path,anchor=''):
    return f'https://github.com/unitreerobotics/{REPOS[repo]}/blob/{SHAS[repo]}/{path}{anchor}'
def hf(name,path='README.md'):
    metadata=json.loads((ROOT/'sources'/'huggingface'/name/'metadata.json').read_text(encoding='utf-8'))
    return f'https://huggingface.co/unitreerobotics/{name}/blob/{metadata["sha"]}/{path}'
def cite(label,url): return f'[{label}]({url})'
def add(key,kind,title,summary,body,url='',**metadata):
    objects.append({'key':key,'kind':kind,'title':title,'summary':summary,'body_md':body.strip()+f'\n\n核对日期（Verified on）：{DATE}。官方结果与本地实测分开记录；阅读状态不代表你已掌握。\n','source_url':url,'reading_status':'unread','mastery_status':'unknown','tags':['宇树（Unitree）','第一组研究（Study Group 01）'], 'metadata':{'research_group':GROUP,'research_key':key,'verified_on':DATE,**metadata}})
def edge(a,b,typ,description,url='',locator=''):
    relations.append({'source_key':a,'target_key':b,'relation_type':typ,'description':description,'evidence':([{'source_url':url,'locator':locator,'explanation':description}] if url else [])})

wma_cfg=source('wma','configs/inference/base_model_inference.yaml')
wma_loop=source('wma','scripts/evaluation/world_model_interaction.py','#L566-L647')
vla_framework=source('vla','src/unifolm_vla/model/framework/unifolm_vla.py')
vla_head=source('vla','src/unifolm_vla/model/modules/action_model/DiT_ActionHeader.py')
wla_framework=source('wla','unifolm_wla/model/framework/VLM4A/QwenMMDiT.py')
wla_head=source('wla','unifolm_wla/model/modules/action_model/MMDiT_ActionHeader.py')
wla_doc=source('wla','docs/train_action_expert_en.md')
state_doc=source('wla','docs/robot_action_state_processing.md')

add('hub','task','第一组研究：宇树开源模型（Unitree Open Models）','先建立模型谱系与证据，再完成无机器人离线实验，最终形成可分享的技术讲解。',f'''
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
''', acceptance='完成五模型对比、数据管线说明、一项离线实测与有来源的分享提纲。',inputs='官方资料、固定版本源码、RTX4090',outputs='研究笔记、实验记录、分享提纲')

add('comparison','resource','五模型对比与发布状态（Comparison and Release Status）','区别视频世界模型、视觉语言动作策略、具身推理基座和全身动作专家。',f'''
# 五模型对比（Model Comparison）
| 模型 | 主干／基座（Backbone） | 学习与输出（Learning and Output） | 首要用途（Primary Use） |
|---|---|---|---|
| UnifoLM-WMA-0 | 视频潜扩散结构（Video Latent Diffusion），继承 DynamiCrafter 代码 | 预测视频／状态；与扩散动作头联合做决策或仿真 | 观察未来交互，探索世界模型辅助动作 |
| UnifoLM-VLA-0 | Qwen2.5-VL-7B → UnifoLM-VLM-Base | 图文与状态条件 → DiT 流匹配连续动作块 | 指令驱动操作与 LIBERO 仿真 |
| UnifoLM-ER-1 | Qwen3-VL-4B | 图像和问题 → 语言、点／框等结构化理解 | 具身推理（Embodied Reasoning） |
| UnifoLM-ER-Flow | ER-1 的继续训练版本 | 动态区域掩码词元与离散动作词元 | 交互中心世界建模与表征对齐 |
| UnifoLM-WLA-1.0 | ER-Flow + MMDiT 动作专家，官方称约 6B | 多视角图像、语言与状态 → 连续动作块 | 跨末端执行器与全身操作 |

表格综合各模型笔记中的代码证据；查看模型卡片获得逐项引用。WMA 与 VLA 是同一家族的不同技术路线，当前公开资料不足以证明它们之间是逐个权重继承；ER-1 → ER-Flow → WLA 则有明确的官方方法说明。

## 发布时间线（Release Timeline）
- 2025-09-15：WMA 训练、推理、权重；2025-09-22：部署代码。[WMA 发布记录]({source('wma','README.md')})
- 2026-01-29：VLA 训练、推理与权重。[VLA 发布记录]({source('vla','README.md')})
- 2026-09-11：ER-1、ER-Flow 权重；09-20：WLA 结构和动作专家训练；09-28：WLA-1.0-Base、微调与当前已提供的 LoRA 入口。[WLA 英文发布记录]({source('wla','README.md')})

## 研究边界（Evidence Boundaries）
开源权重不等于完整原始预训练配方公开，项目展示也不等于独立复现。当前检索到的五模型官方引用以项目／仓库的杂项引用（Miscellaneous Citation）为主；没有把上游论文误标为这些模型本身的学术论文。中文和英文文档存在更新差异，优先核对固定版本英文文档与实际文件。
''',source('wla','README.md'),subtype='documentation')

add('model:wma','model','UnifoLM-WMA-0','世界模型同时承担视频交互仿真与动作策略增强，两种模式必须分别理解。',f'''
# 定位与基座（Role and Backbone）
世界模型—动作架构（World-Model–Action, WMA）以视频生成先验适配机器人交互。官方给出基础版（Base，Open-X 适配）和双模式版（Dual，下游五项宇树数据集适配）。[权重与训练阶段]({source('wma','README.md')})

代码采用潜空间视频扩散（Latent Video Diffusion）：变分自编码器（AutoencoderKL）压缩图像；冻结的开放对比图文编码器（Frozen OpenCLIP）编码文本及图像；重采样器（Resampler）产生图像条件；带时序卷积与注意力的 WMAModel 去噪视频潜变量。动作路径使用条件一维 U-Net（Conditional 1D U-Net）。[结构配置]({wma_cfg})
仓库致谢 DynamiCrafter、Diffusion Policy、ACT 和 HPT；这证明代码来源／方法关联，不能据此断言每个致谢项目都构成独立运行模块。[代码来源说明]({source('wma','README.md')})

## 运行拆解（Execution Walkthrough）
1. 基础视频：`run_base_model_inference.sh` → `base_model_inference.py` → `LatentVisualDiffusion`。输入图像与指令，输出未来视频；脚本当前设置批量 1、320×512、16 帧、16 次 DDIM 采样。[基础入口]({source('wma','scripts/run_base_model_inference.sh')})
2. 交互循环：`run_world_model_interaction.sh` → `world_model_interaction.py`。读取 CSV 指令、图像、HDF5 状态及统计量；归一化与统一维度后，决策模式先产生动作，仿真模式再以动作预测视频／状态，预测观测回填队列进入下一轮。[真实调用顺序]({wma_loop})
3. 真机链路是模型服务与机器人客户端；没有机器人时完成基础视频和模型内交互即可，不能将模型内生成结果当成真实物理环境反馈。[部署入口]({source('wma','scripts/run_real_eval_server.sh')})

## 融合技术（Integrated Techniques）
视频扩散先验（Video Diffusion Prior）、图文条件（Image/Text Conditioning）、扩散动作策略（Diffusion Action Policy）、时序注意力（Temporal Attention）、状态／动作条件投影（State/Action Projection）。它属于学得的交互仿真器，不等价于 MuJoCo 的刚体动力学仿真。

## 优势与待验证优化（Strengths and Testable Improvements）
优势：未来视觉信息与动作生成可共享；可以直接观察模型对接触和物体变化的预测。研究假设：减少采样步数、混合精度、条件缓存可降低耗时，但必须同时测视觉质量与动作误差；长程生成要测漂移、物体恒常性和动作敏感性，不能只比较“视频更好看”。源码提供采样与双模式接口，不意味着具备已公开的树搜索／奖励规划器。[采样实现]({source('wma','src/unifolm_wma/models/samplers/ddim.py')})

## 阅读问题（Reading Questions）
哪一次调用使用真实观测，哪一次使用预测观测？视频去噪次数与动作头更新次数是否相同？怎样验证“输入动作变了，预测结果也合理地变了”？
''','https://github.com/unitreerobotics/unifolm-world-model-action',commit=SHAS['wma'],weight_version='Base/Dual',evidence_level='official+code')

add('model:vla','model','UnifoLM-VLA-0','Qwen2.5-VL 空间与动力学预训练表征，接 DiT 流匹配动作头。',f'''
# 基座与训练阶段（Backbone and Training Stages）
官方说明以 Qwen2.5-VL-7B 进行多任务继续预训练（Continued Pretraining），覆盖空间定位、任务分解、轨迹与动力学信息；约 340 小时清洗真机数据用于离散动作预训练，得到增强的视觉语言基座，再连接动作头。官方展示 12 类真机任务。[方法与官方评测]({ 'https://unigen-x.github.io/unifolm-vla.github.io/' })
加载器实际使用 `Qwen2_5_VLForConditionalGeneration`；发布的 UnifoLM-VLM-Base 配置显示隐藏维数 3584，训练模板中的占位维数不能取代实际模型配置。[主干接口]({source('vla','src/unifolm_vla/model/modules/vlm/QWen2_5.py')})；[发布基座配置]({hf('UnifoLM-VLM-Base','config.json')})

## 实现与张量路径（Implementation and Tensor Flow）
图像、指令 → 处理器（Processor）形成 `input_ids / pixel_values / image_grid_thw` → VLM 最后一层特征 `[B,L,H]` → 动作头，同时输入本体状态（Proprioceptive State）→ 归一化动作块 `[B,T,D]`。[框架的 forward / predict_action]({vla_framework})
动作头是扩散 Transformer（Diffusion Transformer, DiT）实现的流匹配（Flow Matching）。训练取高斯噪声与真实动作线性插值，回归速度 `action - noise`；推理从噪声迭代积分得到连续动作。不是把语言生成的自然语言指令直接交给电机。[动作头]({vla_head})
状态先归一化，输出根据所选 `unnorm_key` 和统计量反归一化；动作单位、夹爪语义与环境接口仍需对齐。[推理与后处理]({source('vla','experiments/LIBERO/unifolm_vla_inference.py')})

## 本地运行路线（Local Execution Route）
首选无机器人路径：UnifoLM-VLM-Base + UnifoLM-VLA-Libero + LIBERO。修改脚本中的绝对路径、仿真任务组、统计量键、试验次数，再从一个任务的一次试验开始。[LIBERO 启动脚本]({source('vla','scripts/eval_scripts/run_eval_libero.sh')})
必须检查平台常量：动作头实际引用 `ACTION_DIM / PROPRIO_DIM / NUM_ACTIONS_CHUNK`；当前 LIBERO 常量为 7／8／8，而发布 YAML 还写有 `action_horizon:16` 等字段。先严格验证权重形状与实际输出，不要按模板猜动作维数。[平台常量]({source('vla','src/unifolm_vla/rlds_dataloader/constants.py')})；[发布配置]({hf('UnifoLM-VLA-Libero','config.yaml')})

## 优势、证据限制与优化（Strengths, Limits and Optimization）
优势：通用图文与空间表征连接连续动作，适合指令条件多任务操作。官方 LIBERO 平均成绩为 98.7%，这是官方表格数值，未在本机复现；比较项并非本轮统一重跑，不能直接推出任何部署场景都同样领先。
待实验：冻结主干、少步动作采样、图像词元预算、动作块执行长度对延迟和成功率的影响。长动作块会减少调用频率，也可能降低纠错频率；不能只以吞吐量作为优化指标。
''','https://github.com/unitreerobotics/unifolm-vla',commit=SHAS['vla'],evidence_level='official+code')

add('model:er1','model','UnifoLM-ER-1','基于 Qwen3-VL-4B 的具身感知与推理基座，先做单图空间问答。',f'''
# 基座与能力（Backbone and Capabilities）
具身推理器（Embodied Reasoner, ER）建立于 Qwen3-VL-4B，官方称使用超过 500 万条空间／具身样本，并与通用图文数据共同训练（Co-training）。任务包含点预测、检测、多图推理、二维轨迹、三维检测与空间问答。[官方模型卡]({hf('UnifoLM-ER-1')})
输出是语言与结构化表述，不能把 ER-1 本身等同于能直接控制 G1 的完整动作策略。架构配置声明 `Qwen3VLForConditionalGeneration`。[发布架构配置]({hf('UnifoLM-ER-1','config.json')})

## 运行方式（Execution）
图像 + 提问 → 聊天模板（Chat Template）与视觉处理器 → 生成（Generate）→ 文本／点／框输出 → 检查格式与空间正确性。使用与仓库版本兼容的 Transformers 与 Qwen 处理器；具体输入方式参考官方 Qwen3-VL 示例。[上游推理示例]({'https://github.com/QwenLM/Qwen3-VL'})
无机器人首个小实验：同一张桌面图，分别问“杯子在盘子的哪一侧？”、“拿取杯子会遇到什么遮挡？”，记录答案、失败例和显存。之后改变颜色／位置／措辞，检验定位与语言理解能否分开评估。

## 优势与优化假设（Strengths and Hypotheses）
4B 级别适合先探索具身空间推理。官方 16 项基准中七项开源领先是其测试汇总，不代表每个基准都领先；BLINK 列仅平均相对深度与空间关系两个子任务。[基准与脚注]({hf('UnifoLM-ER-1')})
待测：短输出与图像词元预算对定位质量、延迟的影响；结构化格式验证与坐标校准；以后再测试量化（Quantization），先保留全精度基线，避免把数值变化与提示词变化混在一起。
''','https://huggingface.co/unitreerobotics/UnifoLM-ER-1',weight_version='dfb321b4317a011ce80622b9305b5dbb6513241b',evidence_level='official+config')

add('model:flow','model','UnifoLM-ER-Flow','ER-1 上融合动态区域掩码词元与离散动作词元的继续训练版本。',f'''
# 从 ER-1 到 ER-Flow（From ER-1 to ER-Flow）
官方将它描述为 ER-1 增加交互中心世界建模（Interaction-centric World Modeling）和离散动作学习（Discrete Action Learning）。模型卡显示为 4B 级别，架构仍属 Qwen3-VL。[模型卡]({hf('UnifoLM-ER-Flow')})；[架构配置]({hf('UnifoLM-ER-Flow','config.json')})

## 两条表征路径（Two Representation Paths）
1. 动态区域：用光流（Optical Flow）提取未来场景变化区域；向量量化变分自编码器（Vector-Quantized Variational Autoencoder, VQ-VAE）将其编码为定长离散掩码词元（Mask Tokens）；VLM 根据当前图像与任务／动作条件预测未来变化。
2. 动作：将动作分成末端位姿、末端关节、下肢关节，各自用残差向量量化（Residual Vector Quantization, RVQ）离散编码；词元按相同时间步对齐后共同学习。
这是对变化区域的预测，不等于 WMA 的完整 RGB 视频生成。ER-Flow 名称中的 Flow 不应与动作专家的流匹配（Flow Matching）混淆。[两条路径的官方说明]({hf('UnifoLM-ER-Flow')})

## 如何运行与目前公开边界（Execution and Public Boundary）
可按 Qwen3-VL 类接口加载权重进行词元生成／表征使用；真正还原动态掩码或物理动作需要对应 VQ-VAE／RVQ 解码器、词表与统计量。当前核对的 HF 文件树与 WLA 代码树未找到完整独立 RVQ／动态区域解码器发布包，不能承诺下载 ER-Flow 权重即可跑通完整演示。先将其作为 WLA 的表征基座使用。[文件树]({'https://huggingface.co/unitreerobotics/UnifoLM-ER-Flow/tree/f6dea62ca3fb42a633723b80d7f4b38b321f010e'})；[动作专家训练文档]({wla_doc})

## 优势与待验证优化（Strengths and Testable Improvements）
紧凑变化表征可以把感知、交互预测与动作语义联系起来。研究假设：动态掩码的学习可能增强动作相关表征，但需同规模、同数据的消融（Ablation）验证，不能把 ER-Flow→WLA 的成功自动归因于光流。重点测码本重建误差（Codebook Reconstruction Error）、小物体接触遗漏、离散／连续动作对齐和跨本体迁移。
''','https://huggingface.co/unitreerobotics/UnifoLM-ER-Flow',weight_version='f6dea62ca3fb42a633723b80d7f4b38b321f010e',evidence_level='official+file-audit')

add('model:wla','model','UnifoLM-WLA-1.0','ER-Flow 表征基座与 MMDiT 连续动作专家，重点读统一空间和本地轨迹评估。',f'''
# 基座与规模（Backbone and Scale）
官方路线为 ER-Flow 多模态基座 + 多模态扩散 Transformer（Multimodal Diffusion Transformer, MMDiT）动作专家。公开介绍称约 6B 参数、约 2500 小时真机数据、64 项任务，包含桌面与全身操作、二指夹爪与五指手；这是官方体系的描述，不代表每条开源接口均已支持所有硬件。[官方项目方法]({'https://unigen-x.github.io/unifolm-wla.github.io/'})
基座属于 Qwen3-VL 系列，不要因仓库致谢 Qwen-Image 就写成“整套模型以 Qwen-Image 为视觉语言基座”。致谢说明组件来源，权重配置和实际 VLM 加载器决定基座。[VLM 加载器]({source('wla','unifolm_wla/model/modules/vlm/QWen3.py')})

## 实现拆解（Implementation Walkthrough）
多视角图像与语言 → Qwen3-VL 处理；60 维状态与60维掩码拼成120维，机器人状态投影器（Robot State Projector）映射进基座表征；特征与带噪动作送入双流联合注意力（Double-stream Joint Attention）的 MMDiT；流匹配预测速度，经积分生成动作块。[框架]({wla_framework})；[MMDiT 结构]({source('wla','unifolm_wla/model/modules/action_model/DiT_modules/mmdit.py')})
动作头的损失按有效自由度掩码计算，无效维度在训练与推理输入中置零；框架还屏蔽助理轮次词元，减少离散目标向连续动作头泄漏。[动作头与掩码]({wla_head})；[框架中的助理掩码]({wla_framework})
发布 Base 配置为 54 维动作、30 个时间点、4 步采样；投影器输入120维不表示机器人有120个物理关节。[发布权重配置]({hf('UnifoLM-WLA-1.0-Base','config.yaml')})

## 运行与训练（Execution and Training）
无机器人首选本地轨迹评估（Local Episode Evaluation）：读数据集、权重配置与统计量，逐动作块预测，反归一化并还原相对位姿，然后对比预测和真实动作。它是离线误差评估，不是闭环成功率。[评估脚本]({source('wla','examples/unifolm_wla/eval_files/unitree/eval_local_episode.py')})
随后可以冻结 VLM，仅微调动作专家与状态投影器；当前官方示例为单卡24GB、批量1、梯度累积8。LoRA 也有独立入口，不能保证任意数据、图像尺寸与环境都一定适配4090。[冻结配置]({source('wla','unifolm_wla/config/training/mmdit_finetune_frozen_vlm.yaml')})；[LoRA 配置]({source('wla','unifolm_wla/config/training/mmdit_lora_frozen_vlm.yaml')})
当前服务器适配器仅覆盖 Dex1 双指夹爪字段，缺少 WBT 手指与底盘字段；全身服务需要扩展协议，不能仅替换权重。[适配器]({source('wla','model_server/unifolm_wla_action_adapter.py')})

## 优势与优化方向（Strengths and Optimization Directions）
统一动作空间与有效性掩码支持不同本体／末端数据共享；表征预训练与动作专家训练可分阶段进行。待验证：不同动作模态损失权重、码本先验对连续控制的价值、冻结／LoRA／全量微调对质量与成本的取舍、少步采样与动作时延鲁棒性、真实闭环中的分布偏移。当前训练框架返回动作损失，不可未经检查就宣称公开微调默认重跑了全部 ER 预训练任务。[实际训练输出]({wla_framework})
''','https://github.com/unitreerobotics/unifolm-wla',commit=SHAS['wla'],weight_version='dedc0612c4a921446db3a8cb0864bb7f7433329e',evidence_level='official+code')

# Foundations and required concepts: short notes instead of a generic curriculum.
foundations=[
('base:dynamic','DynamiCrafter（视频扩散先验 / Video Diffusion Prior）','https://arxiv.org/abs/2310.12190','图像条件与视频生成先验帮助理解 WMA 的图像编码、潜变量与时序生成。WMA 明确致谢其代码，但当前资料未明确标出唯一原始预训练 checkpoint；保留这个未知项。'),
('base:qwen25','Qwen2.5-VL-7B（视觉语言基座 / VLM Backbone）','https://arxiv.org/abs/2502.13923','VLA 的官方基座。重点读视觉编码、动态分辨率与多模态位置编码，不需要先学习所有 Qwen 训练细节。'),
('base:qwen3','Qwen3-VL-4B（视觉语言基座 / VLM Backbone）','https://arxiv.org/abs/2511.21631','ER-1 的官方基座。先理解图像词元、视觉语言特征、生成接口；Qwen 系列的所有能力不能自动视为宇树 checkpoint 已独立验证的能力。'),
('base:vlm','UnifoLM-VLM-Base（空间增强基座 / Spatially Enhanced Backbone）','https://huggingface.co/unitreerobotics/UnifoLM-VLM-Base','VLA 运行需要的空间增强视觉语言基座。项目称其对应继续预训练后的 UnifoLM-VLM-0；发布名使用 VLM-Base。它与 ER-1 使用不同代 Qwen 主干。')]
for key,title,url,body in foundations: add(key,'model',title,body,body+'\n\n'+cite('原始来源（Primary Source）',url),url)

concepts=[
('concept:latent','潜空间视频扩散（Latent Video Diffusion）','在图像压缩后的潜变量上迭代去噪，解码为视频；区分像素分辨率、潜变量分辨率和时间帧数。',wma_cfg),
('concept:policy','扩散动作策略（Diffusion Action Policy）','把动作序列看成条件生成问题，迭代去噪可表达多模态动作分布；WMA 的条件 U-Net 是实际动作路径之一。','https://arxiv.org/abs/2303.04137'),
('concept:fm','流匹配（Flow Matching）','学习将噪声运送到数据的速度场。当前动作头的线性路径可写作 x_t=(1-t)ε+t·a，目标速度 a-ε；推理积分速度场。此处 t 是生成时间，不是机器人控制时间。',vla_head),
('concept:dit','动作扩散 Transformer（Action DiT）','VLA 使用条件 Transformer 预测动作速度；WLA 改用 MMDiT 双流联合注意力。结构家族名不决定噪声目标，必须检查具体损失。',vla_head),
('concept:mmdit','多模态扩散 Transformer（MMDiT）','动作和条件分别处理，通过联合注意力交换信息。WLA 中实际用途是连续动作速度预测；与图像生成结构相关，但不是输出图像的动作专家。',source('wla','unifolm_wla/model/modules/action_model/DiT_modules/mmdit.py')),
('concept:flowmask','光流与动态区域预测（Optical Flow and Dynamic-region Prediction）','光流用于提取场景变化区域，预测其离散掩码表征；物体外观恒常性和接触微运动可能不被粗掩码充分表达，这是待验证局限。',hf('UnifoLM-ER-Flow')),
('concept:vq','向量量化与残差量化（VQ-VAE and RVQ）','VQ-VAE 将连续潜变量映射到码本索引；RVQ 分阶段量化残差。ER-Flow 用前者编码动态区域、后者编码三类动作。完整解码还需要对应码本与解码器。','https://arxiv.org/abs/1711.00937'),
('concept:chunk','动作分块与反馈（Action Chunking and Feedback）','一次预测一段未来动作，执行部分后重新观察。预测块长度、执行步数、控制频率是不同变量；长块可省计算但可能延迟纠错。',source('wma','scripts/run_world_model_interaction.sh')),
('concept:space','统一动作空间与掩码（Unified Action Space and Masks）','WLA 统一54维动作、60维状态，不存在的模块用有效性掩码标记；状态+状态掩码投影输入120维。禁止把未使用维度当实际关节。',state_doc),
('concept:se3','相对位姿与旋转表示（Relative Pose, SE(3), Rotation-6D）','末端与底盘动作以相对当前状态的刚体变换表示；必须分清参考坐标系、旋转组合次序、米／弧度与6维旋转编码。',state_doc),
('concept:norm','归一化与统计量（Normalization and Statistics）','WLA 相对位姿默认 Z-score，普通状态／动作默认1%/99%分位数归一化，跨任务统计需按规范合并。VLA 的 unnorm_key 必须匹配 checkpoint 与数据源。',state_doc),
('concept:lora','冻结主干与低秩适配（Frozen Backbone and LoRA）','冻结 VLM 减少训练开销；LoRA 训练低秩增量。当前 WLA 示例在动作头注入 LoRA，与“对所有 VLM 权重做 LoRA”不是同一设置。',source('wla','unifolm_wla/config/training/mmdit_lora_frozen_vlm.yaml'))]
for key,title,body,url in concepts: add(key,'concept',title,body,body+'\n\n'+cite('定义／实现出处（Definition / Implementation）',url),url)

add('actions','resource','动作与状态数据字典（Action and State Data Dictionary）','把54／60／120维、坐标系、掩码与统计量连接到实际模型输入。',f'''
# 先分清数据空间（Separate Data Spaces）
WLA 的动作向量54维、状态向量60维；120维是状态和掩码拼接后的投影器输入。动作包括双臂末端相对位姿、手部及下身相关模块，缺失模块用掩码表示。默认目标采样率30Hz、动作块30点，约覆盖0到29/30秒。[官方数据处理规范]({state_doc})

## 读一条轨迹的六个问题（Six Questions for an Episode）
1. 每张相机图像对应哪个角色，图像顺序是否与提示词中的角色一致？
2. 指令（Instruction）是一段轨迹共享，还是每个时间点不同？
3. 当前状态（Current State）和未来动作（Future Actions）如何对齐？
4. 哪些动作维度有效，位姿是绝对还是相对？
5. 使用哪个统计量文件，恢复物理单位后是否合理？
6. 预测误差统计是在相对表征还是物理位姿中计算？
多视角角色顺序、状态掩码拼接与动作掩码传递可以从框架逐字段跟踪。[批次到模型的适配代码]({wla_framework})

## 记录模板（Recording Template）
| 字段（Field） | 形状（Shape） | 单位／坐标系（Units / Frame） | 来源文件（Source） | 检查结果（Check） |
|---|---|---|---|---|
| 图像（Images） | 待填 | 相机视角 | 待填 | 待填 |
| 状态（State） | 待填 | 待填 | 待填 | 待填 |
| 动作（Actions） | 待填 | 待填 | 待填 | 待填 |
| 有效性掩码（Validity Masks） | 待填 | 布尔 | 待填 | 待填 |

本表是学习作业模板，尚未冒充已读取真实数据的结果。
''',state_doc,subtype='documentation')

add('gaps','question','公开内容与复现缺口（Public Artifacts and Reproduction Gaps）','分享时区分正式证据、静态代码观察、官方报告与待实测假设。',f'''
# 证据分层（Evidence Levels）
- 官方方法／结果（Official Claim）：官方主页、模型卡、README，能证明“官方这样报告”，不能代替独立实测。
- 代码证据（Code Evidence）：固定提交的类、配置与函数；可确认当前实现，不能单凭静态阅读保证安装成功。
- 本地实验（Local Measurement）：固定版本、输入和种子，保存日志和产物。本组当前还没有模型 GPU 实测。
- 研究假设（Research Hypothesis）：优化和融合建议，必须有对照实验。

## 已识别的缺口（Identified Gaps）
1. WMA：原始视频基座的唯一预训练权重来源和充分量化消融尚需进一步确认；代码继承 DynamiCrafter 不等于同名完整权重直接可替换。
2. VLA：官方脚本存在作者本机绝对路径；动作常量与发布 YAML 在维数／块长度上不一致；当前发布配置的 `QwenFM` 与框架注册名 `unifolm_vla` 也需要实际加载核验。它们是静态兼容性风险，本轮没有伪造运行报错。[发布配置]({hf('UnifoLM-VLA-Libero','config.yaml')})；[注册与框架]({vla_framework})；[平台常量]({source('vla','src/unifolm_vla/rlds_dataloader/constants.py')})
3. ER-Flow：当前公开文件未找到完整独立 VQ-VAE／RVQ 解码器发布包，暂不能保证离散输出到物理动作的端到端复现。[权重文件树]({'https://huggingface.co/unitreerobotics/UnifoLM-ER-Flow/tree/f6dea62ca3fb42a633723b80d7f4b38b321f010e'})
4. WLA：HF Base 模型卡几乎为空，应以固定版本 GitHub 技术文档、权重配置补齐；当前服务协议 Dex1 专用，并非全身手指／底盘通用。[Base 模型卡]({hf('UnifoLM-WLA-1.0-Base')})；[服务器适配器]({source('wla','model_server/unifolm_wla_action_adapter.py')})
5. 微调数据混合：文档明确当前按样本数量采样，配置里的 `weight` 并未生效；不要将统计量“等任务合并”误当训练采样“等任务权重”。[训练数据说明]({wla_doc})

## 性能比较边界（Performance Comparison Limits）
ER 的空间问答分数、VLA 的 LIBERO 成功率、WMA 的视频预测误差和 WLA 的离线动作误差测量不同能力，不应放在同一排行里。真机视频不能直接给出统计成功率。
''',source('wla','README.md'))

add('fusion','question','可验证的模型融合方向（Testable Model Integration）','区分已经融合的技术、系统组合和待研究的权重融合。',f'''
# 已经实现的融合（Implemented Integration）
- WMA：图文条件 + 视频预测 + 动作扩散头。[配置]({wma_cfg})
- VLA：空间增强 VLM 特征 + 状态 + 流匹配动作头。[框架]({vla_framework})
- ER-Flow：视觉、语言、未来动态区域与离散动作共同学习。[模型卡]({hf('UnifoLM-ER-Flow')})
- WLA：ER-Flow 基座 + MMDiT 连续动作专家 + 统一动作／状态掩码。[框架]({wla_framework})

## 第一组可做的研究假设（Research Hypotheses）
| 方向 | 如何组合（Integration） | 对照与测量（Control / Measurement） |
|---|---|---|
| 世界模型评价动作 | VLA 给候选动作，WMA 预测结果，用明确的目标距离或接触指标排序 | 同一任务比较原策略与重排序；先证明动作／坐标／图像协议一致。不能称为官方现成模块。 |
| 基座表征比较 | 在相同小数据上比较 ER-1 与 ER-Flow，动作专家结构相同 | 控制训练步数、数据、种子；对比动作误差与推理成本，检验交互预训练增益。 |
| 轻量动作适配 | 冻结主干，对动作头做 LoRA 与全量头微调对照 | 峰值显存、延迟、误差和失败类型；利用官方现有微调入口。 |

权重融合（Weight Merging）要求架构、参数形状与语义兼容，不能把 Qwen2.5-VL 与 Qwen3-VL 或视频 U-Net 直接相加。先做接口对齐或特征蒸馏（Feature Distillation），后者仍需实际训练验证。这些是本组提出的研究方向，不是宇树已经发布的性能结论。
''',wla_framework)

add('runbook','resource','4090 离线复现路线与资源预算（Offline Runbook and Budget）','先小型ER推理，再WMA视频，最后WLA本地轨迹；环境分别隔离。',f'''
# 环境隔离（Environment Isolation）
你目前使用 Windows、RTX4090，先保持工作台 Python 环境独立。依据官方 Bash、FlashAttention 与数据依赖，建议模型实验采用 Linux／WSL2 独立环境；这是部署建议，不是本轮已完成安装。[NVIDIA WSL2 指南]({'https://docs.nvidia.com/cuda/wsl-user-guide/index.html'})
| 项目 | 当前官方依赖（Pinned Dependencies） |
|---|---|
| WMA | Python严格3.10.18，PyTorch2.3.1，Transformers4.40.1 |
| VLA | README建议Python3.10.18／CUDA12.4；依赖PyTorch2.5.1／Transformers4.52.3 |
| WLA | Python>=3.12,<3.14，PyTorch2.8.0，Transformers5.5.3，uv管理 |
出处：[WMA依赖]({source('wma','pyproject.toml')})、[VLA依赖]({source('vla','pyproject.toml')})、[WLA依赖]({source('wla','pyproject.toml')})。不要把这三套依赖混装，也不要以最新版覆盖固定版本后称为原始复现。

## 执行次序（Execution Order）
1. 环境盘点：WSL版本、驱动、可用显存、磁盘；记录到实验配置。
2. ER-1：只取一张小图、短输出，检查模型与处理器兼容，然后测显存／延迟。
3. WMA Base：先基础视频脚本的一个提示，保留默认16帧与16步；Dual交互脚本默认50步且一轮有两次生成，不能拿两者总耗时直接比较。[基础脚本]({source('wma','scripts/run_base_model_inference.sh')})、[交互脚本]({source('wma','scripts/run_world_model_interaction.sh')})
4. WLA Base：只取 Dex1 一项数据、一条轨迹，从官方离线评估入口比较预测和真实动作；确认54维掩码与统计量。[评估入口]({source('wla','examples/unifolm_wla/eval_files/unitree/eval_local_episode.py')})
5. VLA LIBERO：先检查常量／权重兼容，再一次仿真试验；之后才扩大任务数和尝试微调。

## WLA 离线命令示意（Offline Command Example）
下面是后续 Linux 环境中的官方入口形式，需先完成权重／单任务数据下载、路径及数据配置；本轮尚未执行。
```bash
python -m examples.unifolm_wla.eval_files.unitree.eval_local_episode \\
  --ckpt_path /path/UnifoLM-WLA-1.0-Base/checkpoints/model.safetensors \\
  --data_config_path unifolm_wla/dataloader/multi_source_dataset/configs/unitree.yaml \\
  --episode_idx 0 --save_dir results/episode_0
```
命令出处：[官方评估文档]({wla_doc})。大数据集先按任务选择，再决定是否完整下载。

## 资源记录规则（Resource Accounting）
“权重文件体积”是磁盘下载量，既不等于GPU显存，也不包括激活、缓存、优化器和数据。另见自动生成的权重预算表；4090可行性目前是待实测。ER约4B、WLA约6B的BF16权重理论量级分别约8GB／12GB，只能作为初估；实际峰值显存必须记录。

## 实验最小记录（Minimum Experiment Record）
commit、权重revision、输入文件哈希、动作统计量、种子、精度、分辨率／词元数、动作块、采样步数、预热次数、重复次数、加载耗时、稳定推理耗时、峰值显存、输出路径、失败日志。加载、预热与稳定推理时间分开统计。
''',wla_doc,subtype='documentation')

add('talk','task','分享提纲与证据清单（Talk Outline and Evidence Checklist）','按照问题、结构、代码与实验讲解，不把官方宣传当成本机结果。',f'''
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
''',source('wla','README.md'),acceptance='形成有引用的讲解提纲，并包含一项真实离线结果或明确的未完成标记。')

papers=[
('paper:dynamic','论文：动态图像生成（DynamiCrafter）','https://arxiv.org/abs/2310.12190','2310.12190','读图像条件如何接入视频扩散；将其与WMA配置中的图像重采样器和视频潜变量对应。'),
('paper:dp','论文：扩散动作策略（Diffusion Policy）','https://arxiv.org/abs/2303.04137','2303.04137','读动作序列生成和滚动执行；理解生成动作块与执行前缀的区别。'),
('paper:fm','论文：生成模型的流匹配（Flow Matching for Generative Modeling）','https://arxiv.org/abs/2210.02747','2210.02747','先读概率路径和速度回归，不必首轮通读所有证明；对应动作头的线性插值。'),
('paper:vq','论文：离散表征学习（Neural Discrete Representation Learning）','https://arxiv.org/abs/1711.00937','1711.00937','先理解码本、最近邻量化与解码；这不是ER-Flow完整RVQ训练配方。'),
('paper:mmdit','论文：整流流Transformer（Scaling Rectified Flow Transformers）','https://arxiv.org/abs/2403.03206','2403.03206','作为MMDiT结构背景阅读；不要把其图像生成结果当成WLA机器人性能证据。'),
('paper:q25','论文：Qwen2.5-VL技术报告（Technical Report）','https://arxiv.org/abs/2502.13923','2502.13923','理解VLA的视觉语言主干，先读结构与动态分辨率部分。'),
('paper:q3','论文：Qwen3-VL技术报告（Technical Report）','https://arxiv.org/abs/2511.21631','2511.21631','理解ER系列的上游多模态主干；先读视觉语言对齐与多图处理。')]
for key,title,url,arxiv,body in papers: add(key,'resource',title,body,body+'\n\n'+cite('论文原文入口（Original Paper）',url)+'\n\n阅读状态：仅核对摘要与出处，尚未逐节精读；这是上游论文，不是宇树模型的独立论文。',url,subtype='paper',arxiv=arxiv)

for repo in ['wma','vla','wla']:
    url=f'https://github.com/unitreerobotics/{REPOS[repo]}'
    add('repo:'+repo,'repository',f'官方代码：{REPOS[repo]}（Official Repository）','固定提交用于结构与运行入口核对；目前只保存文本快照，没有安装模型环境。',f'代码提交（Commit）：`{SHAS[repo]}`。\n\n'+cite('固定版本README（Pinned README）',source(repo,'README.md'))+'\n\n本地文本快照位于 `research/unitree-group-01/sources/`；这些是研究资料，不是可执行的完整clone。',url,commit=SHAS[repo])

resources=[
('src:wma','资料：WMA官方项目页（Official Project Page）','https://unigen-x.github.io/unifolm-world-model-action.github.io/','用于确认两种模式与官方演示边界。','model:wma'),
('src:vla','资料：VLA官方项目页（Official Project Page）','https://unigen-x.github.io/unifolm-vla.github.io/','用于确认基座、预训练信号与官方LIBERO表；性能不是本机复现值。','model:vla'),
('src:wla','资料：WLA官方项目页（Official Project Page）','https://unigen-x.github.io/unifolm-wla.github.io/','用于确认ER-1、ER-Flow与WLA的阶段关系。','model:wla'),
('src:er1','模型卡：ER-1（Model Card）',hf('UnifoLM-ER-1'),'用于核对Qwen3-VL-4B、空间训练任务及基准脚注。','model:er1'),
('src:flow','模型卡：ER-Flow（Model Card）',hf('UnifoLM-ER-Flow'),'用于核对动态区域VQ-VAE与三类RVQ动作编码。','model:flow'),
('src:action','文档：统一动作状态处理（Action / State Specification）',state_doc,'逐项查坐标系、掩码、相对位姿和归一化。','model:wla'),
('src:train','文档：动作专家训练与评估（Action Expert Guide）',wla_doc,'用于离线评估、冻结主干微调、LoRA及服务接口。','model:wla'),
('src:budget','文档：CUDA与WSL2（CUDA on WSL2）','https://docs.nvidia.com/cuda/wsl-user-guide/index.html','用于后续Windows主机GPU实验环境选择；本轮没有安装WSL。','runbook')]
for key,title,url,body,target in resources:
    add(key,'resource',title,body,body+'\n\n'+cite('原始来源（Primary Source）',url),url,subtype='documentation')
    edge(key,target,'supports','这份官方资料支持对应模型或运行路线的说明。',url)

add('benchmark:libero','benchmark','LIBERO（终身机器人学习基准 / Lifelong Robot Learning Benchmark）','VLA无机器人闭环仿真入口；单轨迹离线误差不能代替闭环成功率。','先用一个任务一次试验验证输入、动作和环境接口，再扩大多任务评估。记录任务组、试验数和重置／动作语义。\n\n'+cite('官方LIBERO仓库','https://github.com/Lifelong-Robot-Learning/LIBERO'),'https://github.com/Lifelong-Robot-Learning/LIBERO')
add('data:oxe','dataset','Open-X Embodiment（跨本体数据 / Cross-embodiment Data）','WMA基础模型适配的官方数据来源。','不同本体具有不同传感器、动作和状态语义；不要认为能拼接数组就能联合训练。\n\n'+cite('Open-X官方仓库','https://github.com/google-deepmind/open_x_embodiment'),'https://github.com/google-deepmind/open_x_embodiment')
add('data:dex1','dataset','宇树Dex1数据（Unitree Dex1 Dataset）','WLA初始离线评估优先选择一项双指夹爪任务。','先核对单任务的目录、相机角色和统计量；本轮仅登记官方数据来源，没有下载数据集。\n\n'+cite('官方数据合集','https://huggingface.co/collections/unitreerobotics/unifolm-g1-dex1-dataset'),'https://huggingface.co/collections/unitreerobotics/unifolm-g1-dex1-dataset')
add('data:wbt','dataset','宇树全身遥操作数据（Whole-body Teleoperation, WBT）','包含全身／手部相关字段，需要完整协议与有效性掩码。','与Dex1的动作模块不同，后续先做数据字段比较，再考虑全身服务。\n\n'+cite('官方WBT数据合集','https://huggingface.co/collections/unitreerobotics/unifolm-wbt-dataset'),'https://huggingface.co/collections/unitreerobotics/unifolm-wbt-dataset')

tasks=[
('task:01','任务01：五模型输入输出对照（Input / Output Comparison）','不运行GPU，先填五行表。','分别写当前观测、指令、状态、未来动作／视频／词元；说明ER-1为什么不是完整控制策略；每行至少一项官方出处。','comparison','每个模型一行输入输出表，能用自己的话说明五种用途。'),
('task:02','任务02：数据与维度走查（Data / Dimension Walkthrough）','解释54、60、120维与相对位姿。','选WLA数据规范，填写数据字典；随后核对VLA常量与配置差异，列出需要运行验证的项。','actions','完成字段形状、单位、参考坐标系、掩码和统计量表。'),
('task:03','任务03：WMA双模式走查（Dual-mode Walkthrough）','追踪一次决策→仿真→预测观测回填。','对比基础视频入口和交互入口；标明真实观测与预测观测边界，以及每轮生成次数。','model:wma','能画出双模式循环，并注明每次调用的输入与输出。'),
('task:04','任务04：VLA与WLA动作头（Action-head Comparison）','找到噪声、插值、速度目标、采样积分。','分别读取两个动作头与框架，解释DiT／MMDiT、状态注入与掩码；填写最小公式。','concept:fm','两张调用图、一条训练损失解释与两项结构差异。'),
('task:05','任务05：4090最小离线实验（Minimal Offline Experiments）','先单图ER，再单视频WMA，再单轨迹WLA。','按运行路线依次执行，记录版本、配置、显存、耗时和失败；通过前一项完成条件后推进下一项，不设固定周时间。','runbook','至少一项真实产物和完整实验记录，未完成项保持待运行。'),
('task:06','任务06：完成有证据的分享（Evidence-backed Talk）','将架构、代码观察和实测结果组织成讲解。','使用分享提纲，逐页检查来源、结果类型、开源日期与待验证问题。','talk','逐页来源清单、明确的实验状态与两项研究问题。')]
for key,title,summary,body,target,acceptance in tasks:
    add(key,'task',title,summary,body+'\n\n完成条件（Completion Gate）：'+acceptance,acceptance=acceptance)
    edge(key,target,'uses','任务使用这份笔记或概念完成学习。')
    edge('hub',key,'related_to','第一组研究按完成条件推进的子任务。')
for first,second in zip(tasks,tasks[1:]): edge(second[0],first[0],'depends_on','建议先通过前一任务的完成条件，再推进此任务。')

for key,title,model,hypothesis in [
 ('exp:er','实验：ER-1单图空间问答（Single-image Spatial QA）','model:er1','固定图像与模型，比较位置／遮挡问法，并记录显存与延迟。'),
 ('exp:wma','实验：WMA单段视频与动作敏感性（Video / Action Sensitivity）','model:wma','固定提示与种子，先获得基础视频，再检查输入动作变化是否改变合理的交互预测。'),
 ('exp:wla','实验：WLA单轨迹动作评估（Local Episode Action Evaluation）','model:wla','按有效维度比较预测与真实动作，分清离线误差和闭环成功率。')]:
    add(key,'experiment',title,hypothesis,'状态（Status）：待运行（Planned）。\n\n假设（Hypothesis）：'+hypothesis+'\n\n尚未下载权重、安装模型依赖或执行GPU推理；不要把资料核对填写为实验成功。',acceptance='保存输入、配置、版本、输出和资源测量。')
    edge(key,model,'evaluates','后续离线实验评估模型的一个可验证能力。')
    edge('task:05',key,'uses','最小实验按顺序开展。')

for key in ['comparison','actions','gaps','fusion','runbook','talk','model:wma','model:vla','model:er1','model:flow','model:wla']:
    edge('hub',key,'related_to','第一组研究的核心材料与模型。')
for model,repo in [('model:wma','wma'),('model:vla','vla'),('model:wla','wla')]:
    edge('repo:'+repo,model,'implements','官方代码库提供该模型的公开实现。',source(repo,'README.md'))
for a,b in [('model:wma','base:dynamic'),('model:vla','base:vlm'),('base:vlm','base:qwen25'),('model:er1','base:qwen3'),('model:flow','model:er1'),('model:wla','model:flow')]:
    evidence=hf('UnifoLM-ER-Flow') if a=='model:flow' else ('https://unigen-x.github.io/unifolm-wla.github.io/' if a=='model:wla' else ('https://unigen-x.github.io/unifolm-vla.github.io/' if a in ['model:vla','base:vlm'] else (hf('UnifoLM-ER-1') if a=='model:er1' else source('wma','README.md'))))
    edge(a,b,'depends_on','基座／表征／代码继承关系；WMA→DynamiCrafter仅代表公开代码与方法来源，原始checkpoint仍待确认。' if a=='model:wma' else '官方明确说明的基座或继续训练来源。',evidence)
model_concepts={
 'model:wma':['latent','policy','chunk'], 'model:vla':['fm','dit','chunk','norm'],
 'model:er1':[], 'model:flow':['flowmask','vq'], 'model:wla':['fm','mmdit','space','se3','norm','lora']}
for model,keys in model_concepts.items():
    for key in keys:
        item=next(o for o in objects if o['key']=='concept:'+key)
        edge(model,item['key'],'uses','该模型的公开实现／方法使用或支持此项技术；LoRA是公开微调选项。',item['source_url'])
for a,b in [('model:wma','model:vla'),('model:wma','model:wla'),('model:vla','model:wla'),('model:flow','model:wma')]:
    edge(a,b,'compares_with','研究比较：输入输出、世界建模目标与动作路径不同，不表示权重可直接融合。')
for a,b in [('paper:dynamic','base:dynamic'),('paper:dp','concept:policy'),('paper:fm','concept:fm'),('paper:vq','concept:vq'),('paper:mmdit','concept:mmdit'),('paper:q25','base:qwen25'),('paper:q3','base:qwen3')]:
    item=next(o for o in objects if o['key']==a);edge(a,b,'supports','上游原始论文提供概念或结构背景；不代替宇树模型性能证据。',item['source_url'])
for model,data in [('model:wma','data:oxe'),('model:vla','benchmark:libero'),('model:wla','data:dex1'),('model:wla','data:wbt')]: edge(model,data,'uses','官方数据／评估路径关联。',source('wma' if model=='model:wma' else ('vla' if model=='model:vla' else 'wla'),'README.md'))
for model in ['model:wma','model:vla','model:flow','model:wla']: edge('gaps',model,'questions','需要补齐公开材料或进行实际运行验证。')
for model in ['model:wma','model:vla','model:flow','model:wla']: edge('fusion',model,'related_to','组合或表征对照的研究假设，尚未实测。')

# Budget is derived from primary model-file metadata, not GPU claims.
budget=['# 官方权重文件预算（Official Weight File Budget）','', '| 模型（Model） | 权重合计（GiB） | 类型（Format） | 固定版本（Revision） |','|---|---:|---|---|']
for folder in sorted((ROOT/'sources'/'huggingface').iterdir()):
    metadata=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
    files=[item for item in metadata['siblings'] if item['rfilename'].endswith(('.safetensors','.ckpt','.bin','.pt'))]
    size=sum(item.get('size',0) for item in files)
    budget.append(f'| {folder.name} | {size/1024**3:.2f} | '+', '.join(sorted({Path(item['rfilename']).suffix for item in files}))+f' | [{metadata["sha"][:12]}](https://huggingface.co/unitreerobotics/{folder.name}/tree/{metadata["sha"]}) |')
budget+=['','这是模型仓库内权重文件的磁盘合计，不是运行显存，不能用它判断4090一定能运行。VLA官方推理还读取VLM目录，磁盘需同时考虑两个发布包；模型加载过程中可能额外占用CPU内存。数据、环境和下载缓存另计。','本轮仅下载约1MB级文本资料，没有下载上表权重。']
add('budget','resource','权重下载预算（Weight Download Budget）','官方权重磁盘体积与显存需求分开；避免一次下载全部模型。','\n'.join(budget),subtype='documentation')
edge('runbook','budget','uses','先核对磁盘预算再安排模型下载。')
edge('hub','budget','related_to','第一组实验资源预算。')

bundle={'group':GROUP,'verified_on':DATE,'commits':SHAS,'objects':objects,'relations':relations}
(ROOT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
notes=ROOT/'notes';notes.mkdir(exist_ok=True)
for obj in objects:
    (notes/(obj['key'].replace(':','-')+'.md')).write_text('# '+obj['title']+'\n\n'+obj['body_md'],encoding='utf-8')
(ROOT/'README.md').write_text('# 第一组：宇树开源模型研究（Unitree Open-model Study）\n\n核对日期：'+DATE+'。\n\n'+ '\n'.join(f'- [{o["title"]}](notes/{o["key"].replace(":","-")}.md)' for o in objects if o['key'] in ['hub','comparison','model:wma','model:vla','model:er1','model:flow','model:wla','actions','runbook','budget','gaps','fusion','talk'])+'\n\n来源快照位于sources，固定版本清单位于source-manifest.json。状态：完成资料核对与学习框架准备，尚未执行模型GPU实验。\n',encoding='utf-8')
print(json.dumps({'objects':len(objects),'relations':len(relations),'notes':str(notes)},ensure_ascii=False))
