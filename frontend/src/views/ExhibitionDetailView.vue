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
const locations = ref([])
const allCollections = ref([])

const statusType = { 筹备中: 'info', 开展中: 'primary', 已结束: 'success' }
const itemStatusType = { 待布展: 'warning', 已布展: 'primary', 已撤展: 'success' }
const coStatusType = { 待审批: 'warning', 已批准: 'primary', 已驳回: 'danger', 已执行: 'success' }

const locked = computed(() => ex.value && (ex.value.list_frozen || ex.value.status === '开展中'))
const canDirectEdit = computed(() => ex.value && ex.value.status === '筹备中' && !ex.value.list_frozen)
const openExceptions = computed(() => {
  if (!ex.value) return []
  const rows = []
  for (const it of ex.value.items) {
    for (const e of it.exceptions || []) {
      if (!e.resolved) rows.push({ ...e, collection_name: it.collection_name, accession_no: it.accession_no })
    }
  }
  return rows.sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
})

function fmt(dt) {
  return dt ? dt.replace('T', ' ').slice(0, 16) : '—'
}

async function load() {
  loading.value = true
  try {
    ex.value = await exhibitionApi.get(id)
  } finally {
    loading.value = false
  }
}

// ---------- 基本信息 / 安装计划 ----------
const editDialog = ref(false)
const editForm = reactive({ title: '', venue: '', start_date: '', end_date: '', curator: '', description: '', install_plan: '' })

function openEdit() {
  Object.assign(editForm, {
    title: ex.value.title,
    venue: ex.value.venue,
    start_date: ex.value.start_date,
    end_date: ex.value.end_date,
    curator: ex.value.curator || '',
    description: ex.value.description || '',
    install_plan: ex.value.install_plan || '',
  })
  editDialog.value = true
}

async function submitEdit() {
  if (editForm.end_date <= editForm.start_date) {
    ElMessage.warning('结束日期必须晚于开始日期')
    return
  }
  await exhibitionApi.update(id, { ...editForm })
  ElMessage.success('展览信息已更新')
  editDialog.value = false
  load()
}

// ---------- 冻结 ----------
async function doFreeze() {
  const { value } = await ElMessageBox.prompt(
    '冻结后展品清单只能通过变更单增删,请确认清单与安装计划已审定。',
    '冻结展品清单',
    { confirmButtonText: '确认冻结', cancelButtonText: '取消', inputPlaceholder: '操作人姓名', inputValidator: (v) => !!v || '请填写操作人' }
  )
  await exhibitionApi.freeze(id, value)
  ElMessage.success('展品清单已冻结')
  load()
}

async function doUnfreeze() {
  await ElMessageBox.confirm('解冻后可在筹备阶段直接增删展品,确认解冻?', '解冻清单', { type: 'warning' })
  await exhibitionApi.unfreeze(id)
  ElMessage.success('清单已解冻')
  load()
}

// ---------- 添加展品(未冻结) ----------
const itemDialog = ref(false)
const itemForm = reactive({ collection_id: null, display_location: '', planned_mount_date: '' })

async function openItem() {
  itemForm.collection_id = null
  itemForm.display_location = ''
  itemForm.planned_mount_date = ''
  if (!allCollections.value.length) allCollections.value = await collectionApi.list()
  itemDialog.value = true
}

async function submitItem() {
  if (!itemForm.collection_id) {
    ElMessage.warning('请选择藏品')
    return
  }
  await exhibitionApi.addItem(id, {
    collection_id: itemForm.collection_id,
    display_location: itemForm.display_location || null,
    planned_mount_date: itemForm.planned_mount_date || null,
  })
  ElMessage.success('已加入展品清单(待布展)')
  itemDialog.value = false
  load()
}

async function removeItem(item) {
  await ElMessageBox.confirm(
    `将「${item.collection_name}」从清单移除?(仅待布展条目可直接移除)`,
    '移除展品',
    { type: 'warning' }
  )
  await exhibitionApi.removeItem(id, item.id)
  ElMessage.success('已移出清单')
  load()
}

// ---------- 布展 / 撤展验收 ----------
const acceptDialog = ref(false)
const acceptMode = ref('mount') // mount | dismount
const acceptTarget = ref(null)
const acceptForm = reactive({ acceptor: '', return_location_id: null, photo_notes: [], exceptions: [] })

function openAccept(item, mode) {
  acceptTarget.value = item
  acceptMode.value = mode
  acceptForm.acceptor = ''
  acceptForm.return_location_id = null
  acceptForm.photo_notes = []
  acceptForm.exceptions = []
  acceptDialog.value = true
}

async function submitAccept() {
  if (!acceptForm.acceptor) {
    ElMessage.warning('请填写现场验收人')
    return
  }
  const payload = {
    acceptor: acceptForm.acceptor,
    photo_notes: acceptForm.photo_notes.filter((s) => s && s.trim()),
    exceptions: acceptForm.exceptions.filter((s) => s && s.trim()),
  }
  if (acceptMode.value === 'mount') {
    await exhibitionApi.mount(id, acceptTarget.value.id, payload)
    ElMessage.success('布展验收完成,藏品状态更新为「展陈中」')
  } else {
    await exhibitionApi.dismount(id, acceptTarget.value.id, {
      ...payload,
      return_location_id: acceptForm.return_location_id,
    })
    ElMessage.success('撤展验收完成,藏品已登记归库')
  }
  acceptDialog.value = false
  load()
}

// ---------- 异常 ----------
const excDialog = ref(false)
const excTarget = ref(null)
const excForm = reactive({ phase: '布展', note: '', created_by: '' })

function openException(item) {
  excTarget.value = item
  excForm.phase = item.status === '已撤展' ? '撤展' : '布展'
  excForm.note = ''
  excForm.created_by = ''
  excDialog.value = true
}

async function submitException() {
  if (!excForm.note.trim()) {
    ElMessage.warning('请填写异常内容')
    return
  }
  await exhibitionApi.addException(id, excTarget.value.id, { ...excForm })
  ElMessage.success('异常已登记,解决前将持续提示')
  excDialog.value = false
  load()
}

const resolveDialog = ref(false)
const resolveTarget = ref(null)
const resolveForm = reactive({ resolved_by: '', resolve_note: '' })

function openResolve(exc) {
  resolveTarget.value = exc
  resolveForm.resolved_by = ''
  resolveForm.resolve_note = ''
  resolveDialog.value = true
}

async function submitResolve() {
  if (!resolveForm.resolved_by) {
    ElMessage.warning('请填写处理人')
    return
  }
  await exhibitionApi.resolveException(resolveTarget.value.id, { ...resolveForm })
  ElMessage.success('异常已标记解决')
  resolveDialog.value = false
  load()
}

// ---------- 变更单 ----------
const coDialog = ref(false)
const coForm = reactive({
  order_type: '增展',
  remove_item_id: null,
  add_collection_id: null,
  display_location: '',
  reason: '',
  applicant: '',
})

const removableItems = computed(() =>
  (ex.value?.items || []).filter((i) => i.status !== '已撤展')
)

async function openChangeOrder() {
  Object.assign(coForm, {
    order_type: '增展',
    remove_item_id: null,
    add_collection_id: null,
    display_location: '',
    reason: '',
    applicant: '',
  })
  if (!allCollections.value.length) allCollections.value = await collectionApi.list()
  coDialog.value = true
}

async function submitChangeOrder() {
  if (['撤展', '替换'].includes(coForm.order_type) && !coForm.remove_item_id) {
    ElMessage.warning('请选择要撤下的展品')
    return
  }
  if (['增展', '替换'].includes(coForm.order_type) && !coForm.add_collection_id) {
    ElMessage.warning('请选择要增加的藏品')
    return
  }
  await exhibitionApi.createChangeOrder(id, {
    ...coForm,
    display_location: coForm.display_location || null,
  })
  ElMessage.success('变更单已提交,待审批')
  coDialog.value = false
  load()
}

const approveDialog = ref(false)
const approveMode = ref('approve')
const approveTarget = ref(null)
const approveForm = reactive({ approver: '', note: '' })

function openApprove(co, mode) {
  approveTarget.value = co
  approveMode.value = mode
  approveForm.approver = ''
  approveForm.note = ''
  approveDialog.value = true
}

async function submitApprove() {
  if (!approveForm.approver) {
    ElMessage.warning('请填写审批人')
    return
  }
  const api = approveMode.value === 'approve' ? exhibitionApi.approveChangeOrder : exhibitionApi.rejectChangeOrder
  await api(approveTarget.value.id, { ...approveForm })
  ElMessage.success(approveMode.value === 'approve' ? '变更单已批准' : '变更单已驳回')
  approveDialog.value = false
  load()
}

const executeDialog = ref(false)
const executeTarget = ref(null)
const executeForm = reactive({ acceptor: '', return_location_id: null, photo_notes: [], exceptions: [] })

const executeNeedsAcceptance = computed(() => {
  const co = executeTarget.value
  if (!co || !['撤展', '替换'].includes(co.order_type) || !co.remove_item_id) return false
  const item = (ex.value?.items || []).find((i) => i.id === co.remove_item_id)
  return item && item.status === '已布展'
})

function openExecute(co) {
  executeTarget.value = co
  executeForm.acceptor = ''
  executeForm.return_location_id = null
  executeForm.photo_notes = []
  executeForm.exceptions = []
  executeDialog.value = true
}

async function submitExecute() {
  if (executeNeedsAcceptance.value && !executeForm.acceptor) {
    ElMessage.warning('撤下已布展展品须填写现场验收人')
    return
  }
  await exhibitionApi.executeChangeOrder(executeTarget.value.id, {
    acceptor: executeForm.acceptor || null,
    return_location_id: executeForm.return_location_id,
    photo_notes: executeForm.photo_notes.filter((s) => s && s.trim()),
    exceptions: executeForm.exceptions.filter((s) => s && s.trim()),
  })
  ElMessage.success('变更单已执行')
  executeDialog.value = false
  load()
}

function coSummary(co) {
  if (co.order_type === '增展') return `增展「${co.add_collection_name || co.add_collection_id}」`
  if (co.order_type === '撤展') return `撤下「${co.remove_collection_name || co.remove_collection_id}」`
  return `「${co.remove_collection_name || '?'}」→「${co.add_collection_name || '?'}」`
}

onMounted(async () => {
  locations.value = await locationApi.list({ location_type: '库房' })
  await load()
})
</script>

<template>
  <div class="page-container" v-if="ex" v-loading="loading">
    <el-page-header @back="router.push('/exhibitions')">
      <template #content>
        <div class="head-title">
          <span>{{ ex.title }}</span>
          <el-tag size="small" :type="statusType[ex.status]" style="margin-left:10px">{{ ex.status }}</el-tag>
          <el-tag v-if="ex.list_frozen" size="small" type="danger" effect="plain" style="margin-left:6px">
            清单已冻结
          </el-tag>
          <el-tag v-else-if="ex.status === '开展中'" size="small" type="warning" effect="plain" style="margin-left:6px">
            开展中 · 清单锁定
          </el-tag>
        </div>
      </template>
    </el-page-header>

    <!-- 未解决异常:持续可见 -->
    <el-alert
      v-if="openExceptions.length"
      type="error"
      :closable="false"
      style="margin-top:14px"
      :title="`${openExceptions.length} 条布展/撤展异常未解决`"
    >
      <div v-for="e in openExceptions" :key="e.id" class="exc-line">
        <el-tag size="small" type="danger" effect="plain">{{ e.phase }}异常</el-tag>
        <span class="exc-text">
          {{ e.accession_no }} {{ e.collection_name }}:{{ e.note }}
          <span class="exc-meta">(登记 {{ fmt(e.created_at) }}<template v-if="e.created_by"> · {{ e.created_by }}</template>)</span>
        </span>
        <el-button link type="primary" size="small" @click="openResolve(e)">标记解决</el-button>
      </div>
    </el-alert>

    <!-- 基本信息与安装计划 -->
    <el-card shadow="never" style="margin-top:14px">
      <div class="card-head">
        <b>展览信息与安装计划</b>
        <div>
          <el-button size="small" :icon="'Edit'" @click="openEdit">编辑信息 / 安装计划</el-button>
          <el-button
            v-if="ex.status === '筹备中' && !ex.list_frozen"
            size="small"
            type="danger"
            plain
            :icon="'Lock'"
            @click="doFreeze"
          >
            冻结清单
          </el-button>
          <el-button
            v-else-if="ex.status === '筹备中' && ex.list_frozen"
            size="small"
            type="warning"
            plain
            :icon="'Unlock'"
            @click="doUnfreeze"
          >
            解冻清单
          </el-button>
        </div>
      </div>
      <el-descriptions :column="3" border size="small" style="margin-top:10px">
        <el-descriptions-item label="展厅">{{ ex.venue }}</el-descriptions-item>
        <el-descriptions-item label="展期">{{ ex.start_date }} 至 {{ ex.end_date }}</el-descriptions-item>
        <el-descriptions-item label="策展人">{{ ex.curator || '—' }}</el-descriptions-item>
        <el-descriptions-item label="清单状态" :span="3">
          <template v-if="ex.list_frozen">
            已冻结<template v-if="ex.frozen_by">({{ ex.frozen_by }} · {{ fmt(ex.frozen_at) }})</template>,增删展品须走变更单审批
          </template>
          <template v-else-if="ex.status === '开展中'">展览开展中,清单自动锁定,增删/替换展品须走变更单审批</template>
          <template v-else-if="ex.status === '已结束'">展览已结束</template>
          <template v-else>筹备中,清单未冻结,可直接维护</template>
        </el-descriptions-item>
        <el-descriptions-item label="展览简介" :span="3">{{ ex.description || '—' }}</el-descriptions-item>
        <el-descriptions-item label="安装计划" :span="3">
          <span style="white-space:pre-wrap">{{ ex.install_plan || '尚未编制安装计划' }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 展品清单 -->
    <el-card shadow="never" style="margin-top:14px">
      <div class="card-head">
        <b>展品清单({{ ex.items.length }})</b>
        <div>
          <el-tooltip
            :disabled="canDirectEdit"
            content="清单已冻结或展览已开展,请通过变更单增删展品"
            placement="top"
          >
            <span>
              <el-button
                size="small"
                type="primary"
                :icon="'Plus'"
                :disabled="!canDirectEdit"
                @click="openItem"
              >
                添加展品
              </el-button>
            </span>
          </el-tooltip>
          <el-button
            v-if="ex.status !== '已结束'"
            size="small"
            type="warning"
            plain
            :icon="'Document'"
            @click="openChangeOrder"
          >
            发起变更单
          </el-button>
        </div>
      </div>

      <el-table :data="ex.items" size="small" style="margin-top:10px">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-box">
              <div class="accept-block">
                <b>布展验收</b>
                <template v-if="row.mounted_at">
                  <div>验收人:{{ row.mount_acceptor || '—' }} · 时间:{{ fmt(row.mounted_at) }}</div>
                  <div v-if="row.mount_photo_notes?.length">
                    照片说明:
                    <el-tag v-for="(p, i) in row.mount_photo_notes" :key="i" size="small" effect="plain" style="margin:2px 4px 2px 0">{{ p }}</el-tag>
                  </div>
                </template>
                <span v-else class="muted">尚未布展验收</span>
              </div>
              <div class="accept-block">
                <b>撤展验收</b>
                <template v-if="row.dismounted_at">
                  <div>验收人:{{ row.dismount_acceptor || '—' }} · 时间:{{ fmt(row.dismounted_at) }}</div>
                  <div v-if="row.dismount_photo_notes?.length">
                    照片说明:
                    <el-tag v-for="(p, i) in row.dismount_photo_notes" :key="i" size="small" effect="plain" style="margin:2px 4px 2px 0">{{ p }}</el-tag>
                  </div>
                </template>
                <span v-else class="muted">尚未撤展</span>
              </div>
              <div class="accept-block" v-if="row.exceptions?.length">
                <b>异常项</b>
                <div v-for="e in row.exceptions" :key="e.id" class="exc-line">
                  <el-tag size="small" :type="e.resolved ? 'info' : 'danger'" effect="plain">
                    {{ e.phase }} · {{ e.resolved ? '已解决' : '未解决' }}
                  </el-tag>
                  <span class="exc-text">
                    {{ e.note }}
                    <span class="exc-meta">
                      ({{ fmt(e.created_at) }}<template v-if="e.created_by"> · {{ e.created_by }}</template>)
                    </span>
                    <span v-if="e.resolved" class="exc-meta">
                      → {{ e.resolved_by }} 于 {{ fmt(e.resolved_at) }} 解决<template v-if="e.resolve_note">:{{ e.resolve_note }}</template>
                    </span>
                  </span>
                  <el-button v-if="!e.resolved" link type="primary" size="small" @click="openResolve(e)">标记解决</el-button>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="藏品" min-width="200">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.accession_no }}</el-tag>
            <span style="margin-left:6px">{{ row.collection_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="display_location" label="展位" min-width="150">
          <template #default="{ row }">{{ row.display_location || '—' }}</template>
        </el-table-column>
        <el-table-column label="计划安装" width="110">
          <template #default="{ row }">{{ row.planned_mount_date || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="itemStatusType[row.status]">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="异常" width="80">
          <template #default="{ row }">
            <el-badge v-if="row.open_exception_count" :value="row.open_exception_count" type="danger" />
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250">
          <template #default="{ row }">
            <el-button
              v-if="row.status === '待布展' && ex.status !== '已结束'"
              link type="primary" size="small"
              @click="openAccept(row, 'mount')"
            >
              布展验收
            </el-button>
            <el-button
              v-if="row.status === '已布展'"
              link type="warning" size="small"
              @click="openAccept(row, 'dismount')"
            >
              撤展验收
            </el-button>
            <el-button
              v-if="row.status !== '待布展'"
              link type="danger" size="small"
              @click="openException(row)"
            >
              补录异常
            </el-button>
            <el-button
              v-if="canDirectEdit && row.status === '待布展'"
              link type="danger" size="small"
              @click="removeItem(row)"
            >
              移除
            </el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="展品清单为空" :image-size="60" /></template>
      </el-table>
    </el-card>

    <!-- 变更单 -->
    <el-card shadow="never" style="margin-top:14px">
      <div class="card-head"><b>展品变更单({{ ex.change_orders.length }})</b></div>
      <el-table :data="ex.change_orders" size="small" style="margin-top:10px">
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.order_type === '增展' ? 'success' : row.order_type === '撤展' ? 'warning' : 'primary'" effect="plain">
              {{ row.order_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="变更内容" min-width="220">
          <template #default="{ row }">
            {{ coSummary(row) }}
            <span v-if="row.display_location" class="muted">· 展位 {{ row.display_location }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="事由" min-width="200" show-overflow-tooltip />
        <el-table-column label="申请人" width="90">
          <template #default="{ row }">{{ row.applicant || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="coStatusType[row.status]">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审批" min-width="150">
          <template #default="{ row }">
            <span v-if="row.approver">{{ row.approver }} · {{ fmt(row.approved_at) }}</span>
            <span v-else class="muted">—</span>
            <div v-if="row.approval_note" class="muted" style="font-size:12px">{{ row.approval_note }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <template v-if="row.status === '待审批'">
              <el-button link type="success" size="small" @click="openApprove(row, 'approve')">批准</el-button>
              <el-button link type="danger" size="small" @click="openApprove(row, 'reject')">驳回</el-button>
            </template>
            <el-button
              v-if="row.status === '已批准' && ex.status !== '已结束'"
              link type="primary" size="small"
              @click="openExecute(row)"
            >
              执行变更
            </el-button>
            <span v-if="row.status === '已执行'" class="muted">{{ fmt(row.executed_at) }}</span>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无变更单" :image-size="60" /></template>
      </el-table>
    </el-card>

    <!-- 编辑展览信息 -->
    <el-dialog v-model="editDialog" title="编辑展览信息与安装计划" width="620px">
      <el-form :model="editForm" label-width="92px">
        <el-form-item label="展览名称"><el-input v-model="editForm.title" /></el-form-item>
        <el-form-item label="展厅"><el-input v-model="editForm.venue" /></el-form-item>
        <el-form-item label="展期">
          <el-date-picker
            v-model="editForm.range"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
            :default-value="[editForm.start_date, editForm.end_date]"
            style="width:100%"
            @change="(v) => { editForm.start_date = v?.[0]; editForm.end_date = v?.[1] }"
          />
        </el-form-item>
        <el-form-item label="策展人"><el-input v-model="editForm.curator" /></el-form-item>
        <el-form-item label="展览简介"><el-input v-model="editForm.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="安装计划">
          <el-input
            v-model="editForm.install_plan"
            type="textarea"
            :rows="4"
            placeholder="进场时序、展柜通电调试、吊装与点位安排、验收节奏等"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加展品 -->
    <el-dialog v-model="itemDialog" title="添加展品(筹备阶段 · 清单未冻结)" width="520px">
      <el-form :model="itemForm" label-width="92px">
        <el-form-item label="选择藏品">
          <el-select v-model="itemForm.collection_id" filterable style="width:100%">
            <el-option
              v-for="c in allCollections"
              :key="c.id"
              :label="`${c.accession_no} ${c.name}(${c.status})`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="展位">
          <el-input v-model="itemForm.display_location" placeholder="如 独立展柜 C-01" />
        </el-form-item>
        <el-form-item label="计划安装">
          <el-date-picker v-model="itemForm.planned_mount_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialog = false">取消</el-button>
        <el-button type="primary" @click="submitItem">加入清单</el-button>
      </template>
    </el-dialog>

    <!-- 布展 / 撤展验收 -->
    <el-dialog
      v-model="acceptDialog"
      :title="`${acceptMode === 'mount' ? '布展' : '撤展'}现场验收 · ${acceptTarget?.collection_name || ''}`"
      width="560px"
    >
      <el-form label-width="92px">
        <el-form-item label="现场验收人" required>
          <el-input v-model="acceptForm.acceptor" placeholder="验收人姓名" />
        </el-form-item>
        <el-form-item v-if="acceptMode === 'dismount'" label="归库位置">
          <el-select v-model="acceptForm.return_location_id" clearable filterable style="width:100%" placeholder="不选则登记为出库中">
            <el-option v-for="l in locations" :key="l.id" :label="`${l.code} ${l.name}`" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="照片说明">
          <div class="dyn-list">
            <div v-for="(_, i) in acceptForm.photo_notes" :key="i" class="dyn-row">
              <el-input v-model="acceptForm.photo_notes[i]" placeholder="如 入柜点交照 / 展签核对照" />
              <el-button link type="danger" :icon="'Delete'" @click="acceptForm.photo_notes.splice(i, 1)" />
            </div>
            <el-button link type="primary" :icon="'Plus'" @click="acceptForm.photo_notes.push('')">添加照片说明</el-button>
          </div>
        </el-form-item>
        <el-form-item label="异常项">
          <div class="dyn-list">
            <div v-for="(_, i) in acceptForm.exceptions" :key="i" class="dyn-row">
              <el-input v-model="acceptForm.exceptions[i]" placeholder="现场发现的异常,解决前将持续提示" />
              <el-button link type="danger" :icon="'Delete'" @click="acceptForm.exceptions.splice(i, 1)" />
            </div>
            <el-button link type="warning" :icon="'Plus'" @click="acceptForm.exceptions.push('')">登记异常项</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="acceptDialog = false">取消</el-button>
        <el-button :type="acceptMode === 'mount' ? 'primary' : 'warning'" @click="submitAccept">
          确认{{ acceptMode === 'mount' ? '布展' : '撤展' }}验收
        </el-button>
      </template>
    </el-dialog>

    <!-- 补录异常 -->
    <el-dialog v-model="excDialog" :title="`补录异常 · ${excTarget?.collection_name || ''}`" width="480px">
      <el-form label-width="92px">
        <el-form-item label="异常阶段">
          <el-radio-group v-model="excForm.phase">
            <el-radio-button value="布展">布展</el-radio-button>
            <el-radio-button value="撤展">撤展</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="异常内容" required>
          <el-input v-model="excForm.note" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="登记人">
          <el-input v-model="excForm.created_by" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="excDialog = false">取消</el-button>
        <el-button type="danger" @click="submitException">登记异常</el-button>
      </template>
    </el-dialog>

    <!-- 异常解决 -->
    <el-dialog v-model="resolveDialog" title="标记异常已解决" width="480px">
      <p style="margin-top:0">{{ resolveTarget?.note }}</p>
      <el-form label-width="92px">
        <el-form-item label="处理人" required>
          <el-input v-model="resolveForm.resolved_by" />
        </el-form-item>
        <el-form-item label="处理说明">
          <el-input v-model="resolveForm.resolve_note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveDialog = false">取消</el-button>
        <el-button type="primary" @click="submitResolve">确认解决</el-button>
      </template>
    </el-dialog>

    <!-- 发起变更单 -->
    <el-dialog v-model="coDialog" title="发起展品变更单" width="560px">
      <el-alert
        type="info"
        :closable="false"
        title="清单冻结或展览开展后,增删/替换展品须经变更单审批后执行"
        style="margin-bottom:12px"
      />
      <el-form label-width="92px">
        <el-form-item label="变更类型">
          <el-radio-group v-model="coForm.order_type">
            <el-radio-button value="增展">增展</el-radio-button>
            <el-radio-button value="撤展">撤展</el-radio-button>
            <el-radio-button value="替换">替换</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="['撤展', '替换'].includes(coForm.order_type)" label="撤下展品" required>
          <el-select v-model="coForm.remove_item_id" style="width:100%">
            <el-option
              v-for="it in removableItems"
              :key="it.id"
              :label="`${it.accession_no} ${it.collection_name}(${it.status})`"
              :value="it.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="['增展', '替换'].includes(coForm.order_type)" label="增加藏品" required>
          <el-select v-model="coForm.add_collection_id" filterable style="width:100%">
            <el-option
              v-for="c in allCollections"
              :key="c.id"
              :label="`${c.accession_no} ${c.name}(${c.status})`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="coForm.order_type !== '撤展'" label="展位">
          <el-input v-model="coForm.display_location" placeholder="新展品的计划展位" />
        </el-form-item>
        <el-form-item label="事由">
          <el-input v-model="coForm.reason" type="textarea" :rows="3" placeholder="变更原因与依据" />
        </el-form-item>
        <el-form-item label="申请人">
          <el-input v-model="coForm.applicant" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="coDialog = false">取消</el-button>
        <el-button type="primary" @click="submitChangeOrder">提交审批</el-button>
      </template>
    </el-dialog>

    <!-- 审批 -->
    <el-dialog v-model="approveDialog" :title="approveMode === 'approve' ? '批准变更单' : '驳回变更单'" width="440px">
      <p style="margin-top:0">{{ coSummary(approveTarget || {}) }}</p>
      <el-form label-width="92px">
        <el-form-item label="审批人" required>
          <el-input v-model="approveForm.approver" />
        </el-form-item>
        <el-form-item label="审批意见">
          <el-input v-model="approveForm.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approveDialog = false">取消</el-button>
        <el-button :type="approveMode === 'approve' ? 'success' : 'danger'" @click="submitApprove">
          {{ approveMode === 'approve' ? '批准' : '驳回' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 执行变更单 -->
    <el-dialog v-model="executeDialog" title="执行变更单" width="560px">
      <p style="margin-top:0"><b>{{ coSummary(executeTarget || {}) }}</b></p>
      <el-alert
        v-if="executeNeedsAcceptance"
        type="warning"
        :closable="false"
        title="将撤下一件已布展展品,请填写撤展现场验收信息"
        style="margin-bottom:12px"
      />
      <el-form v-if="executeNeedsAcceptance" label-width="92px">
        <el-form-item label="现场验收人" required>
          <el-input v-model="executeForm.acceptor" />
        </el-form-item>
        <el-form-item label="归库位置">
          <el-select v-model="executeForm.return_location_id" clearable filterable style="width:100%" placeholder="不选则登记为出库中">
            <el-option v-for="l in locations" :key="l.id" :label="`${l.code} ${l.name}`" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="照片说明">
          <div class="dyn-list">
            <div v-for="(_, i) in executeForm.photo_notes" :key="i" class="dyn-row">
              <el-input v-model="executeForm.photo_notes[i]" />
              <el-button link type="danger" :icon="'Delete'" @click="executeForm.photo_notes.splice(i, 1)" />
            </div>
            <el-button link type="primary" :icon="'Plus'" @click="executeForm.photo_notes.push('')">添加照片说明</el-button>
          </div>
        </el-form-item>
        <el-form-item label="异常项">
          <div class="dyn-list">
            <div v-for="(_, i) in executeForm.exceptions" :key="i" class="dyn-row">
              <el-input v-model="executeForm.exceptions[i]" />
              <el-button link type="danger" :icon="'Delete'" @click="executeForm.exceptions.splice(i, 1)" />
            </div>
            <el-button link type="warning" :icon="'Plus'" @click="executeForm.exceptions.push('')">登记异常项</el-button>
          </div>
        </el-form-item>
      </el-form>
      <p v-else class="muted">执行后新展品将列入清单(待布展),布展时需单独做现场验收。</p>
      <template #footer>
        <el-button @click="executeDialog = false">取消</el-button>
        <el-button type="primary" @click="submitExecute">确认执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.head-title {
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.expand-box {
  padding: 8px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
}
.accept-block {
  color: #606266;
}
.accept-block b {
  color: #263445;
  margin-right: 8px;
}
.exc-line {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
}
.exc-text {
  flex: 1;
}
.exc-meta {
  color: #909399;
  font-size: 12px;
}
.muted {
  color: #909399;
}
.dyn-list {
  width: 100%;
}
.dyn-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
</style>
