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
})
const rules = {
  title: [{ required: true, message: '请输入展览名称' }],
  venue: [{ required: true, message: '请输入展厅' }],
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
  })
  createDialog.value = true
}

async function submitCreate() {
  await formRef.value.validate()
  if (!form.start_date || !form.end_date || form.end_date <= form.start_date) {
    ElMessage.warning('请选择有效的展期(结束日期须晚于开始日期)')
    return
  }
  const ex = await exhibitionApi.create({ ...form })
  ElMessage.success('展览已创建,请在详情中维护展品清单与安装计划')
  createDialog.value = false
  router.push(`/exhibitions/${ex.id}`)
}

function counts(items) {
  return {
    planned: items.filter((i) => i.status === '待布展').length,
    mounted: items.filter((i) => i.status === '已布展').length,
    dismounted: items.filter((i) => i.status === '已撤展').length,
  }
}

const statusType = { 筹备中: 'info', 开展中: 'primary', 已结束: 'success' }

onMounted(load)
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">展陈管理</h2>
    <p class="page-sub">
      维护可冻结的展品清单与展位安装计划,布展/撤展现场验收留痕,异常项持续跟踪至闭环
    </p>

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
          <el-card
            class="ex-card"
            shadow="hover"
            @click="router.push(`/exhibitions/${ex.id}`)"
          >
            <div class="ex-head">
              <div>
                <el-tag size="small" :type="statusType[ex.status]">{{ ex.status }}</el-tag>
                <el-tag
                  v-if="ex.frozen"
                  size="small"
                  type="warning"
                  effect="dark"
                  style="margin-left:6px"
                >
                  清单已冻结
                </el-tag>
                <el-tag v-else size="small" type="info" effect="plain" style="margin-left:6px">
                  清单编制中
                </el-tag>
              </div>
              <el-tag
                v-if="ex.open_anomaly_count"
                size="small"
                type="danger"
                effect="dark"
              >
                {{ ex.open_anomaly_count }} 项异常未闭环
              </el-tag>
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
            <div class="counts">
              <span>展品 {{ ex.items.length }} 件</span>
              <el-tag size="small" type="info" effect="plain">
                待布展 {{ counts(ex.items).planned }}
              </el-tag>
              <el-tag size="small" type="primary" effect="plain">
                已布展 {{ counts(ex.items).mounted }}
              </el-tag>
              <el-tag size="small" type="success" effect="plain">
                已撤展 {{ counts(ex.items).dismounted }}
              </el-tag>
            </div>
            <div class="enter">
              <el-button link type="primary" size="small">
                进入展览详情<el-icon style="margin-left:2px"><ArrowRight /></el-icon>
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
        <el-form-item label="展期" required>
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
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建并维护清单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ex-card {
  cursor: pointer;
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
.counts {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: #606266;
  flex-wrap: wrap;
}
.enter {
  margin-top: 8px;
  text-align: right;
}
</style>
