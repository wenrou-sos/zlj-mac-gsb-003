<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  collectionApi,
  exhibitionApi,
  loanApi,
  locationApi,
  movementApi,
  restorationApi,
} from '../api'

const route = useRoute()
const id = Number(route.params.id)
const detail = ref(null)
const movements = ref([])
const restorations = ref([])
const loans = ref([])
const exhibitions = ref([])
const locations = ref([])
const exExceptions = ref([])

const moveDialog = ref(false)
const moveForm = ref({ move_type: '移库', to_location_id: null, purpose: '', operator: '', remark: '' })
const submitting = ref(false)

const moveTypeMap = {
  入库: 'success',
  出库: 'warning',
  移库: 'primary',
  布展: 'primary',
  撤展归库: 'success',
  修复出库: 'warning',
  修复归库: 'success',
  借展出库: 'danger',
  借展归还: 'success',
}

async function load() {
  detail.value = await collectionApi.get(id)
  movements.value = await movementApi.list({ collection_id: id, limit: 500 })
  restorations.value = await restorationApi.list({ collection_id: id })
  loans.value = await loanApi.list()
  const allEx = await exhibitionApi.list()
  loans.value = loans.value.filter((l) => l.collection_id === id)
  exhibitions.value = allEx.filter((e) => e.items.some((i) => i.collection_id === id))
  exExceptions.value = await collectionApi.exhibitionExceptions(id)
}

const openExExceptions = computed(() => exExceptions.value.filter((e) => !e.resolved))

async function submitMove() {
  if (['移库', '入库'].includes(moveForm.value.move_type) && !moveForm.value.to_location_id) {
    ElMessage.warning('请选择目标位置')
    return
  }
  submitting.value = true
  try {
    await collectionApi.move(id, { ...moveForm.value })
    ElMessage.success('流转已登记')
    moveDialog.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  locations.value = await locationApi.list()
  await load()
})
</script>

<template>
  <div class="page-container" v-if="detail">
    <el-page-header @back="$router.push('/collections')" content="返回藏品列表" />

    <el-card style="margin-top:14px" shadow="never">
      <div class="head">
        <div>
          <div class="title-row">
            <h2 style="margin:0">{{ detail.name }}</h2>
            <el-tag style="margin-left:10px">{{ detail.status }}</el-tag>
          </div>
          <div class="meta-line">
            <el-tag size="small" effect="plain">{{ detail.accession_no }}</el-tag>
            <span>{{ detail.category }}</span>
            <span v-if="detail.dynasty">{{ detail.dynasty }}</span>
            <span v-if="detail.grade">
              <el-tag size="small" type="warning" effect="plain">{{ detail.grade }}</el-tag>
            </span>
          </div>
        </div>
        <el-button type="primary" :icon="'Switch'" @click="moveDialog = true">登记出入库 / 移库</el-button>
      </div>
      <el-descriptions :column="3" border style="margin-top:16px">
        <el-descriptions-item label="材质">{{ detail.material || '—' }}</el-descriptions-item>
        <el-descriptions-item label="尺寸">{{ detail.dimension || '—' }}</el-descriptions-item>
        <el-descriptions-item label="重量">{{ detail.weight || '—' }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ detail.source || '—' }}</el-descriptions-item>
        <el-descriptions-item label="入藏日期">{{ detail.acquired_date || '—' }}</el-descriptions-item>
        <el-descriptions-item label="当前位置">
          {{ detail.location ? `${detail.location.code} ${detail.location.name}` : '不在库' }}
        </el-descriptions-item>
        <el-descriptions-item label="档案描述" :span="3">{{ detail.description || '—' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-alert
      v-if="openExExceptions.length"
      type="error"
      :closable="false"
      style="margin-top:14px"
      :title="`${openExExceptions.length} 条布展/撤展异常未解决`"
    >
      <div v-for="e in openExExceptions" :key="e.id" style="display:flex;align-items:center;gap:8px;padding:3px 0">
        <el-tag size="small" type="danger" effect="plain">{{ e.phase }}异常</el-tag>
        <span style="flex:1">
          「{{ e.exhibition_title }}」{{ e.note }}
          <span style="color:#909399;font-size:12px">
            ({{ e.created_at.replace('T', ' ').slice(0, 16) }}<template v-if="e.created_by"> · {{ e.created_by }}</template>)
          </span>
        </span>
        <el-button link type="primary" size="small" @click="$router.push(`/exhibitions/${e.exhibition_id}`)">
          前往展览处理
        </el-button>
      </div>
    </el-alert>

    <el-card style="margin-top:14px" shadow="never">
      <el-tabs>
        <el-tab-pane label="出入库流转">
          <el-timeline>
            <el-timeline-item
              v-for="m in movements"
              :key="m.id"
              :type="moveTypeMap[m.move_type] || 'info'"
              :timestamp="m.move_date.replace('T', ' ').slice(0, 16)"
            >
              <el-tag size="small" :type="moveTypeMap[m.move_type] || 'info'">{{ m.move_type }}</el-tag>
              <span style="margin:0 10px">
                {{ m.from_location?.name || '—' }} → {{ m.to_location?.name || '库外' }}
              </span>
              <span v-if="m.purpose" style="color:#606266">{{ m.purpose }}</span>
              <div style="font-size:12px;color:#909399;margin-top:2px">
                <span v-if="m.operator">操作员:{{ m.operator }}</span>
                <span v-if="m.handler" style="margin-left:12px">经手:{{ m.handler }}</span>
                <span v-if="m.remark" style="margin-left:12px">备注:{{ m.remark }}</span>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-tab-pane>

        <el-tab-pane :label="`展陈记录 (${exhibitions.length})`">
          <el-empty v-if="!exhibitions.length" description="暂无展陈记录" :image-size="70" />
          <el-timeline v-else>
            <el-timeline-item v-for="ex in exhibitions" :key="ex.id" :timestamp="`${ex.start_date} ~ ${ex.end_date}`">
              <strong>{{ ex.title }}</strong>
              <el-tag size="small" style="margin-left:8px" :type="ex.status === '开展中' ? 'primary' : 'info'">
                {{ ex.status }}
              </el-tag>
              <div style="font-size:13px;color:#606266">
                展厅:{{ ex.venue }} · 策展人:{{ ex.curator || '—' }}
              </div>
              <div
                v-for="it in ex.items.filter((i) => i.collection_id === id)"
                :key="it.id"
                style="font-size:12px;color:#909399"
              >
                <div>
                  展位:{{ it.display_location || '—' }} · {{ it.status }}
                  <template v-if="it.mounted_at">
                    · 布展验收 {{ it.mount_acceptor || '—' }} @ {{ it.mounted_at.replace('T', ' ').slice(0, 16) }}
                  </template>
                  <template v-if="it.dismounted_at">
                    · 撤展验收 {{ it.dismount_acceptor || '—' }} @ {{ it.dismounted_at.replace('T', ' ').slice(0, 16) }}
                  </template>
                </div>
                <div v-for="e in (it.exceptions || [])" :key="e.id" style="margin-top:2px">
                  <el-tag size="small" :type="e.resolved ? 'info' : 'danger'" effect="plain">
                    {{ e.phase }}异常 · {{ e.resolved ? '已解决' : '未解决' }}
                  </el-tag>
                  <span :style="{ color: e.resolved ? '#909399' : '#f56c6c' }">{{ e.note }}</span>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-tab-pane>

        <el-tab-pane :label="`修复记录 (${restorations.length})`">
          <el-empty v-if="!restorations.length" description="暂无修复记录" :image-size="70" />
          <el-collapse v-else accordion>
            <el-collapse-item v-for="r in restorations" :key="r.id" :name="r.id">
              <template #title>
                <el-tag size="small" :type="r.status === '进行中' ? 'warning' : 'success'" style="margin-right:10px">
                  {{ r.status }}
                </el-tag>
                <strong>{{ r.project_name }}</strong>
                <span style="margin-left:12px;color:#909399;font-size:12px">
                  {{ r.start_date }} ~ {{ r.end_date || '至今' }} · {{ r.restorer }}
                </span>
              </template>
              <p v-if="r.reason"><b>病害状况:</b>{{ r.reason }}</p>
              <p v-if="r.plan"><b>修复方案:</b>{{ r.plan }}</p>
              <el-timeline style="margin-top:8px">
                <el-timeline-item
                  v-for="(t, i) in r.timeline"
                  :key="i"
                  :timestamp="t.date"
                  placement="top"
                >
                  <b>{{ t.stage }}</b>
                  <div style="font-size:13px;color:#606266">{{ t.note }}</div>
                </el-timeline-item>
              </el-timeline>
              <p v-if="r.result" style="color:#677c4b"><b>修复结果:</b>{{ r.result }}</p>
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>

        <el-tab-pane :label="`借展记录 (${loans.length})`">
          <el-empty v-if="!loans.length" description="暂无借展记录" :image-size="70" />
          <el-table v-else :data="loans" size="small">
            <el-table-column prop="borrowing_institution" label="借入机构" min-width="180" />
            <el-table-column prop="exhibition_title" label="展览" min-width="160" />
            <el-table-column prop="loan_date" label="借出日期" width="110" />
            <el-table-column prop="due_date" label="应还日期" width="110" />
            <el-table-column prop="return_date" label="实际归还" width="110" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === '已逾期' ? 'danger' : row.status === '已归还' ? 'info' : 'warning'">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="moveDialog" title="登记出入库 / 移库" width="520px">
      <el-form :model="moveForm" label-width="92px">
        <el-form-item label="流转类型">
          <el-radio-group v-model="moveForm.move_type">
            <el-radio-button value="入库">入库</el-radio-button>
            <el-radio-button value="出库">出库</el-radio-button>
            <el-radio-button value="移库">移库</el-radio-button>
            <el-radio-button value="撤展归库">归库</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="目标位置">
          <el-select
            v-model="moveForm.to_location_id"
            filterable
            clearable
            style="width:100%"
            :disabled="moveForm.move_type === '出库'"
          >
            <el-option
              v-for="l in locations.filter((x) => x.location_type === '库房')"
              :key="l.id"
              :label="`${l.code} ${l.name}`"
              :value="l.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="事由">
          <el-input v-model="moveForm.purpose" placeholder="如 盘点移库 / 研究提用" />
        </el-form-item>
        <el-form-item label="操作员">
          <el-input v-model="moveForm.operator" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="moveForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="moveDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitMove">确认登记</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.title-row {
  display: flex;
  align-items: center;
}
.meta-line {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-top: 8px;
  color: #606266;
  font-size: 13px;
}
</style>
