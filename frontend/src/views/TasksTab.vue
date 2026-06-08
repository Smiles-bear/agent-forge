<template>
  <div>
    <n-card title="Task" style="margin-bottom: 16px;">
      <n-input v-model:value="task" type="textarea" :rows="3" placeholder="Describe your task... e.g. 'add a login feature to the web app'" />
      <n-space style="margin-top: 12px;">
        <n-button type="primary" :loading="matching" @click="match">Match Agent</n-button>
        <n-button type="info" :loading="orchestrating" @click="orchestrate">Orchestrate</n-button>
      </n-space>
    </n-card>

    <!-- Orchestrate Plan -->
    <n-card v-if="orchestrateResults.length" title="Orchestration Plan" style="margin-bottom: 16px;">
      <n-tag type="info">{{ summary }}</n-tag>
      <n-space vertical style="margin-top: 12px;" :size="12">
        <n-card v-for="(r, i) in orchestrateResults" :key="i" size="small" :bordered="true">
          <template #header>
            <n-space align="center">
              <n-tag :type="r.status === 'done' ? 'success' : 'error'" size="small">{{ r.status }}</n-tag>
              <n-text>{{ r.sub_task }}</n-text>
            </n-space>
          </template>
          <n-text depth="3">Agent: {{ r.agent_name || 'not matched' }}</n-text>
          <n-collapse v-if="r.result">
            <n-collapse-item title="View result">
              <pre style="white-space: pre-wrap; font-size: 12px; max-height: 200px; overflow-y: auto;">{{ r.result }}</pre>
            </n-collapse-item>
          </n-collapse>
        </n-card>
      </n-space>
    </n-card>

    <!-- Match Results -->
    <n-card v-if="matches.length" title="Match Results" style="margin-bottom: 16px;">
      <n-space vertical>
        <n-card v-for="(m, i) in matches" :key="i" size="small" :bordered="true">
          <n-space align="center" justify="space-between">
            <div>
              <n-text strong>#{{ i + 1 }} {{ m.agent.name }}</n-text>
              <n-text depth="3"> relevance: {{ m.agent.similarity }}</n-text>
              <n-space :size="4" style="margin-top: 4px;">
                <n-tag size="tiny">tech:{{ m.tech_sim || '—' }}</n-tag>
                <n-tag size="tiny">task:{{ m.task_sim || '—' }}</n-tag>
                <n-tag size="tiny">domain:{{ m.domain_sim || '—' }}</n-tag>
                <n-tag size="tiny">diff:{{ m.diff_sim || '—' }}</n-tag>
              </n-space>
              <n-text depth="3" style="font-size: 12px; display: block; margin-top: 4px;">{{ m.match_reason }}</n-text>
            </div>
            <n-button size="small" :loading="executing === i" @click="execute(m.agent.id, i)">Execute</n-button>
          </n-space>
        </n-card>
      </n-space>
      <n-text v-if="hint" depth="3" type="warning" style="margin-top: 8px;">{{ hint }}</n-text>
    </n-card>

    <!-- Execute Result -->
    <n-card v-if="result" title="Execute Result">
      <n-space align="center" justify="space-between">
        <n-text depth="3">Agent: {{ result.agent_name }} · Latency: {{ result.latency_ms }}ms</n-text>
        <n-space>
          <n-button size="small" type="success" :loading="feedbackLoading === 'up'" @click="sendFb('up')">👍</n-button>
          <n-button size="small" type="error" :loading="feedbackLoading === 'down'" @click="sendFb('down')">👎</n-button>
        </n-space>
      </n-space>
      <n-divider />
      <pre style="white-space: pre-wrap; font-family: monospace; font-size: 13px; max-height: 500px; overflow-y: auto;">{{ result.result }}</pre>
    </n-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { matchAgent, executeAgent, orchestrateTask, sendFeedback } from '../api.js'
import { useMessage } from 'naive-ui'

const message = useMessage()
const task = ref('')
const matching = ref(false)
const orchestrating = ref(false)
const matches = ref([])
const hint = ref(null)
const executing = ref(-1)
const result = ref(null)
const lastAgentId = ref(null)
const feedbackLoading = ref(null)
const orchestrateResults = ref([])
const summary = ref('')

async function match() {
  if (!task.value) return
  matching.value = true; matches.value = []; result.value = null; orchestrateResults.value = []
  try {
    const data = await matchAgent(task.value)
    matches.value = data.matches || []
    hint.value = data.hint
  } catch (e) { message.error('Match failed') }
  finally { matching.value = false }
}

async function orchestrate() {
  if (!task.value) return
  orchestrating.value = true; matches.value = []; result.value = null; orchestrateResults.value = []
  try {
    const data = await orchestrateTask(task.value)
    orchestrateResults.value = data.results || []
    summary.value = data.summary
    if (!data.results.length) message.warning('Orchestration produced no results')
  } catch (e) { message.error('Orchestration failed') }
  finally { orchestrating.value = false }
}

async function execute(agentId, idx) {
  executing.value = idx; result.value = null
  try {
    result.value = await executeAgent(agentId, task.value)
    lastAgentId.value = agentId
  } catch (e) { message.error('Execute failed') }
  finally { executing.value = -1 }
}

async function sendFb(rating) {
  if (!lastAgentId.value) return
  feedbackLoading.value = rating
  try {
    const fb = await sendFeedback(lastAgentId.value, rating)
    message.success(`Feedback recorded. Reliability: ${fb.reliability_score}`)
  } catch (e) { message.error('Feedback failed') }
  finally { feedbackLoading.value = null }
}
</script>
