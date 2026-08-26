# Tests

优先测试研究结论依赖的基础逻辑：

1. `T_world_camera` 方向与 SE(3) round-trip；
2. pure rotation homography 和 depth reprojection；
3. ego-motion flow 在静态场景中的 residual 接近零；
4. out-of-FOV、occluded 和 absent 的区别；
5. region split/merge association；
6. transient slot decay 与 persistent slot 保持；
7. persistent change 的确认和替换；
8. counterfactual metric 的 clean/disturbed 对齐；
9. episode 和 memory slot schema validation。

加入真实模型前先用可解析的合成几何单元测试，避免用神经网络误差掩盖坐标错误。
