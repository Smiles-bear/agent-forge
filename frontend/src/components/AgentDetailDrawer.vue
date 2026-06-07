<template>
  <n-drawer v-model:show="showDrawer" width="500">
    <n-drawer-content v-if="agent" :title="agent.name">
      <n-space vertical size="large">
        <n-descriptions bordered :column="2" size="small">
          <n-descriptions-item label="Reliability">{{ agent.reliability_score ?? 'N/A' }}</n-descriptions-item>
          <n-descriptions-item label="Difficulty">{{ agent.difficulty }}</n-descriptions-item>
          <n-descriptions-item label="Department">{{ agent.department }}</n-descriptions-item>
          <n-descriptions-item label="Protocol">{{ agent.protocol }}</n-descriptions-item>
          <n-descriptions-item label="Endpoint" :span="2">{{ agent.endpoint }}</n-descriptions-item>
        </n-descriptions>

        <div>
          <n-text strong>Verification Status: </n-text>
          <n-tag :type="vStatusType">{{ vStatus?.status || 'loading...' }}</n-tag>
        </div>

        <n-table v-if="vStatus?.results?.length" :bordered="false" size="small">
          <thead><tr><th>Test</th><th>Score</th><th>Steps</th></tr></thead>
          <tbody>
            <tr v-for="r in vStatus.results" :key="r.test_index">
              <td>#{{ r.test_index }}</td>
              <td>{{ r.overall }}</td>
              <td>{{ JSON.stringify(r.steps) }}</td>
            </tr>
          </tbody>
        </n-table>
      </n-space>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { getAgent, getVerification } from '../api.js'

const props = defineProps({ show: Boolean, agentId: Number })
const emit = defineEmits(['update:show'])
const showDrawer = computed({ get: () => props.show, set: (v) => emit('update:show', v) })

const agent = ref(null)
const vStatus = ref(null)

const vStatusType = computed(() => {
  if (!vStatus.value) return 'default'
  if (vStatus.value.status === 'completed') return 'success'
  if (vStatus.value.status === 'in_progress') return 'warning'
  return 'default'
})

watch(() => props.agentId, async (id) => {
  if (!id) return
  try { agent.value = await getAgent(id) } catch (e) { agent.value = null }
  try { vStatus.value = await getVerification(id) } catch (e) { vStatus.value = null }
})
</script>
