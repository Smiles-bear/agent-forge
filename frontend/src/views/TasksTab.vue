<template>
  <div>
    <n-card title="Task" style="margin-bottom: 16px;">
      <n-input v-model:value="task" type="textarea" :rows="3" placeholder="Describe your task... e.g. 'Review this login code for security issues'" />
      <n-button type="primary" :loading="matching" @click="match" style="margin-top: 12px;">Match Agent</n-button>
    </n-card>

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

    <n-card v-if="result" title="Execute Result">
      <n-text depth="3">Agent: {{ result.agent_name }} · Latency: {{ result.latency_ms }}ms</n-text>
      <n-divider />
      <pre style="white-space: pre-wrap; font-family: monospace; font-size: 13px; max-height: 500px; overflow-y: auto;">{{ result.result }}</pre>
    </n-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { matchAgent, executeAgent } from '../api.js'
import { useMessage } from 'naive-ui'

const message = useMessage()
const task = ref('')
const matching = ref(false)
const matches = ref([])
const hint = ref(null)
const executing = ref(-1)
const result = ref(null)

async function match() {
  if (!task.value) return
  matching.value = true; matches.value = []; result.value = null; hint.value = null
  try {
    const data = await matchAgent(task.value)
    matches.value = data.matches || []
    hint.value = data.hint
  } catch (e) { message.error('Match failed') }
  finally { matching.value = false }
}

async function execute(agentId, idx) {
  executing.value = idx; result.value = null
  try { result.value = await executeAgent(agentId, task.value) }
  catch (e) { message.error('Execute failed') }
  finally { executing.value = -1 }
}
</script>
