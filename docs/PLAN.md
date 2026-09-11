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
| SH-03 小规模物理审计 | SH-02 审查与工程通过；拟先16对开发世界，每世界2候选，最多64条分支，不因结果增样本 | 完整场景、快照、原始传感器、原始轨迹、失败、可视化和来源摘要。核验近期完全相同、早期相关证据可见、接触期间不可见、非布局状态一致；必要修复新版本，不覆盖 |
| SH-04 基础对照协议 | 物理审计通过；冻结训练/开发/确认划分、数据量、监督、固定候选与评分、预算和成功门 | 先交长历史/短历史、历史检索、地图加简单动力学及特权诊断的公平比较合同；没有预算和代码审查不训练 |
| SH-05 复现并定位失败 | 已审基础对照与服务器检查；保持相同数据、信息与动作选择规则 | 逐例预测/接触/动作效果、独立场景组成对统计、成本。短历史的必然失败不算新发现；强对照成功则如实收口 |
| SH-06 决定改进机制 | SH-05 确认并复现的具体失败 | 单一机制假设、对照与预算；不预先绑定 CTL，不靠扩场景/模型追正结果 |
| SH-07 独立确认与交付 | 前阶段已审方法和冻结协议 | 未见场景确认、适当现实来源验证及论文/artifact；目前均 planned，不能视为已授权 test 解封 |

SH-03 的16对是首轮开发审计建议上限；物理时长、磁盘和运行时间需 SH-02 测速后登记。SH-04 及以后不预设训练规模、模型架构或实验胜者。测试与计算在服务器由用户手动运行；本地只做源码、文档、Git 和标准库静态核查。

## 当前指针

**SH-02 已实现待审，服务器32项工程检查 pending。** 审查分支 `review/spatial-history-physics`；单对固定物理夹具，不生成SH-03开发集或训练模型。先读 [METHOD 的物理定义](METHOD.md#第二职责批次固定物理工程夹具实现服务器验证及审查-pending)、[DATA 的原始记录](DATA.md#sh-02-原始物理记录实现实际生成-pending)，再审 [场景XML](../configs/spatial_history/physics_v1.xml)、[控制配置](../configs/spatial_history/physics_v1.json)、[物理适配器](../src/spatial_world_model/physics_fixture.py)与[12项新检查](../tests/spatial_world_model/test_physics_fixture.py)。

SH-01原科学提交 `492a7b60f1bd2a996058c328bc02121e4d6fe9ce`、20项通过报告 `1e00352`已核验；用户“继续”后登记本批审查通过并快进合并main，审查登记为9044074。该批准只推进SH-02工程实现与必要测试。SH-02还没通过服务器检查，不合并科学基线、不提前堆叠数据生成/模型代码。

### SH-02 服务器固定命令

用户服务器已核实仓库为 `/root/Emboddied_Spatial_Memory`，数据盘为 `/root/autodl-tmp`。Git继续留在原处；旧 `cpmt_outputs` 约25 GB保留。新隔离环境 `/root/autodl-tmp/spatial-history-venv-v1`，新产物 `/root/autodl-tmp/spatial-history/sh02-engineering-v1`。同一checkout无任务运行、工作树干净时同步一次；不把远端仓库拼写改为Embodied：

```bash
cd /root/Emboddied_Spatial_Memory
git status --short
git fetch origin review/spatial-history-physics
git switch --track origin/review/spatial-history-physics
```

若本地已有同名分支，先检查其提交/状态，不重复创建或重置。后续本阶段全部使用这次交付版本，无需步骤间pull。

SH-02/setup：读取已提交依赖清单，用Linux Python 3.11/3.12在上述新目录创建隔离环境，只安装MuJoCo/NumPy及必要依赖；前台显示安装输出、记录完整freeze和退出状态。检查数据盘挂载存在，不将新环境放到系统盘；不修改旧Torch/NumPy。环境已成功且匹配时只核验复用；残留失败/中断目录拒绝重建覆盖。

```bash
python ops/spatial_history/physics_check.py setup
```

继续条件：`SH-02 ENV READY ... exit=0` 或 `SH-02 ENV VERIFIED ... exit=0`。安装失败停在当前步骤并保留日志，不启动依赖计算。

SH-02/run：自动核验已批准SH-01回执、原实现字节未变、当前源码提交干净和隔离环境，再前台启动独立Linux进程。固定1对世界、4条首次控制分支、4条反序独立重放；每分支4.9 s模拟时长、2450物理步，15帧历史。原20项回归与12项新检查一并执行。真实运行时间尚未测；这是小规模工程检查，默认前台并逐分支报告，不预先承诺速度。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/physics_check.py run
```

读边界：SH-02绑定清单、SH-01导出、隔离环境；不访问旧outputs或封存test。写边界：上述SH-02新产物目录，另由安装步骤写新环境。成功标志 `SH-02 VERIFIED tests=32 original_commit=... exit=0`；`receipt.json`保存实际时间、退出、源码/合同绑定和所有产物摘要。再次run只verify，不重做。失败或进程崩溃保留现场、返回非零并允许导出诊断；不静默换后端/场景/目录重试。

SH-02/export：成功、普通断言失败或子进程崩溃后只要父进程已写receipt均可导出。自动验证原始产物manifest，不重跑；报告包含环境/来源摘要、实际测试结果、每分支诊断和8张无损真实图像预览。失败报告附日志尾部，`status=failed`不会变成物理通过。

```bash
/root/autodl-tmp/spatial-history-venv-v1/bin/python ops/spatial_history/physics_check.py export
```

成功导出标志 `SH-02 EXPORTED status=passed|failed ... exit=0`；这个exit只表示导出完成，物理是否通过看status与报告receipt。若用户中断了父进程导致没有receipt，目录保留并需先诊断，不能用export补造运行成功。可独立使用同入口 `verify` 检查成功目录，无需重复run。

纯Git回传（只提交这份明确报告）：

```bash
git add -- results/spatial_history_physics_v1.json
git commit -m "results: export SH-02 physics engineering checks"
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
