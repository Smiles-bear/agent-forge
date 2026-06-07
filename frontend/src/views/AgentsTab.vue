<template>
  <div>
    <n-space justify="space-between" style="margin-bottom: 16px;">
      <n-input v-model:value="search" placeholder="Search agents..." clearable style="width: 300px;" />
      <n-space>
        <n-button type="primary" @click="showRegister = true">Register Agent</n-button>
        <n-button @click="refresh">Refresh</n-button>
      </n-space>
    </n-space>

    <n-spin :show="loading">
      <n-grid v-if="filteredAgents.length" :cols="2" :x-gap="16" :y-gap="16">
        <n-grid-item v-for="agent in filteredAgents" :key="agent.id">
          <AgentCard :agent="agent" @view="openDetail" @reverify="handleReVerify" />
        </n-grid-item>
      </n-grid>
      <n-empty v-if="!loading && filteredAgents.length === 0" description="No agents registered" />
    </n-spin>

    <RegisterAgentModal v-model:show="showRegister" @registered="refresh" />
    <AgentDetailDrawer v-model:show="showDetail" :agent-id="selectedId" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getAgents, reVerifyAgent } from '../api.js'
import { useMessage } from 'naive-ui'
import AgentCard from '../components/AgentCard.vue'
import RegisterAgentModal from '../components/RegisterAgentModal.vue'
import AgentDetailDrawer from '../components/AgentDetailDrawer.vue'

const message = useMessage()
const search = ref('')
const loading = ref(false)
const agents = ref([])
const showRegister = ref(false)
const showDetail = ref(false)
const selectedId = ref(null)

const filteredAgents = computed(() => {
  if (!search.value) return agents.value
  const q = search.value.toLowerCase()
  return agents.value.filter(a =>
    a.name.toLowerCase().includes(q) ||
    (a.tech_stack || []).some(t => t.toLowerCase().includes(q)) ||
    (a.task_types || []).some(t => t.toLowerCase().includes(q))
  )
})

async function refresh() {
  loading.value = true
  try { agents.value = ((await getAgents()).agents || []) }
  catch (e) { message.error('Failed to load agents') }
  finally { loading.value = false }
}

function openDetail(id) { selectedId.value = id; showDetail.value = true }

async function handleReVerify(id) {
  try {
    await reVerifyAgent(id)
    message.success('Verification started')
    setTimeout(refresh, 3000)
  } catch (e) { message.error('Re-verify failed') }
}

onMounted(refresh)
</script>
