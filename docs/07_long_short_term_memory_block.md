# Block 07 — 长短期视觉空间记忆

> 版本：v0.3（当前仅冻结 Q1，已纳入动态行人与抗噪约束）  
> 状态：Q1 已由用户确认；Q2–Q6 等待用户逐项回答  
> 定位：这是整个具身智能项目中的一个方法模块，不是整个项目计划

## 1. 本模块在整个项目中的位置

本模块只解决具身智能体的地点级长短期空间记忆问题：

- 从连续观察、位姿和动作中判断“我现在处于哪个地方”；
- 判断是仍在原地点、重返旧地点，还是进入了一个新地点；
- 分地点保存结构、视觉特征、区位、包含物、入口和出口；
- 用动作、转弯和门口等证据保存地点之间的转换关系；
- 将行人、移动物体和临时障碍作为独立的动态/瞬态状态，不能覆盖其后方的墙、门和走廊结构；
- 显式传播位姿、深度、光流、结构解析和关联的不确定性，阻止噪声直接污染长期地点记忆；
- 在防污染的同时识别椅子移动、门状态变化等真实持久变化，不能依靠永久冻结记忆获得表面稳定；
- 支持“前一个走廊”“两个转弯之前的房间”“刚才那个地方有什么”等相对地点查询。

它不是整个具身智能系统。感知、局部几何、世界模型、目标解析、任务规划、动作控制、数据集和评测仍属于整个项目中的其他模块；待 Q2–Q6 明确后，再把本模块与这些模块组合成完整项目计划。

## 2. Q1：已确认的需求

### 2.1 用户原意记录

长期记忆应保存不同地点的不同特征、区位信息、空间结构以及其中包含的内容。智能体进入不同地点时，需要建立清楚的地点认知，而不是把连续画面混成一段视频。

以 N 字形路线为例：路线中存在两个走廊。智能体应结合自身的动作记录、转弯次数和观察到的结构变化，先判断已经从第一个走廊进入了不同的第二个走廊，再开始为第二个走廊建立独立记录。同时，长期记忆必须保留“我已经拐了两个弯”、第一个走廊的结构是什么、其中有什么。之后若任务要求寻找“前一个走廊里的某个东西”，系统应能迅速解析指代并检索，而不是重新扫描整段历史视频。

### 2.2 冻结后的技术结论

长期记忆的主索引应是稳定的地点实体 `Place`，而不是孤立图像、所有历史 token 的堆积，或只有对象槽位的表格。

每个地点需要记录：

- 地点类型与局部坐标系；
- 结构特征和视觉特征；
- 世界中的区位及其不确定性；
- 地点内包含的对象、表面和可交互实体；
- 入口、出口、门口和相邻地点；
- 首次访问、最近访问、访问次数和证据来源。

地点之间的关系必须由动作、转弯、相对位姿、入口/出口等证据支持。实际走过的地点序列还要单独保存为路线经历，才能正确回答“前一个”“两个转弯之前”等带有经历顺序的查询。

### 2.3 Q1 补充确认：短期记忆也必须记录结构

短期记忆的作用不只是判断“有没有进入新地方”。它必须利用每一帧的透视结构，持续记录当前局部环境：墙面、地面、天花板、门口、转角、走廊延伸、近—中—远分区、遮挡关系以及这些结构随机器人动作发生的视角变化。

这些透视结构先作为短期观测坐标中的工作记忆，经跨帧自运动对齐形成短期滚动结构图；稳定且一致的部分再巩固到 Local Structural Chart、Place 和长期 world slot。地点切换判断是短期结构记忆的一个输出，而不是它的全部定义。

## 3. 长期记忆的核心表示

长期记忆暂定由三部分组成：

`M_long = G_place + S_content + H_route`

- `G_place = (V_place, E_transition)`：地点拓扑图；
- `S_content`：锚定在地点内的对象、表面、入口和其他内容；
- `H_route`：智能体实际经历过的有序路线记录。

### 3.1 地点节点 PlaceNode

```text
PlaceNode = {
  place_id,
  place_type,
  local_coordinate_frame,
  world_pose_distribution,
  structural_signature,
  visual_signature,
  semantic_summary,
  contained_entity_ids,
  entry_portal_ids,
  exit_portal_ids,
  neighbor_place_ids,
  first_visited,
  last_visited,
  visit_count,
  confidence,
  lifecycle,
  provenance
}
```

它应能回答：这是什么地方、它在哪里、结构是什么、里面有什么、从哪里进入和出去、现在是否重返此处。

### 3.2 地点转换 TransitionEdge

```text
TransitionEdge = {
  transition_id,
  from_place_id,
  to_place_id,
  transition_type,
  action_summary,
  turn_signature,
  relative_transform,
  traveled_distance,
  entry_portal_id,
  exit_portal_id,
  confidence,
  supporting_frame_ids,
  supporting_action_ids,
  traversal_count
}
```

它应能回答：智能体如何从地点 A 到达地点 B、执行了什么动作和转弯、两地的相对关系是什么、结论由哪些观测支持。

### 3.3 地点内容 PlaceContent

```text
PlaceContent = {
  entity_id,
  anchor_place_id,
  entity_type,
  local_geometry,
  appearance_prototypes,
  semantic_distribution,
  relation_to_place,
  visibility_history,
  persistence_state,
  provenance
}
```

对象必须锚定到地点，而不只是出现在某一帧。例如：“灭火器位于 corridor_01，靠近出口 portal_03”。对象状态可以改变，但对象的变化不应自动造成地点身份改变。

### 3.4 路线经历 TraversalRecord

```text
TraversalRecord = {
  traversal_id,
  ordered_place_ids,
  ordered_transition_ids,
  action_trace_ref,
  start_time,
  end_time,
  task_context,
  confidence
}
```

地点图描述世界如何连通；路线经历描述这一次实际按什么顺序走过。二者不能合并，否则无法可靠解释“前一个地点”和“上次经过的地点”。

## 4. 短期记忆的职责：持续记录透视结构

短期记忆首先是当前局部空间的在线结构工作区，其次才承担新地点判断。它不能只保存“是否进入新地方”的分类证据，也不能退化为最近若干帧的队列。

每一帧都要利用消失点、墙面/地面/天花板边界、走廊结构线、深度以及近—中—远关系，形成带空间含义的透视观测：

```text
PerspectiveObservation_t = {
  frame_id,
  camera_pose_and_uncertainty,
  vanishing_point_hypotheses,
  dominant_directions,
  structural_boundaries,
  observation_regions,
  region_relations,
  visible_portal_candidates,
  occlusion_relations,
  provenance
}

ObservationRegion = {
  region_id,
  structural_role,       # left_wall_near / floor_far / corridor_end / ...
  image_mask_or_polygon,
  depth_statistics,
  camera_geometry,
  latent,
  semantic_distribution,
  visibility,
  dynamic_probability,
  uncertainty
}
```

这些逐帧透视结构还要通过深度、位姿和动作进行时序对齐，形成一个滚动的短期结构图。但它只是完整短期记忆的一个子状态；完整短期记忆由四个工作区组成：

```text
ShortTermMemory = {
  structural_workspace: {
    perspective_observation_window,
    temporal_region_correspondences,
    active_structural_elements,
    active_chart_hypotheses,
    local_surface_and_portal_graph
  },
  dynamic_workspace: {
    dynamic_track_bank,
    transient_occupancy,
    occlusion_relations,
    motion_and_stationarity_history
  },
  uncertainty_ledger: {
    pose_depth_flow_uncertainty,
    measurement_and_structure_confidence,
    association_hypotheses,
    conflict_evidence,
    quarantined_writes
  },
  place_route_workspace: {
    recent_pose_and_action_trace,
    accumulated_turn_events,
    current_place_belief,
    place_transition_hypotheses
  }
}
```

其中应保存的不只是当前可见结构，还包括刚刚离开视野但仍可由自运动预测的墙面、门口、转角和通道延伸；短时遮挡只改变可见性，不立即删除结构。

短期结构记忆每一时刻至少执行：

1. 从当前图像解析透视结构区域及区域间关系；
2. 用位姿、深度和动作把上一时刻结构投影到当前视角；
3. 建立跨帧 region correspondence，累积墙面、地面、门口和转角证据；
4. 同时维护旧 Chart 与候选新 Chart，转弯时允许二者混合可见；
5. 对出视野、遮挡和动态占据分别维护状态；
6. 产出当前局部结构记录，并据此更新地点身份和地点转换假设。

因此它既能回答“当前和刚才看到了什么结构”，也能回答：

- 左墙、右墙、地面、门口和走廊尽头在连续视角中如何变化；
- 某个结构是由于相机运动离开视野，还是被动态物体遮挡；
- 转弯期间哪些区域仍属于旧走廊，哪些区域开始支持候选新走廊；
- 最近执行了什么动作、拐了几次弯；
- 是否跨过门口、转角或结构边界；
- 当前相似画面属于旧地点，还是视觉相似的新地点；
- 是否已有足够证据建立新的 Chart 和 Place。

这里还要区分两个维度：短期/长期描述保存时间和确认程度，静态/动态描述世界实体的性质。短期记忆既可以包含尚未确认的静态墙面，也可以包含行人等动态实体；二者不能等同。

### 4.1 行人、动态物体与遮挡

行人不能被简单当成要删除的视觉噪声。对当前避障和动作决策而言，行人的位置与运动非常重要；但对长期静态结构而言，行人通常只是一个短时动态实体或遮挡者。因此短期记忆应为行人建立独立轨迹：

```text
DynamicTrack = {
  track_id,
  instance_and_semantic_distribution,
  camera_or_world_geometry_distribution,
  velocity_distribution,
  motion_and_stationarity_history,
  occupied_regions,
  occludes_static_slot_ids,
  dynamic_probability,
  persistence_probability,
  first_seen,
  last_seen,
  ttl_or_decay_state,
  confidence,
  provenance
}
```

动态概率不能只由原始 optical flow 决定。机器人自身转弯也会产生大光流，而静止不动的行人又可能产生很小的 residual flow。应先利用 pose、depth 和相机内参预测静态世界的自运动光流：

```text
f_residual = f_observed - f_ego(pose, depth, K)

P_dynamic = Fuse(
  residual_motion,
  semantic_or_instance_evidence,
  depth_order_and_occlusion,
  multi_frame_consistency,
  track_history,
  estimator_uncertainty
)
```

其中静止行人仍可由人物语义、先前运动轨迹、位于背景结构之前的深度顺序、进入/离开事件以及实例一致性识别为动态或未决实体，不能因为 `f_residual ≈ 0` 就写入静态墙面。

当行人遮挡一扇门时，短期记忆应同时保持：

```text
Static structure: door_07, visibility = occluded
Dynamic state:    pedestrian_03, occludes = [door_07]
```

此时“没有看到门”不是门消失的反证，门的长期 latent、几何和语义都不能被行人覆盖。行人离开后，应将重新出现的门关联回 `door_07`，而不是创建新门。动态 occupancy 随时间衰减，但证据和轨迹保留到足以完成遮挡恢复与短期规划。

若任务确实要求长期记住某个具体人物，应把其身份与状态放入独立的可持久对象记忆，而不是混入建筑静态结构；这不是当前 MVP 自动假定的能力。

### 4.2 多源噪声与长期写入防污染

“防噪声”不是在输入端做一次滤波，而是让每条观测证据携带来源和不确定性，并控制它能否、以及以多大权重进入长期记忆。至少需要处理：

- RGB 模糊、曝光变化、反光和 DINO latent 抖动；
- 深度噪声、前景/背景边界泄漏和尺度误差；
- pose/odometry 的高斯噪声、漂移和突跳；
- optical-flow 估计误差；
- line/plane/VP 与语义/实例检测抖动；
- region split/merge 和错误 frame-to-world association。

短期不确定性账本至少保存：

```text
UncertaintyLedger = {
  pose_covariance_and_confidence,
  depth_uncertainty_by_region,
  flow_uncertainty_by_region,
  structure_detection_confidence,
  semantic_and_track_confidence,
  top_k_association_hypotheses,
  expected_visibility,
  support_evidence,
  conflict_evidence,
  outlier_flags,
  provenance
}
```

对 observation region `i` 写入静态长期 slot `j` 的权重应是软门控：

```text
alpha_static(i, j) =
    C_assoc
  · C_visibility
  · (1 - P_dynamic)
  · C_pose
  · C_depth
  · C_structure
  · C_measurement
  · C_temporal
```

低可信证据不等于完全丢弃。它应留在短期缓冲区、保留多个关联假设或进入 `quarantined_writes`，等待后续帧、回看或重定位验证；只有证据一致后才提交长期更新。每次写入都保存 frame、region、关联置信度、更新权重和传感器置信度，以支持审计、降权与撤销。

不同故障应采用不同策略：

- **pose 突跳**：继续记录相机/局部坐标中的透视结构，但降低 world association 与 Place/Chart 创建权重；重定位后用保留窗口重新对齐，不能批量复制地点和 slot。
- **深度边界错误**：使用区域内稳健深度统计、前景/背景分层与 covariance，避免把行人深度融合进后方墙面。
- **光流噪声**：将 flow estimator uncertainty 纳入动态融合，不能把转弯产生的 raw flow 当成行人运动。
- **检测抖动或相似纹理**：维护 top-k 关联和多帧确认，证据不足时保持 `Ambiguous`。
- **motion blur 或快速转弯**：降低 measurement/pose confidence，而不是全局停止记录；可靠区域仍可更新短期结构。

防污染也不能变成“永不更新”。当原本预计可见的结构在多个可靠视角中持续产生一致冲突，且动态/遮挡解释不足时，长期 slot 应从 `persistent` 进入 `changed`，再经确认成为 replacement 或 retired。这样才能区分：

```text
行人经过 / 临时遮挡  -> transient，不改写静态结构
椅子永久移动 / 门状态持久改变 -> changed，确认后更新长期记忆
```

### 4.3 当前地点信念

当前地点不应过早坍缩为单一 ID，而应保留带置信度的信念分布，例如：

```text
P(corridor_01) = 0.18
P(corridor_02) = 0.07
P(new_place)   = 0.75
```

只有多帧结构、动作和位姿证据一致时，才把短期假设巩固进长期记忆。

## 5. 从短期证据到长期地点的确认流程

```text
RGB + depth + DINO + structure cues
          └─> 逐帧透视区域 ──自运动对齐──> Structural Workspace

observed flow + pose + depth + K
          └─> ego-flow residual ─┐
semantics + instance + occlusion + track history
          └──────────────────────┴─> Dynamic Workspace

pose/depth/flow/detector/association confidence
          └────────────────────────> Uncertainty Ledger

Structural Workspace + Dynamic Workspace + Uncertainty Ledger + action trace
          ↓
区分静态结构、动态占据、遮挡、出视野、传感器异常和未决冲突
          ↓
带置信度的 region-to-slot / region-to-chart association
          ↓
soft write gate + candidate quarantine + multi-frame confirmation
          ├─> 持续更新短期结构、行人轨迹与地点信念
          ├─> 更新已有长期 slot / Chart / Place
          ├─> 创建候选 Chart / Place / transition
          └─> Existing Place / New Place / Ambiguous
```

无论地点判断结果是什么，短期结构图都要继续更新；地点分类不能替代透视结构记录。若结果为 `Ambiguous`，结构和关联证据继续留在短期记忆中，并通过继续前进、回看入口或主动转头等动作消除歧义；系统不能仅因单帧视觉差异就批量创建新地点。

候选地点的匹配分数暂写为：

```text
s(P_i) =
    w_a · appearance_similarity
  + w_g · structural_similarity
  + w_m · motion_consistency
  + w_t · topology_consistency
  + w_p · portal_consistency
  + w_h · route_history_consistency
  - w_u · registration_uncertainty
```

地点匹配只能使用经过动态分离和置信度加权的结构证据；行人外观和临时 occupancy 不能成为走廊身份。动作一致性、路线历史和 registration uncertainty 也不是辅助日志，而是区分视觉相似地点并防止噪声误建地点的核心证据。

## 6. N 字形转弯案例

### 6.1 路线表示

```text
C1：第一个走廊
  └─ T1：第一次转弯
       └─ K：连接段或短通道
            └─ T2：第二次转弯
                 └─ C2：第二个走廊
```

即使 `C1` 与 `C2` 在纹理、墙面和宽度上高度相似，也不能直接合并。系统需要联合以下证据判断已经进入第二个走廊：

- 已连续执行两个有方向和幅度记录的转弯；
- 位姿与动作积分表明智能体已离开 `C1` 的局部空间范围；
- 中间观察到了连接段、门口或其他转换结构；
- `C2` 的进入方向与 `C1` 的离开方向构成新的相对几何关系；
- 当前局部结构在位姿不确定性范围内无法合理配准回 `C1`；
- 已有地点拓扑无法支持“智能体仍在 C1”这一解释。

证据充足后，长期记忆应形成：

```text
PlaceNode(C1) != PlaceNode(C2)
TransitionEdge(C1 -> K, T1)
TransitionEdge(K  -> C2, T2)
TraversalRecord([C1, K, C2])
```

进入 `C2` 后，系统开始记录 `C2` 自己的局部坐标、结构、视觉特征、对象、入口和出口，同时继续保留 `C1` 的结构及内容，不以新地点覆盖旧地点。

### 6.2 查询“前一个走廊里的某个东西”

```text
当前地点 C2
   ↓
沿当前 TraversalRecord 反向查找
   ↓
跳过非 corridor 类型的连接段 K
   ↓
解析“前一个走廊” = C1
   ↓
只检索锚定在 C1 的 PlaceContent
   ↓
返回对象、历史位置、证据与返回路线
```

若对象可能已经移动，返回结果必须标记“历史上在 C1 被观察到”以及证据时间，必要时引导智能体返回 C1 重新验证。查询过程不需要让当前策略对全部历史帧做全局 attention。

### 6.3 N 字转弯中同时出现行人与位姿噪声

假设机器人第二次转弯时，一名行人正好经过并遮挡 `C2` 的入口，且快速转动造成 pose 与 depth 置信度下降。系统不能在“停止一切更新”和“立即创建 C2”之间二选一，而应分层处理：

1. 透视结构工作区继续记录仍可靠的旧走廊墙面、转角、地面边界和新出现区域；
2. 行人进入 `DynamicTrack`，其深度层遮挡的入口和墙面标记为 `occluded`，不能被人物 latent 覆盖；
3. 不确定性账本降低被遮挡区域、深度边界和 world registration 的置信度；
4. 两次转弯与动作轨迹仍保留，但 `C2` 暂时维持 candidate/ambiguous，不因低可信配准立即创建；
5. 行人离开、相机稳定后，重新观察到的结构与短期候选对齐，再确认 `C2` 及 `K -> C2`；
6. 若后续证据不支持候选，则撤销或降权该候选，不能让一次噪声产生永久错误地点。

这个联合案例是本项目的必要测试，而不是分别测试“转弯”“行人”和“噪声”后就默认三者组合仍然成立。

## 7. 地点身份、地点内容与路线经历必须分离

需要明确避免以下错误：

- 两个走廊视觉相似，就把它们错误合并为同一个地点；
- 仅仅原地转动摄像头，就创建了一个新地点；
- 某个物体被移动，就改变了整个地点的身份；
- 把世界的拓扑图等同于某一次实际走过的路线；
- 把全部地点内容持续塞进当前策略的注意力上下文。

正确关系是：

- `Place` 表示相对稳定的地点身份；
- `PlaceContent` 表示该地点包含或曾包含什么；
- `TransitionEdge` 表示地点间如何转换；
- `TraversalRecord` 表示这一次实际走过的顺序；
- `ShortTermMemory` 同时保存近期结构、动态轨迹、不确定性账本以及尚未确认的地点/路线假设。

## 8. 与 Local Structural Chart 的关系

透视结构、动态证据、不确定性、`Local Structural Chart` 与 `Place` 共同构成连续巩固链条：

```text
PerspectiveObservation + ego-flow residual + semantics + sensor confidence
        ↓
ShortTermMemory
├─ Structural Workspace ──动态分离/跨帧对齐──┐
├─ Dynamic Workspace ─────遮挡与占据解释─────┤
├─ Uncertainty Ledger ─────soft write gate────┤
└─ Place/Route Workspace ──动作与拓扑约束────┘
                                             ↓ 多帧确认
                     Persistent World Slots + Local Structural Charts
                                             ↓ 地点组织与关系绑定
                                  PlaceNode + Transition + Traversal
```

透视结构负责组织当前帧看到什么；短期记忆负责记录结构如何延续、行人如何占据或遮挡、传感器证据是否可靠，以及动作和地点假设；Chart 是被多帧确认后的持久局部几何；`Place` 是认知、检索和任务指代的单位。

透视坐标会随相机变化，所以不能把某一帧的消失点或 perspective grid 直接当作长期坐标。但这不意味着透视结构只做一次性特征提取：它必须先在短期记忆中跨帧累积，再通过世界/局部坐标对齐巩固为 Chart。

`Place` 与 Chart 不必一一对应。

一个较大的地点可以由多个 chart 覆盖；位于门口或转角处的 chart 也可能同时支持相邻两个地点的转换判断：

```text
PlaceNode
├─ chart_ids
├─ contained_entity_ids
├─ portal_ids
└─ transition_edges
```

因此，已有的透视区域和局部结构表示都不需要被废弃：前者是短期记忆的观测与工作单元，后者是地点记忆的持久几何底座。

## 9. 最小接口

```text
parse_perspective_structure(rgb, depth, camera_intrinsics)
    -> PerspectiveObservation

update_short_term_structure(
    perspective_observation,
    pose,
    action,
    previous_short_term_state
) -> ShortTermStructuralUpdate

estimate_ego_motion_flow(depth, pose_t, pose_t1, camera_intrinsics)
    -> EgoFlow + FlowUncertainty

update_dynamic_tracks(
    observed_flow,
    ego_flow,
    semantic_instances,
    depth_occlusion,
    track_history,
    estimator_uncertainty
) -> DynamicTransientUpdate

assess_observation_uncertainty(
    pose,
    depth,
    flow,
    structural_detection,
    association_hypotheses
) -> UncertaintyLedgerUpdate

propose_memory_write(
    observation_region,
    target_slot,
    dynamic_state,
    uncertainty_state
) -> Commit | Quarantine | Reject

observe(rgb, depth, pose, action)
    -> PerspectiveObservation
     + ShortTermStructuralUpdate
     + DynamicTransientUpdate
     + UncertaintyLedgerUpdate

estimate_current_place(short_term_state, place_graph)
    -> PlaceBelief

confirm_place_transition(place_belief, accumulated_evidence)
    -> ExistingPlace | NewPlace | Ambiguous

write_place_observation(place_id, observation, evidence)
    -> MemoryUpdateTrace

record_transition(from_place_id, to_place_id, action_trace, evidence)
    -> TransitionEdge

resolve_place_reference(
    expression="previous corridor",
    current_place_id,
    traversal_id
) -> PlaceCandidates

retrieve_place_contents(place_id, entity_query)
    -> ContentEvidence[]
```

所有接口都必须返回置信度和证据来源，不能只返回一个不可审计的确定答案。

## 10. 本模块必须通过的最小测试

### 10.1 短期透视结构记录测试

- 机器人直行时，左/右墙的近—中—远区域虽然改变图像位置，仍能跨帧关联到同一局部结构；
- 原地旋转时，旧结构按自运动预测逐渐离开视野，新结构逐渐进入，不因 perspective grid 改变而丢失记录；
- 转弯时允许旧 Chart 与候选新 Chart 同时获得证据，而不是在某一帧硬切换；
- 行人短时遮挡门口时，门口保留为不可见/被遮挡结构，行人单独进入动态短期状态；
- 新墙面或新走廊仅在多帧结构、深度和位姿一致后巩固，单帧异常停留在候选状态；
- 在尚未确认是否进入新地点时，仍能查询最近窗口内累计的墙面、门口、转角和通道关系。

### 10.2 行人、动态物体与真实变化测试

- 移动行人完全遮挡门口：门 slot 不被人物 latent、语义或深度覆盖；
- 行人停止不动：即使 residual flow 接近零，仍由语义、遮挡层和轨迹历史维持 dynamic/unknown，而不是写入墙面；
- 机器人转弯造成大 raw flow：ego-motion compensation 后，静态墙面不被误判为动态；
- 行人离开：dynamic occupancy 衰减，门口重现后关联回原 slot，不重复创建；
- 临时推车经过与椅子永久移动：前者进入 transient 并衰减，后者经多视角确认进入 changed/replacement；
- 转弯与行人同时发生：可靠结构 region 继续更新，遮挡 region 保持未知，不使用全局 freeze。

### 10.3 传感器、感知与关联噪声测试

- pose 高斯噪声逐级增加：地点/slot 指标平滑退化，置信度与实际错误率校准；
- pose 突跳：低可信写入被隔离，重定位后从短期窗口恢复，不批量复制 Place、Chart 或 slot；
- depth 前景/背景边界泄漏：人物深度不融合进后方墙面几何；
- optical-flow 噪声：不能单独触发静态结构删除或动态认定；
- motion blur、曝光变化和 latent 抖动：降低测量权重，不能用一次异常覆盖长期原型；
- region split/merge 与相似门：保留多关联假设，错误关联可以降权或撤销；
- 持续可靠冲突：不能永远隔离，必须在确认延迟后更新真实持久变化。

### 10.4 地点身份测试

- 在同一条直走廊内连续前进和视角变化：仍为同一 `Place`；
- 原地旋转一周：不创建新地点；
- 穿过明确门口进入房间：创建新地点和转换边；
- 经过 N 字两次转弯进入相似走廊：创建 `C2`，不能错误合并到 `C1`；
- 沿原路返回 `C1`：重识别为旧地点，不能创建 `C3`。

### 10.5 地点内容与相对查询测试

- 离开地点后，仍可检索其中观察过的对象和结构；
- “前一个地点”解析为当前 traversal 中的直接前驱；
- “前一个走廊”能跳过非走廊类型的连接段；
- “两个转弯之前”能通过转换边和转弯事件定位；
- 对象被移动时，地点身份保持不变，对象状态和时间证据被更新。

### 10.6 地点与查询不确定性测试

- 位姿跳变时先输出 `Ambiguous`，不得批量创建新地点；
- 两地点视觉高度相似且证据不足时触发主动复核；
- 视觉相似但拓扑或运动不可达时拒绝错误合并；
- 缺失路线经历时，不为“前一个”类查询伪造确定答案。

## 11. 本记忆模块的评测指标

项目主鲁棒性指标：

- static memory drift：clean 与 disturbed 配对轨迹的静态 latent、geometry、semantic 差异；
- dynamic contamination rate：行人或临时物体错误覆盖、改类、替换或退休静态 slot 的比例；
- static memory retention：转弯或遮挡后仍可正确检索和投影的历史静态结构比例；
- reappearance consistency：`visible -> occluded/out-of-view -> visible` 后的 IDF1、关联准确率与重复 slot 率；
- transient-vs-persistent change F1、确认延迟和错误冻结率；
- pose/depth/flow noise sweep 下的性能—噪声曲线与 confidence calibration；
- quarantined-write precision/recall、错误提交率和恢复成功率。

地点建模指标：

- current-place recognition accuracy；
- new-place precision / recall；
- duplicate-place rate；
- incorrect-merge rate；
- re-entry IDF1；
- transition-edge precision / recall；
- turn-sequence accuracy；
- route reconstruction accuracy。

任务查询指标：

- relative-place reference accuracy；
- place-conditioned entity retrieval recall / precision；
- retrieval latency 与长期记忆规模的关系；
- 位姿和动作噪声下的置信度校准。

N 字路线必须单独报告：

- `C1/C2` 区分正确率；
- 两次转弯事件保留率；
- “前一个走廊”解析正确率；
- 在 `C2` 中检索 `C1` 内容的正确率；
- 返回 `C1` 的路线规划正确率。

## 12. Q2–Q6：等待用户回答，不在本版擅自冻结

### Q2：何时读取长期记忆？

是每一步都读取，还是只在地点切换、目标需要、预测冲突或策略不确定时读取？

### Q3：一次读取多少、读取什么层级？

读取地点摘要、对象、路线、局部几何还是时间证据？采用 top-k、固定预算还是自适应预算？

### Q4：长期记忆如何影响当前决策？

在高层规划、低层视觉 token、独立记忆分支还是门控残差中融合？如何避免无关历史通过 attention 干扰当前目标？

### Q5：记忆如何更新、遗忘和处理变化？

如何处理结构变化、对象移动、遮挡、消失、重复访问、冲突证据和过期内容？

项目已经冻结的底线是：动态分离、soft confidence update、provenance 和多时间尺度 lifecycle 必须存在；Q5 待回答的是具体的确认窗口、衰减方式、冲突阈值、遗忘策略和长期变化政策，而不是是否需要这些底线机制。

### Q6：DINO-WM 在最终技术栈中的角色是什么？

作为视觉编码器、短期动态预测器、基线、教师模型，还是被其他世界模型替换？

以上五项只保留为待决问题。用户逐项回答后，再把答案写成设计约束、接口、实验和每日任务。

## 13. 当前冻结结论

1. 长期记忆以 `Place` 为主索引，而不是以孤立帧或全量历史 token 为主索引。
2. 每个地点保存结构、视觉、区位、内容、入口、出口和证据。
3. 地点转换由动作、转弯、相对位姿和 portal 共同支持。
4. `TraversalRecord` 单独保存实际走过的有序路线。
5. 短期记忆由透视结构工作图、动态/瞬态轨迹库、不确定性账本和地点/路线工作状态组成；地点判断只是其输出之一。
6. 行人以独立 `DynamicTrack` 与 transient occupancy 保存；其遮挡只改变背景结构的 visibility，不能覆盖墙、门或走廊 slot。
7. 动态判断必须使用 ego-motion compensated residual，并融合语义、实例、深度遮挡、轨迹历史和估计器不确定性；不能只看 raw flow。
8. 位姿、深度、光流、结构检测和关联噪声必须进入 soft write gate；低可信写入先隔离、多帧确认并保存 provenance。
9. 防污染不能依赖永久冻结；持续可靠冲突必须通过 `persistent -> changed -> replacement/retired` 响应真实变化。
10. N 字路线中第二个走廊必须被识别为独立地点，同时保留第一个走廊；行人与噪声同时出现时允许延迟确认，但不能丢掉短期结构。
11. “前一个走廊”先沿 traversal 解析地点，再只检索该地点的内容。
12. Q2–Q6 尚未冻结；它们完成后，本模块才并入整个项目的完整路线图。
