# HC-003 Future Horizon and Leakage

- 状态：M1 选项已由 D-031 冻结；M2 表征相关阈值仍 deferred
- 最早激活：M1；当前正在冻结合同
- 建议默认：先比较 H={1,3,5}，validation 选一个主 horizon；online export 物理删除所有未来、oracle 和 hidden-state 字段。

已确认（D-026，2026-09-05）：

- 主设置保留即时在线判断：时刻 t 不读取真实 t+1 图像，不固定等待下一帧再提交；
- 新观测真实到来后可作新判断并修订记忆，保留原先判断时间；
- 即时判断可输出 QUARANTINE，证据不足时继续保存暂定认知；
- 未来只用于 hindsight 监督和相应评估，不作为在线学生当时的输入；
- 延迟一帧对照暂不纳入当前实验范围。

白话：现在按已经看见的东西判断，下一眼看清后可以改；“现在先拿不准”也是合法决定。这里没有承诺模型能预知无法由当前信息区分的真相。

仍需冻结：

- future pose 来自已执行轨迹还是计划动作；
- variable horizon 如何 mask；
- episode 尾部如何处理；
- visibility/visible-empty 如何进入评分；
- 预计算 feature 是否严格只用对应时刻及以前。

M1 v1 冻结选择（D-030/D-031）：future pose 只来自实际已执行轨迹；主 H=3，H=1/5 为报告型消融；只评分真实存在且 pose/visibility 有效的步；尾部至少有一步 future 则保留并 mask，零 future 只作 online 诊断；visible-positive 与可靠 visible-empty 计分，occluded/unobserved mask；online/future feature cache 物理分离。完整白话与反例见 [M1 hard-condition](../../experiments/counterfactual_transaction_learning/HARD_CONDITION_EXPERIMENT.md)。

研究者选择：M1 v1 已确认；test 仍须等待实现验证，不因本表确认自动解封。

日期 / 理由 / 影响：2026-09-05；D-026 确认在线时间边界时尚未实现训练；后续 D-027 已完成开发实现，当前记录见 [EXECUTE.md](../../EXECUTE.md)。本表其余正式选项仍待确认，开发 H=3 不替代正式冻结。
