# 动作库：种子数据库 scheme（后端须知）

- 更新日期：2026-01-03
- 目标：后端创建“官方动作库种子”的版本化数据源，并按客户端固定契约下发（meta/updates/full），使客户端可 **每日一次拉取检测** + **增量同步**，增量失败自动回退 full。

---

## 1) SSOT（后端实现必须对齐的真值来源）

### 1.1 客户端数据模型（网络 SSOT）

- DTO：`shared-models/src/main/kotlin/com/example/gymbro/shared/models/exercise/ExerciseDto.kt`
- 枚举值（必须使用枚举名原样，区分大小写）：
  - `MuscleGroup`：`shared-models/src/main/kotlin/com/example/gymbro/shared/models/exercise/MuscleGroup.kt`
  - `ExerciseCategory`：`shared-models/src/main/kotlin/com/example/gymbro/shared/models/exercise/ExerciseCategory.kt`
  - `Equipment`：`shared-models/src/main/kotlin/com/example/gymbro/shared/models/exercise/Equipment.kt`
  - `DifficultyLevel`：`shared-models/src/main/kotlin/com/example/gymbro/shared/models/exercise/DifficultyLevel.kt`
  - `ExerciseSource`：`shared-models/src/main/kotlin/com/example/gymbro/shared/models/exercise/ExerciseSource.kt`

### 1.2 种子与 Schema（编辑/校验 SSOT）

- 种子（离线首启兜底）：`app/src/main/assets/exercise/exercise_official_seed.json`
- JSON Schema：`app/src/main/assets/exercise/exercise_schema.json`

> 注意：客户端 API 的 `full` 端点返回的是 `List<ExerciseDto>`，不是 `ExerciseSeedData` 包装对象；后端可以内部存 `ExerciseSeedData`，但对外要“拆出 payload”返回。

---

## 2) 必须实现的下发接口（固定契约）

接口定义：`data/src/main/kotlin/com/example/gymbro/data/exercise/remote/ExerciseApi.kt`

### 2.1 `GET /api/v1/exercise/library/meta`

返回：`ExerciseLibraryMeta`

```json
{
  "version": 1,
  "totalCount": 11,
  "lastUpdated": 1718716800000,
  "checksum": "sha256:…",
  "downloadUrl": null
}
```

约束：
- `version`：单调递增 `Int`（客户端用其与本地版本比较）
- `lastUpdated`：毫秒时间戳 `Long`
- `checksum`：非空字符串（目前客户端不强依赖内容，但建议用于后台审计/排障）
- `downloadUrl`：可选（当前客户端不使用，可先置空）

### 2.2 `GET /api/v1/exercise/library/updates?from=<int>&to=<int>`

返回：`ExerciseLibraryUpdates`

```json
{
  "fromVersion": 1,
  "toVersion": 2,
  "added": [],
  "updated": [],
  "deleted": ["off_5023c57c"],
  "timestamp": 1718803200000
}
```

约束：
- `added/updated`：元素必须是 `ExerciseDto`（字段名 camelCase）
- `deleted`：仅填 `id`（字符串）
- 若后端无法提供某段版本差分（例如只保留最新快照），**直接返回错误**（4xx/5xx 均可）即可触发客户端回退 full（见 §2.3）

### 2.3 `GET /api/v1/exercise/library/full`

返回：`List<ExerciseDto>`

```json
[
  {
    "id": "off_5023c57c",
    "name": "杠铃卧推",
    "description": "…",
    "muscleGroup": "CHEST",
    "category": "UPPER_BODY",
    "equipment": ["BARBELL"],
    "difficulty": "INTERMEDIATE",
    "source": "OFFICIAL",
    "isCustom": false,
    "isOfficial": true,
    "createdAt": 1718716800000,
    "updatedAt": 1718716800000
  }
]
```

约束：
- `equipment` 建议至少 1 个元素（与 seed/schema 及客户端预期一致）
- `createdAt/updatedAt` 为毫秒时间戳 `Long`

---

## 3) 版本与差分生成（最小可行方案）

> 目标是让客户端“能同步”，而不是强行建复杂的服务端全文检索；先满足 `meta/updates/full`。

推荐最小数据结构（后端内部存储形态，供实现参考）：

1) **快照表（必需）**：每次发布一个版本快照  
   - `version (int pk)` / `generated_at_ms (bigint)` / `checksum (text)` / `payload_json (jsonb)`  
2) **差分表（可选但推荐）**：存储 `fromVersion→toVersion` 的增量包  
   - `from_version (int)` / `to_version (int)` / `added_json (jsonb)` / `updated_json (jsonb)` / `deleted_ids (jsonb)` / `timestamp_ms (bigint)`

差分生成建议：
- 以 `id` 为主键对比两个版本 payload：
  - 新增：新版本有、旧版本无
  - 删除：旧版本有、新版本无
  - 更新：`id` 相同但内容变更（可用 `updatedAt` 或内容 hash 判断）

---

## 4) ID 与“改名”风险（必须提前约束）

- 官方 ID 规则（SSOT）：`off_${md5(name).take(8)}`（UTF-8，取 8 位十六进制小写；以当前官方 seed 文件为准）
  - 这意味着：**官方动作一旦改名，会导致 ID 变化**，从而可能影响训练模板/历史引用。
- 后端建议策略：
  - 避免对已发布动作改名；如必须改名：按 **delete(oldId) + add(newId)** 处理，并确保客户端能通过增量 `deleted/added` 完成迁移。

---

## 5) 认证与缓存建议

- 官方库下发接口（meta/updates/full）：客户端调用时不显式传 token（即使带上 Authorization 也应允许），建议默认公开或做轻量限流。
- 可加 CDN/缓存：
  - `meta` 短缓存（分钟级）
  - `full` 可较长缓存（小时级），并配合 `checksum/version` 做缓存失效

---

## 7) 管理端增量更新（Patch 发布）

当仅需要改动少量动作（新增/字段级更新/删除）时，可使用 **Patch JSON** 发布新版本，避免每次上传 full：

- 端点：`POST /api/v1/admin/exercise/library/patch`（仅 admin 可用）
- 并发保护：必须提供 `baseVersion`，且需等于当前 `meta.version`；否则返回 `409 version_conflict`
- 更新语义：
  - `added`：新增完整 `ExerciseDto`（至少包含必填字段）
  - `updated`：按 `id` 匹配，仅覆盖你提供的字段（未提供字段保持不变）
  - `deleted`：按 `id` 删除
  - `generatedAt`：可选（毫秒），用于作为本次发布的 `lastUpdated`（同时作为自动补齐 `updatedAt` 的默认值）

示例：

```json
{
  "baseVersion": 12,
  "generatedAt": 1767398400000,
  "added": [],
  "updated": [
    {
      "id": "off_5023c57c",
      "description": "更新后的描述",
      "updatedAt": 1767398400000
    }
  ],
  "deleted": ["off_deadbeef"]
}
```

---

## 6) 验证清单（交付自测）

- 基础联通：三接口均能 200 返回且 JSON 字段名与类型符合上文
- 版本推进：`meta.version` 从 1→2 后，客户端 `updates?from=1&to=2` 可成功应用（或故意返回错误以验证客户端回退 `full`）
- 兼容性：返回体可包含额外字段（客户端 Gson 解析默认容忍），但 `ExerciseDto` 的关键字段必须存在且类型正确

> 客户端现状说明见：`docs/后端方案/动作库-种子数据库scheme-现状.md`
