<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDivider,
  NInput,
  NSpace,
  NStatistic,
  NTable,
  NTabs,
  NTabPane,
  useDialog,
  useMessage,
} from 'naive-ui'

import api from '@/api'

defineOptions({ name: 'ExerciseLibrarySeedPublish' })

const message = useMessage()
const dialog = useDialog()

const metaLoading = ref(false)
const meta = ref(null)

const seedText = ref('')
const parsedItems = ref([])
const parseError = ref('')
const publishing = ref(false)

const previewItems = computed(() => parsedItems.value.slice(0, 10))

const patchText = ref('')
const parsedPatch = ref(null)
const patchError = ref('')
const patchPublishing = ref(false)

function formatMs(ms) {
  const v = Number(ms)
  if (!Number.isFinite(v) || v <= 0) return '--'
  return new Date(v).toLocaleString()
}

async function loadMeta() {
  metaLoading.value = true
  try {
    meta.value = await api.getExerciseLibraryMeta()
  } finally {
    metaLoading.value = false
  }
}

function tryParseSeedText(text) {
  parseError.value = ''
  parsedItems.value = []

  const raw = String(text || '').trim()
  if (!raw) {
    parseError.value = '请输入或选择种子 JSON'
    return
  }

  let payload
  try {
    payload = JSON.parse(raw)
  } catch (err) {
    parseError.value = `JSON 解析失败：${err?.message || String(err)}`
    return
  }

  const items =
    Array.isArray(payload) ? payload : payload?.items || payload?.payload || payload?.exercises

  if (!Array.isArray(items)) {
    parseError.value = '格式不正确：需要 JSON 数组，或包含 items/payload/exercises 的对象'
    return
  }

  if (!items.length) {
    parseError.value = '种子为空：items 数组不能为空'
    return
  }

  parsedItems.value = items
}

function tryParsePatchText(text) {
  patchError.value = ''
  parsedPatch.value = null

  const raw = String(text || '').trim()
  if (!raw) {
    patchError.value = '请输入 Patch JSON'
    return
  }

  let payload
  try {
    payload = JSON.parse(raw)
  } catch (err) {
    patchError.value = `JSON 解析失败：${err?.message || String(err)}`
    return
  }

  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    patchError.value = '格式不正确：Patch 必须是对象'
    return
  }

  const baseVersion = Number(payload.baseVersion)
  if (!Number.isFinite(baseVersion) || baseVersion < 1) {
    patchError.value = 'baseVersion 必须是 >= 1 的数字'
    return
  }

  const added = Array.isArray(payload.added) ? payload.added : []
  const updated = Array.isArray(payload.updated) ? payload.updated : []
  const deleted = Array.isArray(payload.deleted) ? payload.deleted : []

  if (!added.length && !updated.length && !deleted.length) {
    patchError.value = 'Patch 为空：至少需要 added/updated/deleted 之一'
    return
  }

  parsedPatch.value = {
    baseVersion: Math.trunc(baseVersion),
    added,
    updated,
    deleted,
    generatedAt: payload.generatedAt,
  }
}

function fillPatchTemplate() {
  const baseVersion = Number(meta.value?.version || 1)
  patchText.value = JSON.stringify(
    {
      baseVersion,
      added: [],
      updated: [],
      deleted: [],
      generatedAt: Date.now(),
    },
    null,
    2
  )
  tryParsePatchText(patchText.value)
}

async function handlePickFile(e) {
  const file = e?.target?.files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    seedText.value = text
    tryParseSeedText(text)
    message.success(`已读取文件：${file.name}`)
  } catch (err) {
    message.error(`读取文件失败：${err?.message || String(err)}`)
  } finally {
    // 允许重复选择同一个文件
    e.target.value = ''
  }
}

async function publish() {
  tryParseSeedText(seedText.value)
  if (parseError.value) {
    message.error(parseError.value)
    return
  }

  dialog.warning({
    title: '确认发布种子？',
    content: `将发布 ${parsedItems.value.length} 条动作到新版本。发布后 App 可通过拉取（或推送触发刷新）同步。`,
    positiveText: '发布',
    negativeText: '取消',
    async onPositiveClick() {
      publishing.value = true
      try {
        const res = await api.publishExerciseLibrarySeed(parsedItems.value)
        message.success(`发布成功：version=${res?.version ?? '--'}`)
        await loadMeta()
      } finally {
        publishing.value = false
      }
    },
  })
}

async function publishPatch() {
  tryParsePatchText(patchText.value)
  if (patchError.value) {
    message.error(patchError.value)
    return
  }

  const patch = parsedPatch.value
  if (!patch) return

  const addedCount = Array.isArray(patch.added) ? patch.added.length : 0
  const updatedCount = Array.isArray(patch.updated) ? patch.updated.length : 0
  const deletedCount = Array.isArray(patch.deleted) ? patch.deleted.length : 0

  dialog.warning({
    title: '确认发布增量 Patch？',
    content: `baseVersion=${patch.baseVersion}，新增 ${addedCount} / 更新 ${updatedCount} / 删除 ${deletedCount}。发布后将生成新版本。`,
    positiveText: '发布',
    negativeText: '取消',
    async onPositiveClick() {
      patchPublishing.value = true
      try {
        const res = await api.patchExerciseLibrarySeed(patch)
        message.success(`发布成功：version=${res?.version ?? '--'}`)
        patchText.value = ''
        parsedPatch.value = null
        await loadMeta()
      } finally {
        patchPublishing.value = false
      }
    },
  })
}

onMounted(() => {
  loadMeta()
})
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="官方动作库（种子发布）" size="small" :loading="metaLoading">
      <NAlert type="info" show-icon :bordered="false">
        仅管理员可发布。发布后可通过线上推送触发 App 刷新；App 端也会按每日一次节流进行拉取检测。
      </NAlert>
      <NDivider />
      <NSpace wrap>
        <NStatistic label="当前版本" :value="meta?.version ?? '--'" />
        <NStatistic label="动作数量" :value="meta?.totalCount ?? '--'" />
        <NStatistic label="更新时间" :value="formatMs(meta?.lastUpdated)" />
        <NStatistic label="Checksum" :value="meta?.checksum ?? '--'" />
      </NSpace>
    </NCard>

    <NCard title="发布新版本" size="small">
      <NSpace vertical size="medium">
        <NTabs type="line" animated>
          <NTabPane name="paste" tab="粘贴 JSON">
            <NSpace vertical size="small">
              <NInput
                v-model:value="seedText"
                type="textarea"
                placeholder="粘贴 ExerciseSeedData（推荐：包含 payload/entityVersion），或直接粘贴 ExerciseDto 数组（或 { items/payload/exercises: [...] }）"
                :autosize="{ minRows: 10, maxRows: 22 }"
                @blur="tryParseSeedText(seedText)"
              />
              <NSpace>
                <NButton secondary @click="tryParseSeedText(seedText)">解析预览</NButton>
                <NButton type="primary" :loading="publishing" v-permission="'post/api/v1/admin/exercise/library/publish'" @click="publish">
                  发布
                </NButton>
              </NSpace>
              <NAlert v-if="parseError" type="error" show-icon>
                {{ parseError }}
              </NAlert>
            </NSpace>
          </NTabPane>
          <NTabPane name="file" tab="选择文件">
            <NSpace vertical size="small">
              <input
                type="file"
                accept="application/json"
                @change="handlePickFile"
              />
              <div class="text-xs text-gray-500">
                选择文件后会自动读取并解析；也可切换到“粘贴 JSON”查看或修改内容。
              </div>
            </NSpace>
          </NTabPane>
          <NTabPane name="patch" tab="增量更新 Patch">
            <NSpace vertical size="small">
              <NAlert type="info" show-icon :bordered="false">
                Patch 结构：{ baseVersion, added, updated, deleted, generatedAt? }。updated 按 id 只覆盖你填写的字段。
              </NAlert>
              <NInput
                v-model:value="patchText"
                type="textarea"
                placeholder="粘贴 Patch JSON"
                :autosize="{ minRows: 10, maxRows: 22 }"
                @blur="tryParsePatchText(patchText)"
              />
              <NSpace>
                <NButton secondary @click="fillPatchTemplate">生成模板</NButton>
                <NButton secondary @click="tryParsePatchText(patchText)">解析预览</NButton>
                <NButton
                  type="primary"
                  :loading="patchPublishing"
                  v-permission="'post/api/v1/admin/exercise/library/patch'"
                  @click="publishPatch"
                >
                  发布 Patch
                </NButton>
              </NSpace>
              <NAlert v-if="patchError" type="error" show-icon>
                {{ patchError }}
              </NAlert>
              <div v-if="parsedPatch" class="text-xs text-gray-500">
                baseVersion={{ parsedPatch.baseVersion }}；added={{ parsedPatch.added?.length || 0 }}；updated={{
                  parsedPatch.updated?.length || 0
                }}；deleted={{ parsedPatch.deleted?.length || 0 }}
              </div>
            </NSpace>
          </NTabPane>
        </NTabs>

        <NDivider />

        <div class="text-sm text-gray-600">
          预览（前 10 条）：{{ parsedItems.length ? `共 ${parsedItems.length} 条` : '未解析' }}
        </div>
        <NTable size="small" striped :single-line="false">
          <thead>
            <tr>
              <th style="width: 220px">id</th>
              <th style="width: 200px">name</th>
              <th style="width: 140px">muscleGroup</th>
              <th style="width: 160px">category</th>
              <th style="width: 180px">equipment</th>
              <th style="width: 140px">difficulty</th>
              <th style="width: 220px">updatedAt</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!previewItems.length">
              <td colspan="7" class="py-6 text-center text-gray-500">暂无预览数据</td>
            </tr>
            <tr v-for="item in previewItems" :key="item.id">
              <td>{{ item.id }}</td>
              <td>{{ item.name }}</td>
              <td>{{ item.muscleGroup }}</td>
              <td>{{ item.category }}</td>
              <td>{{ Array.isArray(item.equipment) ? item.equipment.join(', ') : item.equipment }}</td>
              <td>{{ item.difficulty }}</td>
              <td>{{ formatMs(item.updatedAt) }}</td>
            </tr>
          </tbody>
        </NTable>
      </NSpace>
    </NCard>
  </NSpace>
</template>
