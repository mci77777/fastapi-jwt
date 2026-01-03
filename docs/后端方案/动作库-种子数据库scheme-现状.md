# 动作库：种子数据库 scheme（现状）

- 更新日期：2026-01-03
- 结论（审查）：客户端侧“官方动作库”的 SSOT 是 `ExerciseDto`（网络/跨模块）与本地 `exercise` 表（Room），离线首启依赖 `assets` 种子；远端更新采用 **拉取式**（每日一次节流检测 + 手动刷新），后端只需按固定 REST 契约提供 `meta/updates/full` 即可下发。

---

## 1) 近期与本议题直接相关的提交（近端）

- `906fbb8a0`（2026-01-02）`exercise-library: schema/seed + daily sync check`
  - assets：补齐/对齐 `exercise_official_seed.json` 与 `exercise_schema.json`（并内联 `"$schema"` 便于编辑器关联）
  - SSOT：新增 `OfficialExerciseLibraryVersionStore`（SharedPreferences 维护官方库版本与“上次检测时间”）
  - 下发链路：新增 `ExerciseLibrarySyncWorker`（WorkManager 每日一次检测，失败容错且节流）
  - 同步逻辑：`ExerciseRepositoryImpl.syncOfficialLibrary()` 增量失败自动回退 full 覆盖（仅覆盖官方，不影响用户自定义）

> 备注：仓库存在 `assets/ai/README.md` 描述“AI 专用动作库 JSON 规范”，但当前仓库未包含对应 JSON 文件，且与本次客户端 `ExerciseApi` 下发契约不是同一条 SSOT 链路，避免混淆。

---

## 2) 种子（Seed）与 JSON Schema（SSOT）

### 2.1 assets 种子（离线首启兜底）

- 种子文件：`app/src/main/assets/exercise/exercise_official_seed.json`
- 种子载入：`data/src/main/kotlin/com/example/gymbro/data/exercise/initializer/OfficialExerciseInitializer.kt`
  - 解析模型：`ExerciseSeedData(payload: List<ExerciseDto>)`
  - 解析策略：`Json { ignoreUnknownKeys = true }`（容忍前向字段）

### 2.2 JSON Schema（编辑/校验 SSOT）

- Schema 文件：`app/src/main/assets/exercise/exercise_schema.json`
- 用途：
  - 编辑器联想与校验（seed 文件内联 `"$schema": "./exercise_schema.json"`）
  - 约束字段/枚举/ID 规则与 `ExerciseSeedData + ExerciseDto` 对齐

### 2.3 ID 规则（官方/自定义）

- SSOT：`shared-models/src/main/kotlin/com/example/gymbro/shared/models/exercise/ExerciseDto.kt`
- 官方：`off_${md5(name).take(8)}`（与当前官方 seed 文件一致）
  - 自定义：`u_${userId}_${uuid.take(8)}`

---

## 3) 客户端版本与节流（SSOT）

- 存储：SharedPreferences（非 Room），文件名 `exercise_library_prefs`
  - 版本 key：`Constants.Storage.LIBRARY_VERSION_KEY`
  - 上次检测 key：`Constants.Storage.LIBRARY_LAST_CHECK_AT_MS_KEY`
- 实现：`data/src/main/kotlin/com/example/gymbro/data/exercise/local/version/OfficialExerciseLibraryVersionStore.kt`
- 写入时机：
  - 初始化 seed 完成后：版本 = `seedData.entityVersion`
  - 远端同步成功（含回退 full）：版本 = `remoteMeta.version`

---

## 4) 下发/同步链路（端到端）

### 4.1 首次/空库初始化（离线可用）

- 入口：`data/src/main/kotlin/com/example/gymbro/data/exercise/initializer/ExerciseLibraryInitializerService.kt`
- 逻辑：
  - 若本地官方动作数量 `> 0`：跳过
  - 否则从 assets 读 seed → decode → upsert 入库 → 写入版本

### 4.2 每日一次“检测并同步”（拉取式）

- 调度：`app/src/main/kotlin/com/example/gymbro/GymBroApp.kt`（启动时 enqueue 唯一周期任务）
- Worker：`data/src/main/kotlin/com/example/gymbro/data/exercise/worker/ExerciseLibrarySyncWorker.kt`
  - 先检查 `last_check_at_ms`，距离上次检测 < 24h 则直接 `success()`（节流 SSOT）
  - 尽量保证离线可用：先 best-effort seed 初始化，再调用远端同步
  - 同步失败：记录 warning 并返回 `success()`（避免后台反复重试）

### 4.3 手动刷新（前台触发）

- ViewModel：`features/exercise-library/src/main/kotlin/com/example/gymbro/features/exerciselibrary/internal/presentation/viewmodel/ExerciseLibraryViewModel.kt`
- 行为：`Intent.RefreshExercises` → 同步官方库 → 重新加载列表

---

## 5) 远端契约（当前固定）

- Retrofit 接口：`data/src/main/kotlin/com/example/gymbro/data/exercise/remote/ExerciseApi.kt`
  - `GET /api/v1/exercise/library/meta` → `ExerciseLibraryMeta`
  - `GET /api/v1/exercise/library/updates?from&to` → `ExerciseLibraryUpdates`
  - `GET /api/v1/exercise/library/full` → `List<ExerciseDto>`
- 同步实现：`data/src/main/kotlin/com/example/gymbro/data/exercise/repository/ExerciseRepositoryImpl.kt`
  - 增量失败/版本断层：回退 full（只清空官方 `isCustom=0`，不动用户自定义）

---

## 6) 审查发现（对后端交付有影响的点）

1) **版本必须单调递增**：本地以 `Int` 维护版本；后端 `meta.version` 必须可比较且可回滚成本高。  
2) **时间戳单位统一为毫秒**：`createdAt/updatedAt/lastUpdated/timestamp` 都以 `Long(ms)` 约定。  
3) **Schema 文件存在重复字段名风险**：`exercise_schema.json` 内出现重复的 `difficulty` key（JSON 语义上“后者覆盖前者”），对外部 schema 工具的兼容性需留意。  

> 后端交接文档见：`docs/后端方案/动作库-种子数据库scheme-后端须知.md`
