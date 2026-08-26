# Data

此目录不保存大型原始数据。

允许提交：

- manifest 和 split 文件；
- schema 示例；
- 无版权问题的极小测试样本；
- 数据生成与验证说明。

不要提交：RGB-D 视频、仿真场景包、第三方数据集、缓存特征或生成的大规模 episode。实际数据根目录应通过本机配置或任务专用环境变量提供。

每份数据必须记录来源、许可证、版本、hash、scene split、counterfactual group 和生成代码版本。详细要求见 `docs/04_dataset_spec.md`。
