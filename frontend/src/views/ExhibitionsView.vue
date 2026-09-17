<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { exhibitionApi } from '../api'

const router = useRouter()
const rows = ref([])
const loading = ref(false)
const statusFilter = ref('')

const createDialog = ref(false)
const formRef = ref(null)
const form = reactive({
  title: '',
  venue: '',
  start_date: '',
  end_date: '',
  curator: '',
  description: '',
  install_plan: '',
})
const rules = {
  title: [{ required: true, message: '请输入展览名称' }],
  venue: [{ required: true, message: '请输入展厅' }],
  start_date: [{ required: true, message: '请选择开始日期' }],
  end_date: [{ required: true, message: '请选择结束日期' }],
}

async function load() {
  loading.value = true
  try {
    rows.value = await exhibitionApi.list(statusFilter.value || undefined)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, {
    title: '',
    venue: '',
    start_date: '',
    end_date: '',
    curator: '',
    description: '',
    install_plan: '',
  })
  createDialog.value = true
}

async function submitCreate() {
  await formRef.value.validate()
  if (form.end_date <= form.start_date) {
    ElMessage.warning('结束日期必须晚于开始日期')
    return
  }
  await exhibitionApi.create({ ...form })
  ElMessage.success('展览已创建,可进入详情维护展品清单与安装计划')
  createDialog.value = false
  load()
}

function plannedCount(ex) {
  return ex.items.filter((i) => i.status === '待布展').length
}
function mountedCount(ex) {
  return ex.items.filter((i) => i.status === '已布展').length
}

const statusType = { 筹备中: 'info', 开展中: 'primary', 已结束: 'success' }

onMounted(load)
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">展陈管理</h2>
    <p class="page-sub">展览策划、展品清单冻结、布撤展验收与变更单审批</p>

    <el-card shadow="never">
      <div class="toolbar">
        <el-radio-group v-model="statusFilter" @change="load">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="筹备中">筹备中</el-radio-button>
          <el-radio-button label="开展中">开展中</el-radio-button>
          <el-radio-button label="已结束">已结束</el-radio-button>
        </el-radio-group>
        <div class="spacer"></div>
        <el-button type="primary" :icon="'Plus'" @click="openCreate">策划新展</el-button>
      </div>

      <el-row :gutter="14" v-loading="loading">
        <el-col v-for="ex in rows" :key="ex.id" :span="8" style="margin-bottom:14px">
          <el-card class="ex-card" shadow="hover">
            <div class="ex-head">
              <div>
                <el-tag size="small" :type="statusType[ex.status]">{{ ex.status }}</el-tag>
                <el-tag
                  v-if="ex.list_frozen"
                  size="small"
                  type="danger"
                  effect="plain"
                  style="margin-left:6px"
                >
                  清单已冻结
                </el-tag>
              </div>
              <el-badge
                v-if="ex.open_exception_count"
                :value="ex.open_exception_count"
                type="danger"
                title="未解决布撤展异常"
              >
                <el-icon :size="18" color="#f56c6c"><WarningFilled /></el-icon>
              </el-badge>
            </div>
            <h3 class="ex-title">{{ ex.title }}</h3>
            <div class="ex-meta">
              <el-icon><Location /></el-icon>{{ ex.venue }}
            </div>
            <div class="ex-meta">
              <el-icon><Calendar /></el-icon>{{ ex.start_date }} 至 {{ ex.end_date }}
            </div>
            <div class="ex-meta" v-if="ex.curator">策展人:{{ ex.curator }}</div>
            <el-divider style="margin:10px 0" />
            <div class="ex-stats">
              <span>展品 {{ ex.items.length }} 件</span>
              <span v-if="plannedCount(ex)">待布展 {{ plannedCount(ex) }}</span>
              <span v-if="mountedCount(ex)">在展 {{ mountedCount(ex) }}</span>
              <span v-if="ex.open_exception_count" class="exc-text">
                未解决异常 {{ ex.open_exception_count }}
              </span>
            </div>
            <div class="ex-actions">
              <el-button
                size="small"
                type="primary"
                plain
                :icon="'Tickets'"
                @click="router.push(`/exhibitions/${ex.id}`)"
              >
                清单 / 布撤展管理
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <el-dialog v-model="createDialog" title="策划新展" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="92px">
        <el-form-item label="展览名称" prop="title">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="展厅" prop="venue">
          <el-input v-model="form.venue" placeholder="如 第一展厅 / 临时展厅" />
        </el-form-item>
        <el-form-item label="展期">
          <el-date-picker
            v-model="form.range"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
            style="width:100%"
            @change="(v) => { form.start_date = v?.[0]; form.end_date = v?.[1] }"
          />
        </el-form-item>
        <el-form-item label="策展人">
          <el-input v-model="form.curator" />
        </el-form-item>
        <el-form-item label="展览简介">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="安装计划">
          <el-input
            v-model="form.install_plan"
            type="textarea"
            :rows="3"
            placeholder="进场时序、展柜调试、吊装与点位安排等(可在详情页继续完善)"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ex-card {
  min-height: 230px;
}
.ex-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ex-title {
  font-size: 16px;
  margin: 10px 0 6px;
  color: #263445;
}
.ex-meta {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 13px;
  color: #606266;
  margin-top: 4px;
}
.ex-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
}
.exc-text {
  color: #f56c6c;
}
.ex-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
