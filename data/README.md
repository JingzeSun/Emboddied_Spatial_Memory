# 数据目录约定

本目录不提交大型数据、视频、渲染输出或自动下载的数据集。

正式数据通过 manifest 指向外部位置，并记录名称、版本、许可证、scene 清单、split 哈希、生成器版本与标注协议。小型人工 fixtures 位于 `experiments/projective_structural_latent_memory/fixtures/`。

任何 pseudo label 必须保存生成模型、版本、prompt、置信度和人工质量审计；不得称为 ground truth。当前数据路线尚未由 HC-033 确认。

