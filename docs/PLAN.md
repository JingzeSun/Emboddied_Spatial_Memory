# VSMT-lean 从合同到论文结果的完整计划（D-224）

本文件只维护 VSMT-lean（实体生命周期版本化事务，D-224）从当前代码到论文结果的步骤链、依赖、状态、交付物和失败分支。旧 VM-00～VM-06 计划、CPMT、空间世界模型与地点层路线已随分支 `archive/pre-d224-unified-graph` 归档，本文不再列出。方法定义见 [METHOD.md](METHOD.md)，字段见 [DATA.md](DATA.md)，决策理由见 [DECISIONS.md](DECISIONS.md)，运行证据见 [EXECUTE.md](../EXECUTE.md)。本文**不自动切换研究主张**：任何会改变论文声称什么的替代路线，都必须先暂停、报告证据，再写成新决策交用户批准。

## 一、最终目标与总链路

在同一冻结公开 RGB-D 前端、同一召回规则、同一执行器和同一评价协议下，比较 VSMT-lean、TAF、ELU-P、RAC 和 LOW，回答 hindsight 监督的可逆生命周期修订能否减少陈旧实体、误删并保住被搬动物体的身份。

```text
S0 合同冻结（S0-01 → S0-06）
  ↓
S1 前端与数据小试（S1-01 → S1-02a → S1-02b → S1-05）
  ↓
S2 五臂开发表（S2-01 → S2-05）
  ↓
S3 正式数据、训练、validation 与一次性 test（S3-01 → S3-06）
  ↓
S4 论文
```

当前执行点：**S0 五份合同全部审查通过（LOG-214～LOG-219），S1-01 资产与容量授权申请材料已实现待审**（LOG-220），**D-224-S1 九项裁决已批准并落地，服务器冻结资产已只读核验通过**（LOG-221）。D-224 与 D-224-E/F/G 已批准；旧方向已归档到 `archive/pre-d224-unified-graph`，`main` 只含精简版文档。**四项已知冲突全部消解并各有回执**：Python 按两解释器分工、Vulkan 可枚举到 NVIDIA GPU、ProcTHOR-10K 定为 0.1.2（以上 LOG-221），ViT-B/14 完成一次性摘要登记（LOG-223）；基础环境缺 hydra 的阻塞已于 LOG-222 解除。S1-01 里待冻结的 null 只剩 `worker_rule.headroom_fraction`。当前开四个位（三只读/本地登记加一依赖安装），没有任何资产放置、数据生成或训练授权。**S1-01 的 worker 推导死锁已按 D-224-S1 裁决 14 解开**：占用测量移入新拆出的 S1-02a（4 worker × 1 house，4 条 episode 计入正式 50 条），S1-02b 再按算出的 worker 数补齐其余 46 个；S1-01 只保留推导规则。数据盘已由用户清理并经只读核验，22 G → 43 G 可用（LOG-224）。S1-02a 尚未获得运行授权。**2026-09-20 用户批准 D-224-X 裁决 X1～X6**（S0 合同隐患审查的六项修正）：S0-01/02/03/04/05 各追加 v2 合同、v1 字节冻结并由测试钉住摘要，S0-03 求解器与 S0-04 评价器按逐列等价重写；本会话复审修正四处后八个 lean 模块分进程共 386 项本地通过，五份 v2 已按用户批准提交推送（LOG-225）。S1-02a 开工前新增一项前置冻结：S0-02 v2 要求 seed 与 test/validation 规模在第一条 episode 前给定。**2026-09-20 用户审过 S1-01 v1 并把 `headroom_fraction` 定为 0.2**；随之发现 S0 转 v2 后 S1-01 仍指着 v1，已追加 S1-01 v2 改指 v2 并把 S1↔S0 一致性纳入跨合同测试（LOG-226）。S1-01 待冻结 null 已清零。**2026-09-20 用户审过 S1-01 v2 与五份 S0 v2**，并已实现 S1-02a 合同（LOG-227）；该合同把划分复用 S0-02 的 `assign_split`、worker 推导复用 S1-01 的 `derive_worker_count`，不另写第二套。**2026-09-20 用户冻结划分：seed=20260920、validation=50、test=100**（LOG-228）。test 与 validation 的成员、train 块起点与 S1 的开发 house 至此全部确定；`train_houses` 留到 S3-01 登记且只能下调。这三个值只登记在 S1-02a v2 一处，S0-02 v2 的值槽保持 null 并由跨合同测试钉住。S1-02a 六个授权位仍全为 false：用户已口头授权，但核对后确认**缺 runner 与 S0-02 六个路线/干预数值**，开了也跑不了，故记录授权、位不打开（LOG-229）。服务器已同步到受审提交，权威全量 **1249/1249 通过**（首次全绿）；同一次运行查出冻结摘要钉的是行尾表示而非内容，三处坏钉已修。**2026-09-20 冻结三个路线幅度**（translation 0.25／rotation 90／look 30，前两个与 `source` 网格一致并由校验器绑定），追加 S0-02 v3；仍缺 `maximum_actions`、`maximum_interventions_per_episode`、`minimum_yield` 三个数值。runner 勘定结论：驱动代码可复用 ops 的 CloudRendering 模板，但**覆盖式重访路线规划器与干预选择策略尚无可执行规范**，属设计决定而非照规格实现，故未动手写（LOG-230）。

## 二、状态和执行规则

| 状态 | 含义 |
|---|---|
| 已完成 | 代码和必要测试已经受审，或已有可复用的真实证据 |
| 已实现待授权 | 代码已提交并通过测试，但步骤合同中的真实执行授权位仍为 false |
| 未开始 | 依赖未满足，尚不能产生正式产物 |
| 封存 | 已确定但当前阶段禁止打开或使用 |

真实运行的授权由步骤合同里的布尔位表达并由用户在运行前审；真实运行要求 clean checkout，并逐次记录 git commit、合同摘要、输入摘要、产物摘要、worker 数与退出码、资源用量和全部失败。表格中的"完整动作"是必须完整执行的规范，不是可以挑着做的菜单。不能运行成功的 house 或 episode 必须留下失败 receipt，不得省略、替换或补样。测试夹具只证明代码行为；真实步骤只有服务器产物、摘要和退出回执齐全才算完成。

## 三、S0：合同冻结

### S0-01 实体记忆 schema 与五原子程序合同

| 项 | 内容 |
|---|---|
| 状态 | **v1 已完成、v2 已提交（本会话复审后用户批准，LOG-225）**（v1 于 2026-09-19 用户审过，LOG-214；v2 按 D-224-X 裁决 X6 给版本记录加 `opened_by` 并写明折叠记录归档口径，本地 47 项通过，LOG-225） |
| 输入 | METHOD 第三、四节；`cpmt.hashing` 与 `graph_ops` 的纯函数 |
| 完整动作 | 写实体记录 schema、状态机、版本链、五原子结构前条件、REPLACE 复合、帧程序原子提交与回滚、共享去重与 dormancy 规则、**实体 token 序列化 schema 与帧级稀疏残差（D-224-G）** 的机器合同；实现自足的实体记忆核心并补测试 |
| 输出 | [`lean_s0_entity_memory_v2.json`](../configs/vsmt/lean_s0_entity_memory_v2.json)（v1 字节冻结）、纯核心 [`lean_memory.py`](../src/vsmt/lean_memory.py)、合同测试 [`test_vsmt_lean_memory.py`](../tests/test_vsmt_lean_memory.py) |
| 继续门 | 五原子正反例各至少一组通过；非法程序整帧回滚且 M_{t−1} 逐字节不变；token 字段顺序由合同固定并有测试 |

### S0-02 干预数据生成合同

| 项 | 内容 |
|---|---|
| 状态 | **v1 已完成、v2 已提交（本会话复审后用户批准，LOG-225）**（v1 于 2026-09-19 用户审过，LOG-215；v2 按 D-224-X 裁决 X6 把前缀分配顺序改为 test→validation→train，本地 43 项通过，LOG-225） |
| 输入 | DATA 第一～四节；D-199～D-204 的不可观测窗口机制 |
| 完整动作 | 写 house 来源、哈希前缀划分、覆盖式重访路线模板、三类干预及其窗口判定、public/private/provenance 三面 schema、失败保留规则的机器合同；全部数值先登记为 null 或 proposed |
| 输出 | [`lean_s0_intervention_data_v2.json`](../configs/vsmt/lean_s0_intervention_data_v2.json)（v1 字节冻结）、只读检查核心 [`lean_intervention.py`](../src/vsmt/lean_intervention.py)、测试 [`test_vsmt_lean_intervention.py`](../tests/test_vsmt_lean_intervention.py) |
| 继续门 | 干预只在涉及容器不在视锥内的窗口执行；private 与 provenance 不进任何 reader 白名单 |

### S0-03 特征、召回与分配合同

| 项 | 内容 |
|---|---|
| 状态 | **v1 已审通过、v2 已提交（本会话复审后用户批准，LOG-225）**（v1 于 2026-09-20 通过，D-224-R；v2 按 D-224-X 裁决 X5 把字典序规范化改到等式子图上、与 v1 逐列等价，64×500 单帧 125 秒 → 0.01 秒，本地 58 项通过，LOG-225） |
| 输入 | METHOD 第五～七节 |
| 完整动作 | 写前端 cache 字段、应可见与自由空间覆盖比例、召回规则 k/k′/R_active、三个头的特征列表与顺序、代价矩阵与并列规则、封存 digest、私有扰动不变性检查的机器合同；**登记共享 ReID 适配头（D-224-E）的架构、训练数据范围与 S1-05 二选一规则** |
| 输出 | [`lean_s0_assignment_v2.json`](../configs/vsmt/lean_s0_assignment_v2.json)（v1 字节冻结）、纯核心 [`lean_assignment.py`](../src/vsmt/lean_assignment.py)、测试 [`test_vsmt_lean_assignment.py`](../tests/test_vsmt_lean_assignment.py) |
| 继续门 | 同一公开输入换 private 文件后召回顺序、特征矩阵与未训练 logits 逐字节相同 |

### S0-04 teacher、评价器与指标合同

| 项 | 内容 |
|---|---|
| 状态 | **v1 已审通过、v2 已提交（本会话复审后用户批准，LOG-225）**（v1 于 2026-09-20 通过，LOG-219；v2 按 D-224-X 落实 X1 同帧重复色块、X2 未定义 house、X5 评价器分连通块匹配、X6 生命周期版本数与真值表 `in_scope`，合同 53 条布尔声称全绑定，本地 88 项通过，LOG-225；复审修正 X1 组级记账、X2 不适用臂例外、范围外实体退出精确率分母） |
| 输入 | METHOD 第八、十一节；DATA 第六、七节 |
| 完整动作 | 写标签定义、δ_moved、七项指标、匈牙利匹配口径、bootstrap 与主门、三分解记账、nuisance probe 的机器合同 |
| 输出 | [`lean_s0_teacher_metrics_v2.json`](../configs/vsmt/lean_s0_teacher_metrics_v2.json)（v1 字节冻结）、纯核心 [`lean_teacher.py`](../src/vsmt/lean_teacher.py)、测试 [`test_vsmt_lean_teacher.py`](../tests/test_vsmt_lean_teacher.py)；只依赖 S0-03 产物的数据形状，不导入其函数 |
| 继续门 | 指标清单在任何数据生成前冻结；清单外指标不得计算或报告 |

### S0-05 对照、消融与配置网格合同

| 项 | 内容 |
|---|---|
| 状态 | **v1 已审通过、v2 已提交（本会话复审后用户批准，LOG-225）**（v1 于 2026-09-20 通过，LOG-219；v2 按 D-224-X 落实 X3 AssocOnly/HeuristicLabel 同配方重训不复用权重、X4 预登记 ELU-P `rollout_config` 与三个拟合量的估计程序，合同 73 条布尔声称全绑定，本地 44 项通过，LOG-225；复审修正 HeuristicLabel 私有依赖声称） |
| 输入 | METHOD 第九、十节；D-224-R 三项前提：规则臂门内分级代价（−余弦 / 质心距离）、每个规则臂网格含宽门或无门选项、不合格格用登记的哨兵 logit 表达 |
| 完整动作 | 写 TAF/ELU-P/RAC/LOW 的机制、参数与有限网格，VSMT-lean 训练配方与 τ_r 网格，**四组**消融（NoVersion/HandCost/HeuristicLabel/**AssocOnly**）定义，每方法 ≤12 配置规则，**必做附录臂 `LLM-op` 的 validation-only 口径**与可选臂 **`VSMT-lean-ctx`（D-224-F）** 的准入条件与单列报告规则 |
| 输出 | [`lean_s0_arms_v2.json`](../configs/vsmt/lean_s0_arms_v2.json)（v1 字节冻结）、纯核心 [`lean_arms.py`](../src/vsmt/lean_arms.py)、测试 [`test_vsmt_lean_arms.py`](../tests/test_vsmt_lean_arms.py)；规则臂只产生喂给 S0-03 求解器的 logit 与存在决定，特征按封存顺序取位置 |
| 继续门 | 每方法网格 ≤12 且预登记；规则臂无梯度 |

### S0-06 用户合同审查

| 项 | 内容 |
|---|---|
| 状态 | **v1 已通过；v2 已提交（本会话复审后用户批准，LOG-225）**（2026-09-20 用户批准 S0-01～S0-05 v1；同日 D-224-X 隐患审查后五份 v2 待用户代码审查；跨合同一致性由 `test_vsmt_lean_cross_contract.py` 机器核对，20 项通过，含五份 v1 的 sha256 钉住与 D-224-X 六项跨合同一致性） |
| 输入 | S0-01～S0-05 全部合同与测试 |
| 完整动作 | 用户逐份审查；修改只能追加新版本，不改已审字节 |
| 输出 | 审查回执；S1 授权位仍为 false |
| 继续门 | 用户批准后才可申请 S1 授权；**S1-01 资产与容量授权申请材料按用户要求留到下一次会话准备，本次不申请任何授权** |

## 四、S1：前端与数据小试

### S1-01 资产与服务器容量

| 项 | 内容 |
|---|---|
| 状态 | **v1 已审通过（2026-09-20 用户代码审查）、v2 已提交待审**（LOG-220～224、226；v1 字节冻结并由跨合同测试钉住摘要；v2 只做三件事：`depends_on` 改指 S0 v2、`headroom_fraction` 冻结为 0.2、S1↔S0 一致性交给 `test_vsmt_lean_cross_contract.py` 机器核对（+9 项）。S1-01 本身 83 项、八个 lean 模块分进程共 401 项本地通过；九项资产登记完整、四项冲突全部有回执、**待冻结 null 已清零**；按 D-224-S1 开四个位，未放置任何资产、未装模拟器） |
| 输入 | D-215 冻结的 SAM 2.1 摘要；LOG-136 来源回执登记的 DINOv2、AI2-THOR、ProcTHOR 标识；ProcTHOR-10K 由 D-224-S1 定为 0.1.2 并按上游 LFS 指针登记；DINOv2 ViT-B/14 由 LOG-223 一次性登记，URL 从钉死的 dinov2 commit 源码推导并经 ViT-S/14 回执实证 |
| 完整动作 | 写资产登记、许可证登记、容量探测清单、worker 推导规则、两份回执字段与停止条件的机器合同；用户授权后才下载并核对资产摘要；探测 CPU、RAM、GPU 显存、磁盘、渲染后端；按单 worker 实测占用定最大安全 worker 数 |
| 输出 | [`lean_s1_assets_capacity_v2.json`](../configs/vsmt/lean_s1_assets_capacity_v2.json)（v1 字节冻结）、纯核心 [`lean_assets.py`](../src/vsmt/lean_assets.py)、测试 [`test_vsmt_lean_assets.py`](../tests/test_vsmt_lean_assets.py)；授权后另出资产回执与容量回执 |
| 继续门 | 登记在获取之前；标识不全的资产不可获取（当前九项全部登记完整）；摘要不符即停且不得换镜像、换版本或先用着；worker 数有实测依据并写进回执——容量读数已有，但单 worker 实测占用尚未测量，因此 worker 数仍不可算 |

### S1-02a 4-worker pilot 与占用实测

| 项 | 内容 |
|---|---|
| 状态 | **v1 已审通过、v2 已提交待审；划分已冻结**（LOG-227/228；seed=20260920、validation=50、test=100 于 2026-09-20 冻结，`train_houses` 留到 S3-01；本地 54 项只读检查通过，九个 lean 模块分进程共 464 项通过。六个授权位仍全为 false，未跑任何 episode） |
| 输入 | S0-02 v2 合同（**seed 与 test/validation 规模须先冻结**，因为 v2 把分配顺序改为 test→validation→train，train 块的起点由它们决定；裁决 X6）、S1-01 容量读数与 worker 推导规则 |
| 完整动作 | 取 train 块哈希前缀最前的 **4 个 house，4 个 worker 各跑 1 条 episode**：覆盖式重访路线、不可观测窗口干预、public/private/provenance 三面写盘；同时实测 `cpu_cores_per_worker`、`ram_gb_per_worker`、`vram_gb_per_worker`、`disk_gb_per_worker` 与 4 路并发是否安全；失败 house 保留 receipt 不替换 |
| 输出 | [`lean_s1_02a_pilot_v2.json`](../configs/vsmt/lean_s1_02a_pilot_v2.json)（v1 字节冻结）、纯核心 [`lean_pilot.py`](../src/vsmt/lean_pilot.py)、测试 [`test_vsmt_lean_pilot.py`](../tests/test_vsmt_lean_pilot.py)；授权后另出 4 条 raw、pilot 生成回执与**占用回执**（含 `concurrency_verified_at=4`、峰值 RSS/显存/磁盘、墙钟与退出码） |
| 继续门 | 四条全部有终态；占用五项齐全才允许推导 worker 数。**这 4 条是正式 S1-02 样本的一部分，计入 50，不得跑完丢弃重生成**；pilot 失败不构成"重试到好为止"的理由 |

**白话：为什么先跑 4 个。** 它解决的是"worker 数要由实测决定，可实测又必须先跑起来"这个先有鸡还是先有蛋。输入是 4 个 house 和 4 个并发 worker，输出是能不能跑通加一份占用读数。例如实测每 worker 峰值 6 GB 内存、2 GB 显存，就能算出这台机器还能开多少个。它**不等于**已经证明更大并发安全：pilot 只验证了 4 路，`concurrency_verified_at` 与算出来的 `derived_worker_count` 必须分开记；扩产后若出现不稳定，如实报告，不得事后把数字悄悄改小当没发生。

### S1-02b 扩到 50 house

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S1-02a 占用回执；S1-01 的 worker 推导规则与已冻结的 `headroom_fraction`＝0.2（每项可用资源打八折再除以单 worker 占用） |
| 完整动作 | 按 S1-01 公式算出最大安全 worker 数并记下瓶颈项，用该并发补齐哈希前缀其余 **46 个 house**，各生成一条 episode；失败 house 保留 receipt 不替换 |
| 输出 | 合计 50 条 raw、生成回执、干预成品率、`requested/actual` worker 数与资源用量 |
| 继续门 | 计划数＝成功数＋失败数；成品率写入回执；低于 S0-02 登记下限触发规模裁决，**不得换 house 挑好样本** |

### S1-03 共享前端 cache

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S1-02b public 面、S1-01 资产 |
| 完整动作 | 跑 F-01 reader 生成 fragment、几何、自由空间、可见体积；同时提取 ViT-S/14 与 ViT-B/14 两套描述子；写逐帧与逐 episode 封印 |
| 输出 | 50 条 cache、fragment 成品率、每帧 proposal 数分布 |
| 继续门 | 任一帧 proposal 溢出即该 episode construction failure |

### S1-04 前端诊断

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S1-03 cache；private 只在特征封存后打开 |
| 完整动作 | 量冻结描述子（ViT-S/14、ViT-B/14）与共享 ReID 投影三者的跨视角分离度分布，即同物体跨视角余弦减异物体余弦；按 S0-03 召回规则算 recall_miss@k；统计应可见、自由空间覆盖比例分布；**统计单视角 fragment AABB 对真值整物体 AABB 的三维 IoU 分布**（BIND 用单视角 AABB 覆盖实体 AABB，而节点匹配用裁决 C 冻结的 IoU 0.3、选配置又用节点 F1；若中位 IoU 不到 0.3，所有臂的 F1 接近 0，选参变噪声；D-224-X） |
| 输出 | 分离度报告、recall_miss 报告、fragment-真值 IoU 报告 |
| 继续门 | 分离度低于 S0-03 登记下限触发证据层级裁决，不得就地调前端；fragment-真值中位 IoU 低于 0.3 触发匹配口径裁决，不得在 S2 就地改 AABB 累积规则 |

### S1-05 描述子选择与 S1 收口

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S1-04 报告 |
| 完整动作 | 按 S0-03 登记的规则在冻结描述子与共享 ReID 投影中选一次并冻结；写 S1 收口回执 |
| 输出 | 描述子/投影冻结回执；若选中 ReID 投影，另记冻结描述子基线以供论文并列报告 |
| 继续门 | 此后不得再换描述子 |

## 五、S2：五臂开发表

### S2-01 共同 runner 与实体记忆包装

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S0-01、S0-03 合同；S1-05 cache |
| 完整动作 | 实现 `cache 帧 + M_{t−1} → 帧程序 → M_t` 的共同 runner；共享召回、去重、dormancy、应可见判定与共同更新后审计；**`entity_geometry` 由五臂共用的确定性函数从（公开体素集，M_{t−1}）在线算出并有纯函数测试**；**非法程序回滚后对该帧提交空程序**（tick 推进、维护规则照常）并计数（D-224-X） |
| 输出 | runner、接口测试 |
| 继续门 | 五臂读取逐字节相同的 cache clone |

### S2-02 四个对照实现

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S0-05 合同；现有 `baselines.py` |
| 完整动作 | clean-room 实现 TAF、ELU-P、RAC、LOW 的代价矩阵与存在决定；文件头登记来源、差异与 not-an-official-implementation；`LLM-op` 实现接口与 validation-only 入口，不在 S2 调用 |
| 输出 | 四臂代码与分支测试 |
| 继续门 | 阈值全部来自无默认值配置 |

### S2-03 VSMT-lean 实现

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S0-03、S0-05 合同 |
| 完整动作 | 实现三个代价头、代价矩阵、矩形分配、编译与提交；训练循环与两轮 DAgger；实现 `NoVersion` 与 `AssocOnly` 两个消融开关（同一代码路径、同一训练预算；**AssocOnly 同配方重训、去掉存在损失项，不复用 VSMT-lean 权重**，裁决 X3）；第 0 轮 DAgger 的 ELU-P 轨迹取 S0-05 v2 预登记的 `rollout_config`（裁决 X4）；不读 slot/路径/样本名 |
| 输出 | 模型代码、训练入口、单元测试 |
| 继续门 | 候选换序后每个实体的 logit 跟着实体走、最终程序不变 |

### S2-04 teacher 与评价器

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S0-04 合同 |
| 完整动作 | 实现封存后标签器（含同帧重复色块的 `duplicate_of_labelled`，裁决 X1）、七项指标、三分解、nuisance probe、私有扰动不变性检查；评价器收到的真值表含所有可解析物体并带 `in_scope` 标志（裁决 X6）；每项指标的未定义 house 清单按 `undefined_houses` 算一次并传给全部配对比较（裁决 X2） |
| 输出 | 评价器代码与测试 |
| 继续门 | 修改 private 不改变任何公开产物字节 |

### S2-05 50 house 开发表

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S2-01～S2-04；S1 cache |
| 完整动作 | 在 50 house 上跑五臂（VSMT-lean 只做一次开发训练），**并把 `NoVersion` 与 `AssocOnly` 两个消融用同一次开发预算一起跑**，兑现风险探针的第三件事；出第一张表、逐例失败、runtime/memory、接口问题清单 |
| 输出 | 开发表，含 VSMT-lean 对 `NoVersion`、对 `AssocOnly` 的开发差 |
| 继续门 | 只用于发现工程问题与早期风险读数；**不据此选择论文赢家、不调网格、不因开发差不利就改设计或删消融**；`HandCost`、`HeuristicLabel`、`LLM-op` 与 `VSMT-lean-ctx` 仍只在 S3 跑 |

## 六、S3：正式数据、训练、validation 与一次性 test

### S3-01 冻结正式数据与统计预算

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S1 成品率、S2 开发表 |
| 完整动作 | 冻结 train/validation/test = 300/50/100 house 的 manifest（seed 与 test/validation 规模已在 S1-02a 前冻结，此处只允许按成品率下调 train，裁决 X6）、bootstrap seed、主门效应量、停止规则；登记未定义 house 的排除规则与功效按有效 house 数计算（裁决 X2）、最强对照在 test 上逐指标后验选取的口径、回执里钉住 Python 版本（bootstrap 依赖 `random.Random`） |
| 输出 | 三个互斥 manifest、功效说明 |
| 继续门 | test manifest 此后只读一次 |

### S3-02 正式生成与 cache

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S3-01 manifest |
| 完整动作 | 按最大安全 worker 生成 train/validation 的 raw 与 cache；test 生成后封存不读 |
| 输出 | 正式数据、失败与资源回执 |
| 继续门 | 固定样本全部有终态；失败不替换 |

### S3-03 训练与配置选择

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S3-02 train；S0-05 网格 |
| 完整动作 | 先在 train 上按 S0-05 v2 登记的程序估 ELU-P 三个拟合量，并用预登记的 `rollout_config` 产生第 0 轮轨迹与 HeuristicLabel 标签（裁决 X4）；再 VSMT-lean 两轮 DAgger × 5 seed；四组消融同预算（AssocOnly 重训，裁决 X3）；规则臂各 ≤12 配置；`LLM-op` 只在 validation 上跑一次；只读 validation 选择 |
| 输出 | checkpoint、配置、训练曲线、完整失败 |
| 继续门 | 不读 test；不按单一场景临时增配 |

### S3-04 validation 后冻结

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S3-03 全部候选 |
| 完整动作 | 选最终 checkpoint、τ_r 与各臂配置；写冻结回执与 test 可执行代码摘要 |
| 输出 | 冻结回执 |
| 继续门 | 此后不得改算法、数据、阈值、指标或预算 |

### S3-05 test 一次性运行

| 项 | 内容 |
|---|---|
| 状态 | 封存，未打开 |
| 输入 | S3-04 冻结字节、S3-01 test manifest |
| 完整动作 | 一次性读取 test，跑五臂与四组消融、配对统计、house 级 bootstrap；`LLM-op` 不进 test |
| 输出 | 主表（含与主比较并列的 `AssocOnly` 行）、消融表、三分解、规模与成本、逐例失败 |
| 继续门 | 只跑一次；失败照实报告，不换样本、不改方法、不改指标 |

### S3-06 主张审计

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S3-05 不可变结果 |
| 完整动作 | 逐条检查证据是否支持第二节三项贡献；不支持的主张不写 |
| 输出 | 论文结果包与可复现实验索引 |
| 继续门 | 主门失败就报告 no-go，不通过换数据或缩减对照制造成功 |

## 七、S4：论文

| 项 | 内容 |
|---|---|
| 状态 | 未开始 |
| 输入 | S3-06 结果包 |
| 完整动作 | 写作、失败分析、成本与限制 |
| 输出 | 论文稿 |
| 继续门 | 证据不支持的主张不写 |

## 八、时间与最近动作

| 阶段 | 估计 | 主要不确定项 |
|---|---|---|
| S0 | 3 天 | 用户审查往返 |
| S1 | 1 周 | SAM2 资产获取；跨视角余弦分离度；干预成品率 |
| S2 | 1 周 | RAC 投影实现；DAgger 稳定性 |
| S3 | 2 周 | 生成吞吐；统计功效 |
| S4 | 1 周 | |

估计不承诺。最近动作按顺序为：

1. 2026-09-19 用户批准 D-224 裁决 A～D，并要求把旧方向归档到分支 `archive/pre-d224-unified-graph`、在 `main` 上重写 METHOD/PLAN/DATA。已完成文档重写，未生成数据、未训练、未连接服务器。
2. 2026-09-19 用户批准 D-224-E/F/G：共享 ReID 适配头登记为 S1-05 可选前端、`VSMT-lean-ctx` 登记为可选臂、S0-01 固定实体 token schema；并确认执行顺序为先只冻结看数据前必须定的项，五臂一起在 50 house 跑通，再按三分解决定是否启用 E/F。
3. 2026-09-19 用户审过 S0-01 并采纳其中三处语义选择；同时批准把对话初期四项裁决中的前三项补进文档（`NoVersion` 与 `AssocOnly` 提前到 S2-05、新增必做消融 `AssocOnly` 并与主比较并列、`LLM-op` 收口为必做附录臂），外部基准第二张表推迟到 S2-05 后再裁。
4. 2026-09-19 用户审过 S0-02，并确认 `LLM-op` 维持必做附录臂。
5. 2026-09-19 S0-03 首版实现后经 Codex 审查退回，返工版落地（状态无关的全局召回通道、−logit 代价、字典序最小最优解、两阶段封存、合同绑定关键声称），三处语义变化登记为 D-224-S03，待用户复审。
6. 2026-09-19～20 S0-04 teacher、评价器与指标合同实现并经审核重写，待用户代码审查（LOG-217）。
7. 2026-09-20 用户批准裁决 L～Q 全部按推荐口径执行（D-224-LQ）；METHOD 第六、八、十一节与 DATA 第六、七节据此更正，合同绑定该裁决编号。
8. 2026-09-20 用户批准 D-224-R：S0-03 返工版复审通过并提交，三条规则臂约束登记为 S0-05 前提，S0-03 合同补 up_axis_index；S0-05 开始。
9. 2026-09-20 S0-05 对照、消融与配置网格合同实现，待用户代码审查（LOG-218）。
10. 2026-09-20 用户批准 D-224-SW：五项口径按推荐执行，S0-05 提交推送，S0-06 用户合同审查开始；跨合同一致性检查落为测试。
11. 2026-09-20 用户批准 S0-04 与 S0-05 通过代码审查；S0-06 用户合同审查完成，S0 全部五份合同审查通过。S1-01 资产与容量授权申请材料留到下一次会话准备，本次会话不再推进。
12. 2026-09-20 S1 开始前先做归属检查：确认 S0 合同阶段的产物恰为五份 `lean_s0_*` 合同、五个 `lean_*` 纯核心与六个 `test_vsmt_lean_*` 测试，其余 `vm04_*`／`d2xx_*`／`l1_*`／`cpmt` 属旧方向；其中 D-215、D-224 资产合同、F-01 reader 合同及其按字节绑定的七个文件是 S1 的活依赖，不得归档或改字节。随后实现 S1-01 资产与容量授权申请材料（LOG-220），待用户代码审查与六项裁决。
13. 2026-09-20 用户一次批准 D-224-S1 九项裁决并授权服务器只读核验与清理。九项全部落地（ProcTHOR-10K 定 0.1.2、ViT-B/14 本地登记待执行、两解释器分工、只读探测渲染后端、许可证留后、清理 tests/README、删 84 个孤儿字节码、切断 lean 对 cpmt.executor 的传递性 import）。服务器核验七项冻结资产标识全部一致，Vulkan 能枚举到 NVIDIA GPU，simulator-py39 已备齐 ai2thor/procthor；新发现基础环境缺 hydra 使 SAM2 无法 import。数据盘清理已只读勘定 21.9 GB，删除命令被本地安全策略拦下未执行（LOG-221）。
14. 2026-09-20 用户批准补充裁决 10～13：追认 9-19 资产放置（凭 reflog 重建时间线）、按 D-224 已有授权安装 hydra-core/omegaconf/iopath（torch 与 SAM2 工作树未变，SAM2 可 import，生成器 17 参数与登记一致）、数据盘清理由用户自己执行、estimator 5.5 GB 因 F-01 兼容适配器仍在用而保留（LOG-222）。
15. 2026-09-20 执行裁决 2：ViT-B/14 一次性摘要登记完成（URL 由钉死 dinov2 commit 源码推导并经 ViT-S/14 回执实证，346,378,731 字节 / `0b8b82f8…`，核对 768 维/patch 14/12 层/86.58M 参数后删除临时文件）。四项已知冲突至此全部拿到回执，S1-01 待冻结 null 只剩 `worker_rule.headroom_fraction`（LOG-223）。
16. 2026-09-20 用户清理数据盘（22 G → 43 G 可用，保留清单九项经只读核验全在），并批准补充裁决 14：S1-01 的 worker 死锁按方案 A 解开，占用测量移入 S1-02a（4 worker × 1 house）、S1-02b 扩到 50 house；pilot 的 4 条计入正式样本，`concurrency_verified_at` 与 `derived_worker_count` 分开记（LOG-224）。
17. 2026-09-20 用户审过 S1-01 v1、定 `headroom_fraction`＝0.2，并要求核对 S0 转 v2 是否连带影响 S1。核出三处：S1-01 `depends_on` 仍指 v1、headroom 待冻结、S1 从未进入跨合同核对。追加 S1-01 v2（v1 字节冻结并钉住摘要），跨合同测试加 9 项 S1↔S0 检查；PLAN 的 S1-02a 前置冻结与 S1-04 的 IoU 诊断在 v2 那批已同步，无需再改（LOG-226）。
18. 2026-09-20 用户审过 S1-01 v2 与五份 S0 v2，并要求写 S1-02a 合同。合同、纯核心与测试已实现待审（LOG-227）：pilot 形状固定为 4 worker × 1 house，4 条计入 50 条且禁止看过结果后重生成；占用取峰值、在完整 episode 上量、并把 `concurrency_verified_at` 与算出来的 worker 数分开记。**seed 与 test/validation 规模用户未给定，合同中保持 null，须冻结后才能跑第一条 episode。**
19. 2026-09-20 用户审过 S1-02a 并冻结划分：seed=20260920、validation=50、test=100。追加 S1-02a v2（v1 字节冻结并钉住摘要），校验器改为「三个值要么全开要么全冻」，跨合同测试加 9 项钉住「划分只在一处登记、S0-02 值槽保持 null」（LOG-228）。
17. 2026-09-20 S0 合同隐患审查后用户批准 D-224-X 裁决 X1～X6：同帧重复色块记 `duplicate_of_labelled`、未定义 house 按指标排除并计数、AssocOnly 同配方重训、预登记 ELU-P `rollout_config` 与拟合程序、求解器规范化改等式子图（64×500 单帧 125 秒 → 0.01 秒）与评价器分连通块匹配、划分顺序 test→validation→train、折叠记录归档口径、生命周期版本数、真值表 `in_scope`。五份 v2 合同追加、v1 字节冻结并钉摘要，八个 lean 模块分进程 382 项通过；本会话复审修正四处（X1 组级记账、X2 不适用臂例外、HeuristicLabel 私有依赖声称、范围外实体退出精确率分母）后 386 项通过，五份 v2 已按用户批准提交推送（LOG-225）。

## 九、失败时的暂停点与待触发裁决

失败时先暂停并如实报告证据，不得在同一轮里自行选定替代路线；任何替代路线在执行前必须写成新决策并经用户批准。

| 步骤 | 失败长什么样 | 暂停点与必须触发的裁决 |
|---|---|---|
| S1-01 | 资产摘要与 D-215/LOG-136 登记值不符 | 原样停下报告，**不得**换镜像、换 tag 或先用着；是否重新冻结前端由用户裁决 |
| S1-02a | CloudRendering 虽能看到 Vulkan 与 GPU，但实际起不来或只落到 llvmpipe 软件光栅 | 触发**渲染后端裁决**：改后端等于动 S0-02 已审字节，须另开版本并经用户批准；不得默默接受软件光栅的吞吐 |
| S1-02b | 干预成品率远低于登记下限；路线无法保证重访 | 触发**规模裁决**：下调 house 数或改路线模板；不得换 house 挑好样本 |
| S1-04 | 单视角 fragment AABB 对真值整物体框的中位 IoU 低于 0.3 | 触发**匹配口径裁决**：裁决 C 冻结的 0.3 与裁决 V 的节点 F1 选参会同时失效；备选是 BIND 时按并集累积 AABB 或改用质心距离匹配，都动已审字节，须用户批准 |
| S1-04 | 两套描述子的跨视角分离度都不足 | 触发**证据层级裁决**：是否降到 L1 oracle mask。这会把主张从"可部署 RGB-D 条件下的比较"改为"感知正确前提下的机制诊断"，属改变论文声称什么，须用户批准 |
| S2-05 | VSMT-lean 在 50 house 上不优于对照 | 不构成结论，照常进入 S3，无需裁决 |
| S3-02 | 成品率低于 S3-01 假设 | 按已冻结停止规则收口，用实际样本量运行，功效不足写入限制；不得事后加样本 |
| S3-03 | 训练不收敛或 DAgger 第 1 轮劣于第 0 轮 | 两轮都报告，按登记规则取主表轮次；不得因结果换轮 |
| S3-05 | 主门失败 | 如实 no-go，不换数据、不缩对照；能保留哪些贡献在 S3-06 逐条审 |
