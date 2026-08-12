# ClientController 接口文档

**路径前缀**: `/client`

**说明**: 客户端查询接口，带权限过滤，仅提供给前端用户查询使用，不做增删改操作。

---

## 1. 查询当前用户可见的技能列表

```
GET /client/skills/list
```

### 请求参数

| 参数名     | 类型    | 必填 | 说明                                                         |
|------------|---------|------|--------------------------------------------------------------|
| installed  | Boolean | 否   | 安装状态过滤。传 true 只查已安装，传 false 只查未安装，不传查全部可见 |

### 权限控制

- 未登录用户：仅能看到 `public` 命名空间下的公开技能
- 已登录用户：
  - `public` 技能 → 所有人可见
  - `personal` 技能 → 仅创建者本人可见
  - `private` 技能 → 仅所属命名空间的成员可见

### 返回数据

```json
{
  "code": "0000",
  "message": "成功",
  "data": [
    {
      "id": "string",
      "name": "string",
      "slug": "string",
      "namespaceId": "string",
      "namespaceName": "string",
      "description": "string",
      "visibility": "public | private | personal",
      "status": "active | pending_review | draft | rejected",
      "currentVersion": "string",
      "downloadCount": 0,
      "starCount": 0,
      "ratingAvg": 0.0,
      "ratingCount": 0,
      "latestVersion": "string",
      "lastVersionId": "string",
      "tags": ["string"],
      "createTime": "2025-01-01T00:00:00.000+0000",
      "updateTime": "2025-01-01T00:00:00.000+0000",
      "createNo": "string"
    }
  ]
}
```

### 返回字段说明

| 字段名          | 类型       | 说明                              |
|-----------------|------------|-----------------------------------|
| id              | String     | 技能ID                            |
| name            | String     | 技能名称                          |
| slug            | String     | 唯一标识（URL友好）               |
| namespaceId     | String     | 所属命名空间ID                    |
| namespaceName   | String     | 所属命名空间名称                  |
| description     | String     | 技能描述                          |
| visibility      | String     | 可见性: public / private / personal |
| status          | String     | 状态: active / pending_review / draft / rejected |
| currentVersion  | String     | 当前版本号                        |
| downloadCount   | Long       | 下载次数                          |
| starCount       | Long       | 收藏次数                          |
| ratingAvg       | Double     | 平均评分                          |
| ratingCount     | Long       | 评分人数                          |
| latestVersion   | String     | 最新版本号（语义化版本）           |
| lastVersionId   | String     | 最新版本ID                        |
| tags            | String[]   | 标签列表                          |
| createTime      | Date       | 创建时间                          |
| updateTime      | Date       | 更新时间                          |
| createNo        | String     | 创建人登录名                      |

---

## 2. 下载指定版本的技能 ZIP 包

```
GET /client/skills/{skillId}/versions/{versionId}/download
```

### 路径参数

| 参数名    | 类型   | 必填 | 说明       |
|-----------|--------|------|------------|
| skillId   | String | 是   | 技能ID     |
| versionId | String | 是   | 版本ID     |

### 响应

- Content-Type: `application/zip`
- Content-Disposition: `attachment; filename="{技能名}_{版本号}.zip"`
- 状态码 200 返回 ZIP 文件流
- 文件不存在时返回 500 + 错误信息

### 附加逻辑

- 每次下载会自动增加该技能的 `downloadCount`（+1）
- 文件名由后端动态生成：`{技能名称}_{语义化版本号}.zip`

### 错误码

| HTTP状态码 | 说明                 |
|------------|----------------------|
| 200        | 成功，返回文件流      |
| 500        | 文件不存在或读取失败  |

---

## 3. 查询当前用户可见的命名空间列表（已排除）

```
GET /client/namespaces/list
```

说明：该接口已从文档中移除，但代码中存在。不对外提供。
