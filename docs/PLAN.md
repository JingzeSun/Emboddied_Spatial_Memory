# 空间历史驱动的世界模型研究计划

本文件是阶段、审查节点和当前指针的唯一维护处。方法见 [METHOD.md](METHOD.md)，字段见 [DATA.md](DATA.md)，证据见 [EXECUTE.md](../EXECUTE.md)，转向依据为 D-062。

## 当前目标与授权

2026-09-11 用户认可严格成对的空间历史候选，并明确“可以，开始吧，必要的时候重构整个工作区”。当前开始执行；持久三维状态和动态预测不预设为创新，CTL 不预设为新机制。旧科学 no-go、test 封存、源码和结果原路径保留。

白话：先让两个世界的近期输入相同、旧观察揭示的隐藏结构不同，再看同一控制的后果预测和动作选择。例如推杆把物块推向此前见过而当前不可见的挡板；模型应利用过去分清受阻和通过。这不是给出物块未来运动再生成图像，也不是立即建设通用机器人。

D-059 的逐职责代码审查继续有效：当前批次可实现及做必要服务器工程测试，用户审过后才进入依赖它的下一科学批次。仅执行已确定的本阶段，不提前写未确定模型/损失/预算。

## 分阶段交付

| 步骤 ID | 输入与工作 | 输出、继续条件 |
|---|---|---|
| SH-01 成对数据合同 | 已认可的候选；实现严格字段/时序/成对校验和模型输入提取，提供手工正负例 | 可读提交、具体输入输出、服务器回执；用户审查当前批次后进入 SH-02。不是物理案例 |
| SH-02 物理生成器 | 已审合同；选择并固定模拟器版本、坐标/相机、控制器/饱和、物理参数、接触语义、场景和观察路径 | 单职责模拟器实现及必要服务器测试；真实快照恢复、控制执行、渲染和重放。实现审过才生成开发审计案例 |
| SH-03 小规模物理审计 | SH-02 审查与工程通过；D-065固定16对开发世界，64条不同分支及64次独立重放，不因结果增样本 | 完整场景、快照、原始传感器、原始轨迹、失败、可视化和来源摘要。16对全部满足原物理/输入条件才通过；必要修复新版本，不覆盖 |
| SH-04 基础对照协议 | 物理审计通过；冻结训练/开发/确认划分、数据量、监督、固定候选与评分、预算和成功门 | 先交长历史/短历史、历史检索、地图加简单动力学及特权诊断的公平比较合同；没有预算和代码审查不训练 |
| SH-05 复现并定位失败 | 已审基础对照与服务器检查；保持相同数据、信息与动作选择规则 | 逐例预测/接触/动作效果、独立场景组成对统计、成本。短历史的必然失败不算新发现；强对照成功则如实收口 |
| SH-06 决定改进机制 | SH-05 确认并复现的具体失败 | 单一机制假设、对照与预算；不预先绑定 CTL，不靠扩场景/模型追正结果 |
| SH-07 独立确认与交付 | 前阶段已审方法和冻结协议 | 未见场景确认、适当现实来源验证及论文/artifact；目前均 planned，不能视为已授权 test 解封 |

SH-03预算由D-065固定：128次4.9 s模拟执行，新产物2 GiB，按案例边界检查；预计5–10分钟前台，实际耗时待服务器记录。SH-04及以后不预设训练规模、模型架构或实验胜者。测试与计算在服务器由用户手动运行；本地只做源码、文档、Git和标准库静态核查。

## 当前指针

**当前交付SH-04/v1视觉强对照协议提案，尚未实现或授权训练。** 用户明确“可以，下一步”后，SH-03/v2验收批次及批准登记`e901beb`已合并并推送main；新审查分支`review/spatial-history-baselines`。先读[METHOD的SH-04协议](METHOD.md#sh-04-首轮视觉对照协议-v1proposed尚未实现或授权训练)、[DATA的新小试权限与划分](DATA.md#sh-04-新小试数据与模型权限proposed尚未生成)、[机器参数提案](../configs/spatial_history/baseline_protocol_v1.json)和D-067。参数文件明确proposed_not_executable，当前不运行训练、确认评估或旧物理重测。

已完成证据：[SH-03/v2报告](../results/spatial_history_development_audit_v2_wall_clearance.json)为12项/16对通过，原科学提交57d01aa、报告ce5b3f1，LOG-107；原v1失败保留于LOG-106。它们只供工程/输入审计，不能拆分成训练/确认。当前协议文档有新增内容，不借旧SH-03回执认证；旧产物按原代码/合同摘要复用。

### SH-04交付与继续条件

白话：先验证现成视觉编码器能读到旧图里的证据，再建立公平的小规模学习比较。例如先检查两世界近期特征完全相同、首帧的布局信息能被简单读出；这不是已经训练世界模型。本轮完整交付的是协议提案，服务器当前没有新命令，不需要为了同步文档pull或安装依赖。

| 职责批次 | 固定工作与读写范围 | 输出与继续条件 |
|---|---|---|
| SH-04-A 公开视觉输入审计（下一实现批次） | 只读已验收SH-03/v2的16对原始记录，验证来源并提取公开RGB/深度/标定/本体/控制；新环境中固定DINO代码和权重，冻结编码；0训练步、0新模拟 | 公开输入/标签隔离的可审实现、信息泄漏负例测试、权重/完整依赖锁、首帧固定近邻诊断、实际显存/时间/磁盘回执。未通过先定位，不换编码器或扩大数据 |
| SH-04-B 家族划分与新数据 | A审查通过后交48家族清单、跨split去重和来源适配；先只生成train/validation共80对，确认16对暂不生成 | 完整物理审计、raw/public/labels隔离和manifest；不满足物理门的例保留且停止依赖训练，不补样。旧16对始终排除训练/确认 |
| SH-04-C 基线/评分实现冻结 | B审查后按单一职责分别交S/L/R预测器、共享观测地图及两种动力学、统一评分；先必要测试/吞吐核查，不堆叠未审科学代码 | 所有主方法输入/监督一致，具体mask、拟合/接触算子、代码/环境/预算固定且用户审过；达到这些条件才进入SH-05效果实验 |

A拟使用独立数据盘环境，候选依赖PyTorch2.6.0/torchvision0.21.0的CUDA12.4发行组合（[官方版本表](https://pytorch.org/get-started/previous-versions/#v260)），与现有MuJoCo环境隔离；具体依赖闭包与权重摘要必须在A运行前锁定，当前没有安装。预检预计≤20分钟前台，复用原16对，不重渲染；未取到固定权重或超资源预算则保留失败。

本小试资源提案：新环境/权重≤6 GiB、新数据/特征/checkpoint/结果≤6 GiB，峰值CUDA分配≤12 GiB且≤实际设备容量80%，训练最多18次×1500更新、单次≤20分钟、总训练≤6 GPU小时。设备实际显存和长历史模型吞吐要实测，不能由租赁标称值推断；若吞吐表明无法按上限完成全部强对照，先修订预算协议，不静默缩短历史或只留下弱对照。各已确定职责阶段一次同步交付其完整检查/运行/验收/导出入口；当前不提前写未审训练入口。

未来SH-05先在train/validation完成所有候选训练和选参，然后锁定模型/算法/数据/评分；confirmation在该阶段授权后只生成并评估一次，不能用其结果修方法。原50 GB数据盘中的CPMT数据与SH-03失败/通过产物均保留。新小试只作固定模板内参数插值，不承诺论文创新、真实机器人或通用智能。

SH-01审查批准已登记于9044074。SH-02科学提交e3a1d71及通过报告f6b8c58完成核验后，用户明确要求“下一步”，据上下文登记对该批次的审查通过，允许合并main并实施SH-03固定开发审计。此授权不包括SH-04训练协议或模型效果实验。

### SH-03/v2 历史服务器固定命令

以下仅保留原版本57d01aa的操作说明，不是当前待执行任务；METHOD/DATA已进入新提案，不能在当前checkout冒用旧绑定重跑。原成功回执已经验收，无需再次同步或导出。

白话：同一次同步提供“检查新适配→生成完整16例→核验和导出”，避免步骤切换再改入口。输入已验收SH-02报告/源码与固定登记，输出独立案例回执；例如某例完整生成但没有预期碰撞，会保留为audit_failed并继续余下固定例。这不是自动调参或训练流水线。

已核实服务器仓库`/root/Emboddied_Spatial_Memory`，环境`/root/autodl-tmp/spatial-history-venv-v1`；复用环境和EGL，无需安装或删除旧数据。当前已在review/spatial-history-development分支，checkout空闲且`git status --short`无输出时同步一次：

```bash
cd /root/Emboddied_Spatial_Memory
git status --short
git pull --ff-only origin review/spatial-history-development
```

若当前分支或路径与已核实状态不同，先只读核对，不用reset；本阶段同步后不再pull。新运行目录固定`/root/autodl-tmp/spatial-history/sh03-development-v2-wall-clearance`。旧v1原始目录与报告不改；新METHOD/DATA和适配源码不借旧回执认证。

SH-03/check：检查已验收SH-02原Git绑定、原模拟器未变、v1完整失败报告及原Git来源、环境freeze和新阶段来源，然后服务器执行原8项加新增4项（共12项）。写新目录的环境/启动记录和`check/`，只读旧报告及源码；不模拟16例。成功标志`SH-03 CHECK VERIFIED tests=12 exit=0`，同版成功回执复用，失败不重跑。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/development_check.py check
```

SH-03/run：只在上述成功后运行，自动核验依赖。用新墙位置前台生成原固定16对，每例保存4条原始分支和4次反序重放；预计5–10分钟。每例完成先写退出回执/摘要，再启动下一例；新版本已有完整回执只核验复用，从最早未启动例继续，不借v1的12例通过状态。完整物理审计失败仍记录并做完固定清单；运行异常停止余下案例。启动后无回执的中断现场拒绝覆盖或自动重试，须先诊断。只写本阶段新数据盘目录，不访问旧outputs或封存test。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/development_check.py run
```

成功标志`SH-03 VERIFIED cases=16 unique_branches=64 replay_branches=64 exit=0`。否则保留全部已生成数据，导出诊断，不扩大计算；2 GiB按案例边界检查，底层df不代表租赁配额。无需重复run来查询结果，独立`verify`可只读核验。

SH-03/export：通过或已保存退出回执的失败均可导出；自动核验逐例manifest、完整状态和新代码绑定，不重模拟。导出成功只表示报告生成，审计看`status`。父进程中断没有退出回执时先诊断，不补造成功证据。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/development_check.py export
```

成功标志`SH-03 EXPORTED status=passed|failed ... exit=0`。不同内容的同名报告不覆盖；固定批次完成或停止后回传这一份报告：

```bash
git add -- results/spatial_history_development_audit_v2_wall_clearance.json
git commit -m "results: export SH-03 wall-clearance revision audit"
git push origin review/spatial-history-development
```

本地pull后只核验导出摘要、逐项失败和原PNG，不本地跑测试/模拟。通过仍只证明这16种开发设置的物理与输入条件，不能宣称模型利用了空间历史；下一科学协议须本批验收和审查后交付。

### SH-02 已验收背景（历史记录，不是当前执行指令）

依据：初次EGL环境问题已解决，实际renderer为RTX 4080 SUPER、驱动595.71.05。球形推头版的两份失败报告d087389和只读接触诊断0c4335e均已回传核验，具体失败证据见LOG-105。物块与推头约2.916 s开始接触、约4.05–4.08 s最后接触，随后物块停止，推头继续移动；对应挡板布局约5.048 s出现推头–墙接触。物块全过程y≤0.214694 m，未到墙近侧面0.575 m。这足以定位原预期的持续推动没有实现，不把机器人撞墙改记成物块撞墙。

本次单一科学改动：球形推头改为宽0.30 m、前后厚0.05 m、高0.05 m的平面推头；原质量/初始中心、速度控制、物块、墙/屏、相机、求解器和通过门保留。配置文件名沿用v1接口，内容version/model已标v2，原球形配置由原提交与失败产物复现。v2在同一固定工程对上已产生预期物块撞墙/通过对照，成对终点距离约0.292881/0.319261 m；不是对任意新场景的可靠性结论。

后续评分边界：目前goal半径0.5 m仅作为查询字段，四个终点都在该半径内，不能直接把本次“受阻/通过”当成目标成功/失败或动作选择收益。SH-04仍须事先冻结与任务相符的评分、阈值和预算；当前不据此更改工程配置或重跑。

### SH-02/v2 历史固定命令

以下仅保留复现路径。SH-03已扩充METHOD/DATA，不能在新checkout重跑这些命令来借用旧回执；旧完成任务按原版本复用，当前命令仅为上面的SH-03。

用户服务器已核实仓库为 `/root/Emboddied_Spatial_Memory`，数据盘为 `/root/autodl-tmp`。复用已验收EGL的环境 `/root/autodl-tmp/spatial-history-venv-v1`；新产物 `/root/autodl-tmp/spatial-history/sh02-engineering-v2-flat-pusher`，新报告 `results/spatial_history_physics_v2_flat_pusher.json`，默认路径已随修复更新，原失败目录/报告不覆盖。当前审查checkout无任务运行、工作树干净时同步一次：

```bash
cd /root/Emboddied_Spatial_Memory
git status --short
git pull --ff-only origin review/spatial-history-physics
```

后续本阶段全部使用这次交付版本，无需步骤间pull。32项检查和全部物理/控制源码字节不因推头配置修复改写。

SH-02/setup：本机服务器环境已经安装且通过GPU EGL探测，依赖清单未变，当前可直接run，其内部会检查freeze。新服务器重建时才需要本步骤及系统EGL依赖和上下文检查：读取已提交依赖清单，用Linux Python 3.11/3.12创建隔离环境；前台显示安装输出、记录freeze和退出状态。成功且匹配的环境只核验复用，失败/中断目录拒绝重建覆盖。

```bash
python ops/spatial_history/physics_check.py setup
```

继续条件：`SH-02 ENV READY ... exit=0` 或 `SH-02 ENV VERIFIED ... exit=0`。安装失败停在当前步骤并保留日志，不启动依赖计算。

SH-02/run：自动核验已批准SH-01回执、原实现字节未变、当前源码提交干净和隔离环境，再前台启动独立Linux进程。固定1对世界、4条首次控制分支、4条反序独立重放；每分支4.9 s模拟时长、2450物理步，15帧历史。原20项回归与12项物理检查一并执行。v1实测套件11.830 s，v2需实际计时，前台逐分支报告。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/physics_check.py run
```

读边界：SH-02绑定清单、SH-01导出、隔离环境；不访问旧outputs或封存test。写边界：上述SH-02新产物目录，另由安装步骤写新环境。成功标志 `SH-02 VERIFIED tests=32 original_commit=... exit=0`；`receipt.json`保存实际时间、退出、源码/合同绑定和所有产物摘要。再次run只verify，不重做。失败或进程崩溃保留现场、返回非零并允许导出诊断；不静默换后端/场景/目录重试。

SH-02/export：成功、普通断言失败或子进程崩溃后只要父进程已写receipt均可导出。自动验证原始产物manifest，不重跑；报告包含环境/来源摘要、实际测试结果、每分支诊断、8张无损真实图像预览，以及首次分支的控制末尾位置和各接触对起止/步数/最大力。只读摘要复用已有诊断函数，省略完整逐接触段列表以控制报告大小；原trace保留。失败附日志尾部，`status=failed`不会变成物理通过。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/physics_check.py export
```

成功导出标志 `SH-02 EXPORTED status=passed|failed ... exit=0`；这个exit只表示导出完成，物理是否通过看status与报告receipt。若用户中断了父进程导致没有receipt，目录保留并需先诊断，不能用export补造运行成功。可独立使用同入口 `verify` 检查成功目录，无需重复run。

纯Git回传（只提交这份明确报告）：

```bash
git add -- results/spatial_history_physics_v2_flat_pusher.json
git commit -m "results: export SH-02 flat-pusher engineering checks"
git push origin review/spatial-history-physics
```

本地pull后只核验摘要、读失败诊断和原始PNG预览，不在本机重跑科学测试。继续条件为服务器检查通过、用户审查本批实现与画面；其后才交SH-03。若失败，先定位具体渲染/接口/物理问题，记录必要修复和新版本路径；失败样本不覆盖，不借用旧回执。训练、候选评分和大规模生成均不在本阶段。

### SH-01 已验收实现及历史命令

SH-01阅读顺序：

1. [METHOD 的当前候选与第一职责批次](METHOD.md#第一职责批次成对输入边界)和 [DATA 的字段合同](DATA.md#当前空间历史成对记录-v1d-062)。
2. [手工输入](../data/fixtures/spatial_history/manual_pair.json)：两个世界3帧，其中末2帧相同；每世界2条控制分支。2×2像素和未来坐标均手工指定。
3. [核心模块](../src/spatial_world_model/pair_contract.py)：`audit_pair → model_input`；[测试](../tests/spatial_world_model/test_pair_contract.py)验证20项合同性质。
4. [服务器入口](../ops/spatial_history/contract_check.py)：`run → verify → export` 已一次交付；不含生成/训练步骤。

已验收例子：`audit_pair` 返回 `contract_valid=true`、`early_visual_evidence_differs=true`、两个 `outcomes_differ_by_action=true`，但 `physics_and_visibility_verified=false`。同一候选的两个短历史查询完全相同；完整历史查询只因早期视觉证据不同而不同。改变私有未来标签不改变提取结果。[服务器回执](../results/spatial_history_contract_v1.json)只认证原提交的合同，不认证后续模拟器。

### SH-01 服务器固定命令

以下仅保留原提交492a7b6的运行记录/复现入口，不是当前同步指令。SH-02扩充了METHOD/DATA，原SH-01回执绑定旧文档字节；不能在新checkout上冒用旧verify认证新文档。SH-02读取不可变旧导出并重新运行原20项合同回归，使用全新来源绑定。

前提：在实际服务器仓库内、无运行中的任务使用该 checkout；先只读确认位置和工作树，不根据提示符猜路径。

```bash
pwd -P
git rev-parse --show-toplevel
git status --short
```

仅在该 checkout 空闲且工作树干净时同步一次（若已有同名本地审查分支，先检查提交，不重置它）：

```bash
git fetch origin review/spatial-history-contract
git switch --track origin/review/spatial-history-contract
git rev-parse HEAD
python --version
```

SH-01/run：Python 3.11或3.12，标准库即可；无需安装旧 Torch/NumPy 或新模拟器。预计为短检查，前台显示每项测试、结果和退出；未测速，不承诺实际时长。

```bash
python ops/spatial_history/contract_check.py run
```

成功标志：`SH-01 VERIFIED tests=20 ... exit=0`，实际测试名和计数从套件生成并写回执，不沿用旧 marker。读边界仅新模块、测试、夹具与 METHOD/DATA；写边界 `outputs/spatial-history/contract-v1/`，保存 started、日志、退出回执、输入输出和 hash。不会导入旧 CPMT、调用模拟器或读取旧 run/test。成功目录再次 run 只核验；失败或中断目录保留并拒绝静默重跑，不删除后“再试”。

SH-01/verify、export：只在 run 成功后执行；源码、合同和产物摘要须匹配。独立 verify 可用于重连，不重跑测试。export 自动包含 verify，日常无需重复调用：

```bash
python ops/spatial_history/contract_check.py export
```

导出 `results/spatial_history_contract_v1.json`，含完整服务器回执、实际测试名、源码/合同绑定、产物摘要和示例。不同已有报告拒绝覆盖；确需运行修复版本时先登记修复和新路径，再用 `--run-dir outputs/spatial-history/<明确新版本>` 及 export 的 `--report results/<明确新版本>.json` 保存新证据，不能用换目录静默重试同一失败。

继续条件：工程检查成功、用户审查 SH-01 代码与例子；其后才实现 SH-02。当前没有依赖的效果实验或下一科学模块被执行。审查批准须登记具体提交；后续改变科学语义重新审查。

## 工作区复用与历史保留

- 保留全部 `src/cpmt`、旧配置/schema/fixtures/tests/scripts/ops/results 路径与字节；新包独立，不导入旧 query、候选、教师或能量。
- 可复用来源登记、文件摘要、运行证据的工程思路；不为复用而耦合旧训练依赖。新代码用新回执，不能冒用旧 source hash。
- 第一轮没有必要搬迁旧源码或删除文件；大重构需明确解决实际依赖问题后再做。用户许可重构不等于要求清空工作区或服务器 outputs。
- ARKitScenes/ADT 已下载开发预览和 [来源清单](../data/manifests/visual_source_review.json)保留，完整接入暂缓；它们不能直接提供所需的机器人控制反事实分支。
- D-059/D-061 的32步旧计划由本计划替代为暂停状态；完整原文在 [转向前版本](https://github.com/JingzeSun/Emboddied_Spatial_Memory/blob/5f4fd115ed89876c0045d325af290d2636171e73/docs/PLAN.md)。不另建 archive/进度文件。
