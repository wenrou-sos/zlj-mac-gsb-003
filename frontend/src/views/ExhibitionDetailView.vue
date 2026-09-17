<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { collectionApi, exhibitionApi, locationApi } from '../api'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)

const ex = ref(null)
const loading = ref(false)
const candidates = ref([])
const storageLocations = ref([])

// ---- 对话框状态 ----
const planDialog = ref(false)
const planForm = reactive({
  collection_id: null,
  display_location: '',
  install_plan_note: '',
  planned_mount_date: '',
})

const mountDialog = ref(false)
const mountTarget = ref(null)
const mountForm = reactive({ acceptor: '', photo_note: '', anomaly: '' })

const dismountDialog = ref(false)
const dismountTarget = ref(null)
const dismountForm = reactive({
  acceptor: '',
  photo_note: '',
  anomaly: '',
  return_location_id: null,
})

const resolveDialog = ref(false)
const resolveTarget = reactive({ item: null, phase: 'mount' })
const resolveForm = reactive({ resolved_by: '', note: '' })

const coDialog = ref(false)
const coForm = reactive({
  change_type: '新增',
  reason: '',
  add_collection_id: null,
  remove_item_id: null,
  display_location: '',
  install_plan_note: '',
  planned_mount_date: '',
  requested_by: '',
})

const approveDialog = ref(false)
const approveTarget = ref(null)
const approveForm = reactive({ approved_by: '', approval_note: '', reject: false })

async function load() {
  loading.value = true
  try {
    ex.value = await exhibitionApi.get(id)
  } finally {
    loading.value = false
  }
}

const openAnomalies = computed(() => {
  if (!ex.value) return []
  const list = []
  for (const it of ex.value.items) {
    if (it.mount_anomaly && !it.mount_anomaly_resolved) {
      list.push({ item: it, phase: 'mount', label: '布展异常', at: it.mounted_at, text: it.mount_anomaly })
    }
    if (it.dismount_anomaly && !it.dismount_anomaly_resolved) {
      list.push({ item: it, phase: 'dismount', label: '撤展异常', at: it.dismounted_at, text: it.dismount_anomaly })
    }
  }
  return list
})

function statusTagType(s) {
  return { 待布展: 'info', 已布展: 'primary', 已撤展: 'success' }[s] || 'info'
}

function coTagType(s) {
  return { 待审批: 'warning', 已批准: 'primary', 已驳回: 'danger', 已执行: 'success' }[s] || 'info'
}

function fmt(t) {
  return t ? t.replace('T', ' ').slice(0, 16) : '—'
}

// ---- 清单冻结 ----
async function freeze() {
  try {
    const { value } = await ElMessageBox.prompt('请输入冻结操作人', '冻结展品清单', {
      confirmButtonText: '确认冻结',
      cancelButtonText: '取消',
      inputPlaceholder: '如 策展人 / 部门负责人',
    })
    await exhibitionApi.freeze(id, value || '策展团队')
    ElMessage.success('清单已冻结,此后增删展品须提交变更单审批')
    load()
  } catch (e) {
    /* 取消 */
  }
}

// ---- 筹备阶段:加入清单 ----
async function openPlan() {
  Object.assign(planForm, {
    collection_id: null,
    display_location: '',
    install_plan_note: '',
    planned_mount_date: '',
  })
  candidates.value = await collectionApi.list({ status: '在库' })
  planDialog.value = true
}

async function submitPlan() {
  if (!planForm.collection_id) {
    ElMessage.warning('请选择藏品')
    return
  }
  await exhibitionApi.planItem(id, { ...planForm })
  ElMessage.success('已加入展品清单(待布展)')
  planDialog.value = false
  load()
}

async function removePlanned(item) {
  await ElMessageBox.confirm(`将「${item.collection_name}」移出清单?`, '移除清单条目', {
    type: 'warning',
  })
  await exhibitionApi.removePlanned(id, item.id)
  ElMessage.success('已移出清单')
  load()
}

// ---- 布展验收 ----
function openMount(item) {
  mountTarget.value = item
  Object.assign(mountForm, { acceptor: '', photo_note: '', anomaly: '' })
  mountDialog.value = true
}

async function submitMount() {
  if (!mountForm.acceptor) {
    ElMessage.warning('请填写现场验收人')
    return
  }
  await exhibitionApi.mount(id, mountTarget.value.id, { ...mountForm })
  ElMessage.success(
    mountForm.anomaly ? '布展验收已登记,异常项将持续跟踪至闭环' : '布展验收完成'
  )
  mountDialog.value = false
  load()
}

// ---- 撤展验收 ----
function openDismount(item) {
  dismountTarget.value = item
  Object.assign(dismountForm, {
    acceptor: '',
    photo_note: '',
    anomaly: '',
    return_location_id: null,
  })
  dismountDialog.value = true
}

async function submitDismount() {
  if (!dismountForm.acceptor) {
    ElMessage.warning('请填写现场验收人')
    return
  }
  await exhibitionApi.dismount(id, dismountTarget.value.id, { ...dismountForm })
  ElMessage.success(
    dismountForm.anomaly ? '撤展验收已登记,异常项将持续跟踪至闭环' : '撤展验收完成'
  )
  dismountDialog.value = false
  load()
}

// ---- 异常闭环 ----
function openResolve(item, phase) {
  resolveTarget.item = item
  resolveTarget.phase = phase
  Object.assign(resolveForm, { resolved_by: '', note: '' })
  resolveDialog.value = true
}

async function submitResolve() {
  if (!resolveForm.resolved_by) {
    ElMessage.warning('请填写处理人')
    return
  }
  await exhibitionApi.resolveAnomaly(
    id,
    resolveTarget.item.id,
    resolveTarget.phase,
    { ...resolveForm }
  )
  ElMessage.success('异常已闭环')
  resolveDialog.value = false
  load()
}

// ---- 变更单 ----
async function openCO() {
  Object.assign(coForm, {
    change_type: '新增',
    reason: '',
    add_collection_id: null,
    remove_item_id: null,
    display_location: '',
    install_plan_note: '',
    planned_mount_date: '',
    requested_by: '',
  })
  candidates.value = await collectionApi.list({ status: '在库' })
  coDialog.value = true
}

const removableItems = computed(() =>
  ex.value ? ex.value.items.filter((i) => ['待布展', '已布展'].includes(i.status)) : []
)

async function submitCO() {
  if (!coForm.reason) {
    ElMessage.warning('请填写变更事由')
    return
  }
  if (['新增', '替换'].includes(coForm.change_type) && !coForm.add_collection_id) {
    ElMessage.warning('请选择新增/替换进来的藏品')
    return
  }
  if (['撤除', '替换'].includes(coForm.change_type) && !coForm.remove_item_id) {
    ElMessage.warning('请选择要撤除/替换的原展品')
    return
  }
  await exhibitionApi.createChangeOrder(id, { ...coForm })
  ElMessage.success('变更单已提交,等待审批')
  coDialog.value = false
  load()
}

function openApprove(co, reject = false) {
  approveTarget.value = co
  approveForm.reject = reject
  Object.assign(approveForm, { approved_by: '', approval_note: '' })
  approveDialog.value = true
}

async function submitApprove() {
  if (!approveForm.approved_by) {
    ElMessage.warning('请填写审批人')
    return
  }
  const payload = {
    approved_by: approveForm.approved_by,
    approval_note: approveForm.approval_note,
  }
  if (approveForm.reject) {
    await exhibitionApi.rejectChangeOrder(id, approveTarget.value.id, payload)
    ElMessage.success('变更单已驳回')
  } else {
    await exhibitionApi.approveChangeOrder(id, approveTarget.value.id, payload)
    ElMessage.success('变更单已批准并执行,新展品待现场布展验收')
  }
  approveDialog.value = false
  load()
}

onMounted(async () => {
  storageLocations.value = await locationApi.list({ location_type: '库房' })
  await load()
})
</script>

<template>
  <div class="page-container" v-if="ex" v-loading="loading">
    <el-page-header @back="router.push('/exhibitions')" content="返回展陈列表" />

    <!-- 标题区 -->
    <el-card style="margin-top:14px" shadow="never">
      <div class="head">
        <div>
          <div class="title-row">
            <h2 style="margin:0">{{ ex.title }}</h2>
            <el-tag style="margin-left:10px" :type="ex.status === '开展中' ? 'primary' : ex.status === '已结束' ? 'success' : 'info'">
              {{ ex.status }}
            </el-tag>
            <el-tag
              :type="ex.frozen ? 'warning' : 'info'"
              :effect="ex.frozen ? 'dark' : 'plain'"
              style="margin-left:8px"
            >
              {{ ex.frozen ? '清单已冻结' : '清单编制中' }}
            </el-tag>
            <el-tag v-if="ex.open_anomaly_count" type="danger" effect="dark" style="margin-left:8px">
              {{ ex.open_anomaly_count }} 项布撤展异常未闭环
            </el-tag>
          </div>
          <div class="meta-line">
            <span><el-icon><Location /></el-icon> {{ ex.venue }}</span>
            <span><el-icon><Calendar /></el-icon> {{ ex.start_date }} 至 {{ ex.end_date }}</span>
            <span v-if="ex.curator">策展人:{{ ex.curator }}</span>
            <span v-if="ex.frozen && ex.frozen_at">
              冻结于 {{ fmt(ex.frozen_at) }}<template v-if="ex.frozen_by"> · {{ ex.frozen_by }}</template>
            </span>
          </div>
        </div>
        <div class="head-actions">
          <el-button
            v-if="ex.status === '筹备中' && !ex.frozen"
            type="warning"
            :icon="'Lock'"
            @click="freeze"
          >
            冻结展品清单
          </el-button>
          <el-button
            v-if="ex.status === '筹备中' && !ex.frozen"
            type="primary"
            :icon="'Plus'"
            @click="openPlan"
          >
            加入展品清单
          </el-button>
          <el-button
            v-if="ex.status !== '已结束' && (ex.frozen || ex.status === '开展中')"
            type="primary"
            :icon="'DocumentAdd'"
            @click="openCO"
          >
            提交变更单
          </el-button>
        </div>
      </div>
      <p v-if="ex.description" class="desc">{{ ex.description }}</p>
      <el-alert
        v-if="!ex.frozen && ex.status === '筹备中'"
        title="清单未冻结:可直接增删展品与编辑安装计划;冻结后只能通过变更单审批增删。"
        type="info"
        :closable="false"
        style="margin-top:10px"
      />
      <el-alert
        v-if="ex.status === '开展中'"
        title="展览已开展:不允许无审批替换展品,任何新增/撤除/替换均须提交变更单并经审批后执行。"
        type="warning"
        :closable="false"
        style="margin-top:10px"
      />
    </el-card>

    <!-- 未闭环异常(持续可见) -->
    <el-card v-if="openAnomalies.length" shadow="never" style="margin-top:14px">
      <template #header>
        <div class="card-head">
          <el-icon color="#f56c6c"><WarningFilled /></el-icon>
          <span>未闭环布撤展异常({{ openAnomalies.length }})</span>
          <span class="sub">异常项在闭环前持续展示于展览详情与藏品详情</span>
        </div>
      </template>
      <el-table :data="openAnomalies" size="small" row-class-name="anomaly-row">
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.phase === 'mount' ? 'warning' : 'danger'">
              {{ row.label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="展品" min-width="200">
          <template #default="{ row }">
            <router-link :to="`/collections/${row.item.collection_id}`" class="link">
              {{ row.item.accession_no }} {{ row.item.collection_name }}
            </router-link>
            <span class="sub" v-if="row.item.display_location"> · {{ row.item.display_location }}</span>
          </template>
        </el-table-column>
        <el-table-column label="发生时间" width="150">
          <template #default="{ row }">{{ fmt(row.at) }}</template>
        </el-table-column>
        <el-table-column prop="text" label="异常描述" min-width="260" show-overflow-tooltip />
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openResolve(row.item, row.phase)">
              登记处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 展品清单 -->
    <el-card shadow="never" style="margin-top:14px">
      <template #header>
        <div class="card-head">
          <span>展品清单与安装计划({{ ex.items.length }})</span>
          <el-button
            v-if="ex.status === '筹备中' && !ex.frozen"
            link
            type="primary"
            size="small"
            @click="openPlan"
          >
            + 加入展品
          </el-button>
        </div>
      </template>
      <el-table :data="ex.items" size="small">
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="总登记号 / 名称" min-width="220">
          <template #default="{ row }">
            <router-link :to="`/collections/${row.collection_id}`" class="link">
              {{ row.accession_no }} {{ row.collection_name }}
            </router-link>
            <el-tag v-if="row.change_order_id" size="small" type="warning" effect="plain" style="margin-left:6px">
              变更单 #{{ row.change_order_id }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="display_location" label="展位" min-width="150">
          <template #default="{ row }">{{ row.display_location || '—' }}</template>
        </el-table-column>
        <el-table-column label="安装计划" min-width="200">
          <template #default="{ row }">
            <div>{{ row.install_plan_note || '—' }}</div>
            <div class="sub" v-if="row.planned_mount_date">计划布展:{{ row.planned_mount_date }}</div>
          </template>
        </el-table-column>
        <el-table-column label="布展验收" min-width="200">
          <template #default="{ row }">
            <template v-if="row.mounted_at">
              <div>{{ fmt(row.mounted_at) }} · {{ row.mount_acceptor }}</div>
              <div class="sub" v-if="row.mount_photo_note">📷 {{ row.mount_photo_note }}</div>
              <div v-if="row.mount_anomaly" :class="row.mount_anomaly_resolved ? 'anomaly-done' : 'anomaly-text'">
                {{ row.mount_anomaly_resolved ? '✓ 布展异常已闭环' : '⚠ 布展异常未闭环' }}
              </div>
            </template>
            <span v-else class="sub">未布展</span>
          </template>
        </el-table-column>
        <el-table-column label="撤展验收" min-width="200">
          <template #default="{ row }">
            <template v-if="row.dismounted_at">
              <div>{{ fmt(row.dismounted_at) }} · {{ row.dismount_acceptor }}</div>
              <div class="sub" v-if="row.dismount_photo_note">📷 {{ row.dismount_photo_note }}</div>
              <div v-if="row.dismount_anomaly" :class="row.dismount_anomaly_resolved ? 'anomaly-done' : 'anomaly-text'">
                {{ row.dismount_anomaly_resolved ? '✓ 撤展异常已闭环' : '⚠ 撤展异常未闭环' }}
              </div>
            </template>
            <span v-else class="sub">未撤展</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
          <el-button
            v-if="row.status === '待布展' && ex.status === '筹备中' && !ex.frozen"
            link
            type="danger"
            size="small"
            @click="removePlanned(row)"
          >
            移出清单
          </el-button>
          <el-button
            v-if="row.status === '待布展' && ex.status !== '已结束'"
            link
            type="primary"
            size="small"
            @click="openMount(row)"
          >
            布展验收
          </el-button>
          <el-button
            v-if="row.status === '已布展'"
            link
            type="warning"
            size="small"
            @click="openDismount(row)"
          >
            撤展验收
          </el-button>
          <el-button
            v-if="row.mount_anomaly && !row.mount_anomaly_resolved"
            link
            type="danger"
            size="small"
            @click="openResolve(row, 'mount')"
          >
            闭环异常
          </el-button>
          <el-button
            v-if="row.dismount_anomaly && !row.dismount_anomaly_resolved"
            link
            type="danger"
            size="small"
            @click="openResolve(row, 'dismount')"
          >
            闭环异常
          </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 变更单 -->
    <el-card v-if="ex.change_orders.length" shadow="never" style="margin-top:14px">
      <template #header>
        <div class="card-head">
          <span>展品变更单({{ ex.change_orders.length }})</span>
          <span class="sub">清单冻结后的增删/替换均须审批留痕,开展中无审批变更单一律禁止替换展品</span>
        </div>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="co in ex.change_orders"
          :key="co.id"
          :type="co.status === '已驳回' ? 'danger' : co.status === '待审批' ? 'warning' : 'success'"
          :timestamp="fmt(co.requested_at)"
        >
          <div class="co-row">
            <el-tag size="small" :type="coTagType(co.status)">{{ co.status }}</el-tag>
            <el-tag size="small" effect="plain" style="margin:0 8px">{{ co.change_type }}</el-tag>
            <strong>变更单 #{{ co.id }}</strong>
            <span class="sub" v-if="co.requested_by"> · 申请人 {{ co.requested_by }}</span>
            <span class="co-actions">
              <el-button
                v-if="co.status === '待审批'"
                link
                type="success"
                size="small"
                @click="openApprove(co, false)"
              >
                批准并执行
              </el-button>
              <el-button
                v-if="co.status === '待审批'"
                link
                type="danger"
                size="small"
                @click="openApprove(co, true)"
              >
                驳回
              </el-button>
            </span>
          </div>
          <div class="co-detail">
            <span v-if="co.add_collection_label">新展品:{{ co.add_collection_label }}</span>
            <span v-if="co.remove_item_label">原展品:{{ co.remove_item_label }}</span>
            <span v-if="co.display_location">展位:{{ co.display_location }}</span>
          </div>
          <p class="co-reason" v-if="co.reason">事由:{{ co.reason }}</p>
          <div class="sub" v-if="co.approved_at">
            {{ co.status === '已驳回' ? '驳回' : '审批' }}:{{ co.approved_by }} · {{ fmt(co.approved_at) }}
            <template v-if="co.approval_note"> · {{ co.approval_note }}</template>
          </div>
          <div class="sub" v-if="co.executed_at">已执行:{{ fmt(co.executed_at) }}(新展品待现场布展验收)</div>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- 加入清单对话框 -->
    <el-dialog v-model="planDialog" title="加入展品清单(登记展位与安装计划)" width="560px">
      <el-alert
        title="此时仅登记清单与安装计划,藏品不出库;布展时再做现场验收。"
        type="info"
        :closable="false"
        style="margin-bottom:12px"
      />
      <el-form :model="planForm" label-width="96px">
        <el-form-item label="选择藏品" required>
          <el-select v-model="planForm.collection_id" filterable style="width:100%" placeholder="仅显示在库藏品">
            <el-option
              v-for="c in candidates"
              :key="c.id"
              :label="`${c.accession_no} ${c.name}`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="展位">
          <el-input v-model="planForm.display_location" placeholder="如 独立展柜 C-01" />
        </el-form-item>
        <el-form-item label="安装计划">
          <el-input v-model="planForm.install_plan_note" type="textarea" :rows="2"
            placeholder="展具、照度、固定方式、注意事项等" />
        </el-form-item>
        <el-form-item label="计划布展日期">
          <el-date-picker v-model="planForm.planned_mount_date" type="date"
            value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialog = false">取消</el-button>
        <el-button type="primary" @click="submitPlan">加入清单</el-button>
      </template>
    </el-dialog>

    <!-- 布展验收对话框 -->
    <el-dialog v-model="mountDialog" title="布展现场验收" width="560px">
      <p style="margin-top:0">
        展品:
        <strong>{{ mountTarget?.accession_no }} {{ mountTarget?.collection_name }}</strong>
        <span class="sub">({{ mountTarget?.display_location }})</span>
      </p>
      <el-form :model="mountForm" label-width="96px">
        <el-form-item label="现场验收人" required>
          <el-input v-model="mountForm.acceptor" placeholder="如 陈列部·张三" />
        </el-form-item>
        <el-form-item label="照片说明">
          <el-input v-model="mountForm.photo_note" type="textarea" :rows="2"
            placeholder="现场照片数量、拍摄部位、存档编号等" />
        </el-form-item>
        <el-form-item label="异常项">
          <el-input v-model="mountForm.anomaly" type="textarea" :rows="3"
            placeholder="无异常可留空;有异常请详细描述,将持续跟踪至闭环" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mountDialog = false">取消</el-button>
        <el-button type="primary" @click="submitMount">完成布展验收</el-button>
      </template>
    </el-dialog>

    <!-- 撤展验收对话框 -->
    <el-dialog v-model="dismountDialog" title="撤展现场验收" width="560px">
      <p style="margin-top:0">
        展品:
        <strong>{{ dismountTarget?.accession_no }} {{ dismountTarget?.collection_name }}</strong>
      </p>
      <el-form :model="dismountForm" label-width="96px">
        <el-form-item label="现场验收人" required>
          <el-input v-model="dismountForm.acceptor" placeholder="如 保管部·李四" />
        </el-form-item>
        <el-form-item label="照片说明">
          <el-input v-model="dismountForm.photo_note" type="textarea" :rows="2"
            placeholder="撤展状况、包装过程、归库照片等" />
        </el-form-item>
        <el-form-item label="异常项">
          <el-input v-model="dismountForm.anomaly" type="textarea" :rows="3"
            placeholder="如 状况变化、包装损坏等;将持续跟踪至闭环" />
        </el-form-item>
        <el-form-item label="归库位置">
          <el-select v-model="dismountForm.return_location_id" clearable filterable style="width:100%"
            placeholder="不选则登记为出库中">
            <el-option
              v-for="l in storageLocations"
              :key="l.id"
              :label="`${l.code} ${l.name}`"
              :value="l.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dismountDialog = false">取消</el-button>
        <el-button type="warning" @click="submitDismount">完成撤展验收</el-button>
      </template>
    </el-dialog>

    <!-- 异常闭环对话框 -->
    <el-dialog v-model="resolveDialog" :title="resolveTarget.phase === 'mount' ? '闭环布展异常' : '闭环撤展异常'"
      width="500px">
      <el-alert
        :title="resolveTarget.phase === 'mount'
          ? resolveTarget.item?.mount_anomaly
          : resolveTarget.item?.dismount_anomaly"
        type="error"
        :closable="false"
        style="margin-bottom:12px"
      />
      <el-form :model="resolveForm" label-width="96px">
        <el-form-item label="处理人" required>
          <el-input v-model="resolveForm.resolved_by" />
        </el-form-item>
        <el-form-item label="处理说明">
          <el-input v-model="resolveForm.note" type="textarea" :rows="3"
            placeholder="原因分析与处理结果,将追加到异常记录中" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveDialog = false">取消</el-button>
        <el-button type="primary" @click="submitResolve">确认闭环</el-button>
      </template>
    </el-dialog>

    <!-- 变更单对话框 -->
    <el-dialog v-model="coDialog" title="提交展品变更单" width="600px">
      <el-alert
        title="清单已冻结:新增/撤除/替换展品均须审批。开展中未经审批的变更单,不允许替换展品。"
        type="warning"
        :closable="false"
        style="margin-bottom:12px"
      />
      <el-form :model="coForm" label-width="110px">
        <el-form-item label="变更类型" required>
          <el-radio-group v-model="coForm.change_type">
            <el-radio-button value="新增">新增展品</el-radio-button>
            <el-radio-button value="撤除">撤除展品</el-radio-button>
            <el-radio-button value="替换">替换展品</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="['新增', '替换'].includes(coForm.change_type)" label="新展品" required>
          <el-select v-model="coForm.add_collection_id" filterable style="width:100%" placeholder="选择在库藏品">
            <el-option
              v-for="c in candidates"
              :key="c.id"
              :label="`${c.accession_no} ${c.name}`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="['撤除', '替换'].includes(coForm.change_type)" label="原展品" required>
          <el-select v-model="coForm.remove_item_id" filterable style="width:100%" placeholder="选择清单中的展品">
            <el-option
              v-for="i in removableItems"
              :key="i.id"
              :label="`${i.accession_no} ${i.collection_name}(${i.status})`"
              :value="i.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="['新增', '替换'].includes(coForm.change_type)" label="展位">
          <el-input v-model="coForm.display_location" />
        </el-form-item>
        <el-form-item v-if="['新增', '替换'].includes(coForm.change_type)" label="安装计划">
          <el-input v-model="coForm.install_plan_note" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item v-if="['新增', '替换'].includes(coForm.change_type)" label="计划布展日期">
          <el-date-picker v-model="coForm.planned_mount_date" type="date"
            value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="变更事由" required>
          <el-input v-model="coForm.reason" type="textarea" :rows="3"
            placeholder="变更原因与依据,供审批人判断" />
        </el-form-item>
        <el-form-item label="申请人">
          <el-input v-model="coForm.requested_by" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="coDialog = false">取消</el-button>
        <el-button type="primary" @click="submitCO">提交审批</el-button>
      </template>
    </el-dialog>

    <!-- 审批对话框 -->
    <el-dialog
      v-model="approveDialog"
      :title="approveForm.reject ? '驳回变更单' : '批准并执行变更单'"
      width="500px"
    >
      <el-form :model="approveForm" label-width="80px">
        <el-form-item label="审批人" required>
          <el-input v-model="approveForm.approved_by" placeholder="如 馆长 / 策展委员会" />
        </el-form-item>
        <el-form-item label="审批意见">
          <el-input v-model="approveForm.approval_note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approveDialog = false">取消</el-button>
        <el-button :type="approveForm.reject ? 'danger' : 'success'" @click="submitApprove">
          {{ approveForm.reject ? '确认驳回' : '确认批准并执行' }}
        </el-button>
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
  flex-wrap: wrap;
  gap: 2px;
}
.meta-line {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-top: 10px;
  color: #606266;
  font-size: 13px;
}
.desc {
  color: #606266;
  font-size: 13px;
  margin: 10px 0 0;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.card-head .sub {
  font-weight: 400;
  color: #909399;
  font-size: 12px;
}
.sub {
  color: #909399;
  font-size: 12px;
}
.link {
  color: #409eff;
  text-decoration: none;
}
.anomaly-text {
  color: #f56c6c;
  font-size: 12px;
  margin-top: 2px;
}
.anomaly-done {
  color: #67c23a;
  font-size: 12px;
  margin-top: 2px;
}
:deep(.anomaly-row) {
  background-color: #fef0f0;
}
.co-row {
  display: flex;
  align-items: center;
}
.co-actions {
  margin-left: auto;
}
.co-detail {
  display: flex;
  gap: 16px;
  margin-top: 6px;
  font-size: 13px;
  color: #606266;
}
.co-reason {
  margin: 4px 0;
  font-size: 13px;
  color: #606266;
}
</style>
