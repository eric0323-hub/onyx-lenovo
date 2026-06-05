# Taxonomy Article Import Test Set

这套资料基于本地数据库中 `ys260040@gmail.com` 创建的 active taxonomy 生成：

- taxonomy: `企业知识库标签体系`
- taxonomy_id: `1`
- active_version_id: `1`
- leaf nodes: `12`
- test articles: `20`

使用方式：

1. 在标签治理的文章导入页面，只上传 `articles/` 目录下的 `.md` 文件。
2. 不要上传 `expected_labels.csv` 或 `expected_labels.json`，它们只用于人工验收。
3. 导入并完成摘要/打标后，用 `expected_labels.csv` 快速对照主标签和次标签。

覆盖设计：

- 12 个叶子标签均至少覆盖 1 篇文章。
- 部分文章故意覆盖两个相关场景，用于观察多标签推荐是否稳定。
- 文章正文没有写入预期标签路径或节点 ID，避免导入时污染打标结果。
