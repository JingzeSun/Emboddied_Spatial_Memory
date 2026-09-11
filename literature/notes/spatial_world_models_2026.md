# 空间历史与动作条件世界模型：定向文献核查

核查日期：2026-09-11。范围是D-062的空间历史、机器人控制、视野外交互后果及动作选择。本文是文献证据与重合审查，不是模型复现、穷尽综述或新颖性保证。当前方法建议见[方法合同](../../docs/METHOD.md)，唯一执行顺序见[计划](../../docs/PLAN.md)。旧CTL文献笔记保留其历史用途。

核查范围按各行标注：多数工作阅读相关方法/实验段落及可找到的作者代码说明，部分仅核摘要或公开资产；没有下载模型、安装依赖或运行论文实验。“有代码”只表示公开入口可核验，不代表当前服务器能运行；未查到入口也不证明作者没有发布。

## 必须分开的输入条件

白话：这组区分防止把“给出未来答案后画出来”当成控制预测。输入可能是控制、计划机器人路径或真实未来状态，输出都可能叫视频，但难度和信息完全不同。例如给推杆速度后预测物块会不会受阻，需要预测实际执行；给完整物块位移后渲染只检查生成。它不是按论文标题中的action一词分类。

| 条件 | 含义与核查要求 |
|---|---|
| 机器人控制指令 | 输入速度、力或目标位姿；实际机器人运动及接触后物块运动尚未知。须登记控制器和力/速度限幅 |
| 机器人计划几何路径 | 根据关节配置/运动学得到将要经过的位置；若假定完全实现，不能顺带宣称预测了跟踪失败 |
| 物体真实未来变换 | 若已作为模型输入，则不再是未知交互后果预测；仅作为训练标签时另论 |
| 仿真真值状态 | 可以在离线监督/独立诊断端使用；主预测输入不得含私有几何、快照或未来真值 |

## 直接相关工作

| 工作与阅读版本 | 实际输入、监督及历史机制 | 评估与本项目边界 |
|---|---|---|
| [DINO-WM](https://arxiv.org/html/2411.04983v2)，ICML 2025，[正式记录](https://proceedings.mlr.press/v267/zhou25t.html) | 图像、本体状态和控制→未来视觉特征（DINO冻结）及本体表征；动作/本体编码可训练，按checkpoint配置核验；因果Transformer、视觉目标规划 | 已有动作条件latent预测与控制。加RGBD、长历史及物块真值状态头是任务适配，不是原设定复现 |
| [DreamerV3](https://www.nature.com/articles/s41586-025-08744-2)，Nature 2025；正式题名Mastering diverse control tasks through world models | 循环隐状态结合观测和动作；完整系统同时学习重建、奖励/继续状态及策略/价值 | 需检验普通循环记忆是否足够。抽取其RSSM并改为离线状态监督，不是完整Dreamer复现 |
| [Learning 3D Persistent Embodied World Models](https://proceedings.neurips.cc/paper_files/paper/2025/hash/970f59b22f4c72aec75174aae63c7459-Abstract-Conference.html)，NeurIPS 2025；本轮复核摘要，详细输入待进一步核验 | 将预测RGBD融合进持续三维地图，再用于生成条件 | 持续三维地图与未来生成的组合早有先例；本轮未据摘要认定其机器人接触控制条件 |
| [FloWM v2](https://arxiv.org/html/2601.01075v2)，2026-05-28；正式题名Flow Equivariant World Models: Structured Memory for Dynamic Environments | 部分图像与已知自运动→循环空间状态与未来图像；状态按自运动及速度通道推进 | 受控2D/3D动态、超训练时长预测、位置读出和简单规划。已覆盖结构记忆与视野外动态；不等同受有限力控制的推物接触。ICML 2026身份由[官方目录](https://icml.cc/Downloads/2026)对应Poster条目核验 |
| [PERSIST v2](https://arxiv.org/html/2603.03482v2)，2026-06-03 | 图像/相机初态及游戏按键鼠标→体素、相机及图像；训练用真值体素/相机，真值初始体素版本单列 | 展示倒退撞视野外树与不可见环境演化。持续3D＋视野外后果不是空白；游戏域和强3D监督须注明。ICML 2026身份由[官方目录](https://icml.cc/Downloads/2026)核验 |
| [Mem-World v2](https://arxiv.org/html/2606.18960v2)，2026-06-18，预印本 | 多视角/历史图像＋未来机器人动作块；带时间的表面元素索引历史，按未来腕相机位姿检索；视频监督 | 遮挡回放、策略评价和合成数据用途高度相关；初始化多视角较强。所读实验未见我们的严格成对历史/同控制碰撞归因，不能据此断言其失败 |
| [PointWorld v1](https://arxiv.org/html/2601.03782v1)，2026-01-07；CVF官方搜索条目已找到，页面直读受限，索引保守待核 | RGBD点云＋URDF/未来关节配置形成的机器人点流→场景点流；含跟踪监督，通常一张/少数当前图 | 实体交互和真实机器人规划直接相关；限制节明确把机器人路径当完全实现，不预测受力限导致的跟踪误差。缺持续历史接口不等于实验已证明记忆失败 |
| [MRO-GWM v1](https://arxiv.org/html/2606.01950v1)，2026-06-01，预印本 | 对象高斯、历史物体/末端位姿＋未来末端目标→未来物体位姿；目标送入控制器。实验提供真值对象分割与历史位姿 | 多物体交互及规划已有实例；未来物体位姿是标签，并非动作输入。强感知真值不能与本项目公开视觉输入混排 |
| [Ctrl-World v3](https://arxiv.org/html/2510.10125v3)，2026-03-01；ICLR官方搜索条目已找到，页面直读受限，索引保守待核 | 多相机及稀疏历史＋未来末端位姿→视频；关节速度策略需适配器/运动学转换 | 已有动作条件视频、策略排名和机器人收益；精细碰撞仍有局限，但论文局限不是我们协议中的可复现失败 |
| [PropNet v2](https://arxiv.org/html/1809.11169v2)，ICRA 2019，[正式记录](https://ieeexplore.ieee.org/document/8793509/) | 可见对象的位置/速度等结构状态与控制→潜空间动态；短历史与多步关系传播，重建/预测监督 | 部分可观测箱体推动和控制早有先例。不是原始RGB空间历史模型，但否定“图交互＋部分观测”本身新颖 |
| [Graph Network-based Simulators](https://proceedings.mlr.press/v119/sanchez-gonzalez20a.html)，ICML 2020 | 粒子状态图→学习消息传递→下一步物理状态 | 学习局部交互与长滚动已有成熟基础；它本身不解决从受限图像恢复未知场景状态 |

### 仓库与资源核验

下列大小/用时属于公开文件或作者所报条件，不是本机实测，也不能由checkpoint文件大小推出显存峰值。

| 工作 | 本轮核验的入口 | 对当前单卡的处置建议（planned） |
|---|---|---|
| DINO-WM | [官方仓库](https://github.com/gaoyuezhou/dino_wm)，train/plan及PointMaze、PushT、Wall权重/配置 | 优先一个原任务的官方权重重新评估；固定commit、checkpoint自带配置，不能拿仓库默认参数冒充论文参数 |
| FloWM | [官方仓库](https://github.com/hlillemark/flowm)，模型/数据下载脚本、推理与训练入口、RSSM等对照 | 同属优先核验候选；先审单个checkpoint及最小数据切片。是否适合有限力接触动作要另审，不全量下载 |
| DreamerV3 | [作者仓库](https://github.com/danijar/dreamerv3)、[RSSM源码](https://github.com/danijar/dreamerv3/blob/main/dreamerv3/rssm.py) | JAX实现；抽取或改写PyTorch须标适配、验证时序/重置，不在本轮启动完整在线强化学习 |
| PERSIST | [官方仓库](https://github.com/francelico/PERSIST)、[模型组织](https://huggingface.co/PERSIST-team) | 原规模多卡多天，当前不从头复训；作为直接近邻及结构机制参照 |
| PointWorld | [官方仓库](https://github.com/NVlabs/PointWorld)、[small-droid权重目录](https://huggingface.co/nvidia/PointWorld_models/tree/main/small-droid) | 单checkpoint页面1.83GB，但仍需DINOv3访问/依赖/机器人几何适配；不整包下载34.1GB，不据此承诺可运行 |
| Ctrl-World | [官方仓库](https://github.com/Robert-gyj/Ctrl-World)、[权重](https://huggingface.co/yjguo/Ctrl-World) | README列模型约8GB另加SVD约8GB及CLIP；当前存储不适合作第一批，推理显存未测 |
| Mem-World / MRO-GWM | 本轮未找到可核验Mem-World官方代码/权重；[MRO-GWM项目](https://embodiedvision.github.io/mro-gwm/)未核到实现 | 保留方法条件审查；缺代码如实写未复现，不能用自建相似网络顶替原方法 |
| PropNet / GNS | [PropNet](https://github.com/YunzhuLi/PropNet)、[GNS](https://github.com/google-deepmind/deepmind-research/tree/master/learning_to_simulate) | 用作交互动力学结构依据；PropNet环境较旧，公开checkpoint还说明后续调参优于原文，重评与原结果复现分开 |

## 三类证据分列

白话：解决“用了同名骨干就宣称复现论文”的问题。输入源码、配置、权重与运行结果，输出明确证据级别。例如跑作者PushT权重是重新评估，改RGBD和状态标签训练是迁移适配；它们都不等于从头复现原论文训练。

1. 基础架构比较：同信息、监督和候选评分，报告容量、历史覆盖、训练曲线、全部种子及成本。包括完整历史、循环状态、检索、观测地图＋动力学。
2. 原设定核验：固定作者版本、原任务、输入、checkpoint与官方指标。仅跑通前向是运行检查；重评checkpoint与复现训练分别标记，数值差异保存。
3. 任务迁移：逐项登记动作语义、历史窗口、深度/相机输入、监督及读出头改动。原版条件与统一监督适配分别报告，不能把权限不同的数字直接解释为架构优劣。

尤其需要先检查监督是否含答案信息：若两条不同物体轨迹在全部未来图像/本体观测中不可区分，纯视觉预测目标不要求还原隐藏位置。新增状态读出时要写清标签量、世界模型是否冻结、梯度是否回传。此为根据任务与原方法目标作出的推断，不是原论文已做过的失败实验。

## 研究判断与阅读优先级

当前不能主张：首次持续3D世界状态、首次视野外动态、首次用历史改善动作条件生成、首次用交互图做部分观测控制。没有发现与当前精确配对完全一样的评估，不意味着已证明空白或方法优势。

优先阅读DINO-WM的观测/动作/损失接口，FloWM的结构状态与自运动、PropNet的部分观测交互，再对照Mem-World/PointWorld/PERSIST的强输入与限制。这样分别理解视觉表征、时间记忆、物理交互及已有覆盖，不要求先凭空发明一整套架构。

面向ICML的判断依据是[2026官方评审说明](https://icml.cc/Conferences/2026/ReviewerInstructions)：技术可靠性、表达、意义和原创性分别评估，原创性可以来自对已有方法的新认识，不规定最低参数量。我们的判断是：当前SH-03工程夹具不足以独立支撑方法论文；较小但能排除替代解释的实验可以成为起点，最终仍须明确新认识、强对照和可信适用范围。此判断不是录用预测。
