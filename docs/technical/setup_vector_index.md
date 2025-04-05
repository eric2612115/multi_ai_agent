# 为MongoDB Atlas设置向量搜索索引

MongoDB Atlas上的向量索引能够帮助您进行高效的相似性搜索，这对于知识图谱和语义搜索至关重要。以下是设置步骤：

## 1. 访问您的MongoDB Atlas集群

登录MongoDB Atlas并访问您的集群。

## 2. 创建向量索引

有两种方法可以创建向量索引：

### 方法1：通过Atlas UI创建

1. 在集群页面，点击"Collections"按钮
2. 选择`research_db`数据库和`nodes`集合
3. 点击"Search"标签
4. 点击"Create Search Index"
5. 选择"Visual Editor"
6. 索引名称输入`nodes_vector_index`（这是应用中使用的默认名称）
7. 点击"Add Field"
8. 字段名称选择`embedding`
9. 类型选择`vector`
10. 维度设置为`768`（这是应用中使用的默认嵌入维度）
11. 距离度量选择`cosine`
12. 点击"Create Index"

### 方法2：通过MongoDB Shell创建

或者，您可以通过MongoDB Shell运行以下命令：

```javascript
db.nodes.createIndex(
  { embedding: "vector" },
  { 
    name: "nodes_vector_index",
    dimension: 768,
    metric: "cosine"
  }
)
```

## 3. 验证索引创建

1. 等待索引构建完成（这可能需要几分钟时间）
2. 在Atlas UI中的"Search"标签下，您应该能看到已创建的索引

## 4. 测试向量搜索

您可以通过在MongoDB Atlas中运行以下查询来测试向量搜索：

```javascript
db.nodes.aggregate([
  {
    $search: {
      "index": "nodes_vector_index",
      "vectorSearch": {
        "queryVector": [0.1, 0.2, /* ... 剩余元素 ... */],
        "path": "embedding",
        "numCandidates": 100,
        "limit": 10
      }
    }
  }
])
```

请记得替换`queryVector`中的值为实际的查询向量。

## 注意事项

- 确保您的MongoDB Atlas集群具有足够的资源来支持向量搜索
- 免费M0集群可能对向量搜索有限制，如果您计划大规模使用，建议升级到付费集群
- 确保应用中的配置项`enable_vector_search`设置为`true`
