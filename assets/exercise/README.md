# GymBro 动作库种子数据

## 📁 文件说明

- `exercise_official_seed.json` - 官方动作种子数据
- `exercise_schema.json` - JSON Schema 验证文件（已与 shared-models 严格对齐）
- `README.md` - 本说明文档

## 🎯 数据概览

当前种子数据包含 **60 个精选健身动作**（每个部位 10 个），覆盖主要肌群：

### 胸部动作 (10个)
- 杠铃卧推 (`off_5023c57c`)
- 哑铃卧推 (`off_a9a8603d`)
- 上斜杠铃卧推
- 上斜哑铃卧推
- 下斜杠铃卧推
- 哑铃飞鸟
- 绳索夹胸（站姿）
- 俯卧撑（标准）
- 器械坐姿推胸
- 夹胸机（蝴蝶机）

### 背部动作 (10个)
- 引体向上 (`off_63bab238`)
- 杠铃划船 (`off_dee0cb74`)
- 高位下拉
- 坐姿绳索划船
- 单臂哑铃划船
- T 杠划船
- 直臂下压（绳索）
- 面拉（Face Pull）
- 反向飞鸟（上背）
- 罗马椅背伸

### 腿部动作 (10个)
- 杠铃深蹲 (`off_eb02d317`)
- 硬拉 (`off_615f2a8a`)
- 前蹲（杠铃）
- 腿举（Leg Press）
- 保加利亚分腿蹲
- 行走弓步
- 腿屈伸（腿伸）
- 腿弯举（腿后侧）
- 站姿提踵
- 臀推（Hip Thrust）

### 肩部动作 (10个)
- 杠铃推举 (`off_b7ccaf9d`)
- 哑铃侧平举 (`off_93566fbc`)
- 哑铃推举
- 阿诺德推举
- 哑铃前平举
- 俯身哑铃飞鸟（后束）
- 绳索侧平举
- 立姿杠铃划船
- 耸肩（哑铃）
- 绳索后束飞鸟

### 手臂动作 (10个)
- 杠铃弯举 (`off_eafd145e`)
- 双杠臂屈伸 (`off_a87e1409`)
- 哑铃锤式弯举
- 交替哑铃弯举
- 牧师凳弯举
- 绳索下压（肱三头）
- 仰卧臂屈伸（法式推举）
- 过顶哑铃臂屈伸
- 窄距卧推
- 反手弯举

### 核心动作 (10个)
- 平板支撑 (`off_4beb4c0f`)
- 侧平板支撑
- 仰卧卷腹
- 反向卷腹
- 悬垂举腿
- 俄罗斯转体
- 死虫式（Dead Bug）
- 登山者
- 绳索伐木（Woodchop）
- 鸟狗式（Bird Dog）

## 🔧 ID 生成规则

### 官方动作 ID
- **格式**: `off_{hash}`
- **生成**: `md5(name).take(8)`（UTF-8，取 8 位十六进制小写；与当前种子文件内的 id 一致）
- **示例**: `off_5023c57c` (杠铃卧推)

### 自定义动作 ID
- **格式**: `u_{userId}_{uuid}`
- **生成**: 用户ID + UUID前8位
- **示例**: `u_user123_a1b2c3d4`

## 📝 数据格式

每个动作包含以下字段：

### 必填字段
- `id` - 唯一标识符
- `name` - 动作名称（纯字符串）
- `muscleGroup` - 主要肌群
- `category` - 动作分类
- `equipment` - 所需器械
- `source` - 动作来源
- `isCustom/isOfficial` - 动作类型标识
- `createdAt/updatedAt` - 时间戳

### 可选字段
- `description` - 动作描述（string）
- `targetMuscles` - 目标肌群（枚举数组）
- `secondaryMuscles` - 次要肌群（枚举数组）
- `difficulty` - 难度等级（BEGINNER/NOVICE/INTERMEDIATE/ADVANCED/EXPERT）
- `defaultSets` / `defaultReps` / `restTimeSeconds` - 默认训练参数
- `steps` - 动作步骤（string 数组）
- `tips` - 训练技巧（string 数组）
- `media` - 媒体资源（字段：`thumbnailUrl`/`videoUrl`/`imageUrls`/`stepImages`/`version`）

## ✅ 数据验证

使用 JSON Schema 验证数据格式：

```bash
# 安装验证工具
npm install -g ajv-cli

# 验证数据格式
ajv validate -s exercise_schema.json -d exercise_official_seed.json
```

> 编辑器识别：`exercise_official_seed.json` 已内联 `"$schema": "./exercise_schema.json"`，可自动关联 Schema。

## 🚀 使用方式

### 在代码中加载
```kotlin
// OfficialExerciseInitializer.kt（与模型严格对齐）
private fun loadSeedData(): ExerciseSeedData {
    val json = context.assets.open("exercise/exercise_official_seed.json")
        .bufferedReader().use { it.readText() }
    // 建议使用容错配置，允许前向兼容
    return Json { ignoreUnknownKeys = true }.decodeFromString(json)
}
```

### 数据初始化流程
1. 应用首次启动时检查官方动作数量
2. 如果为空，从 assets 加载种子数据
3. 转换为 Entity 对象并批量插入数据库
4. 标记初始化完成，避免重复加载

## 📊 数据统计

- **总动作数**: 60
- **难度分布**: 
  - 初级: 3个 (27%)
  - 中级: 7个 (64%)
  - 高级: 1个 (9%)
- **器械分布**:
  - 杠铃: 5个 (45%)
  - 哑铃: 2个 (18%)
  - 徒手: 4个 (36%)

## 🔄 更新流程

1. **修改数据**: 编辑 `exercise_official_seed.json`
2. **验证格式**: 运行 JSON Schema 验证（Schema 已对齐 `shared-models` 枚举与字段名）
3. **更新版本**: 修改 `entityVersion` 和 `generatedAt`
4. **测试加载**: 确保应用能正确加载新数据
5. **提交代码**: 通过 PR 流程合并更改

## 🛡️ 注意事项

1. **ID 唯一性**: 确保所有 ID 在全局范围内唯一
2. **哈希一致性**: 官方动作 ID 必须与名称哈希匹配
3. **时间戳**: `createdAt <= updatedAt`
4. **必填字段**: 所有必填字段都不能为空
5. **枚举值**: 确保所有枚举字段使用正确的值

## 📞 联系方式

如有问题或建议，请联系开发团队或提交 Issue。
