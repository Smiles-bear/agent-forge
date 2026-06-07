<template>
  <n-card :bordered="true" hoverable>
    <template #header>
      <n-space align="center">
        <n-tag :type="reliabilityColor" size="small" round>{{ reliabilityLabel }}</n-tag>
        <n-text strong>{{ agent.name }}</n-text>
      </n-space>
    </template>
    <n-space vertical size="small">
      <n-space wrap :size="4">
        <n-tag v-for="t in (agent.tech_stack || [])" :key="t" size="tiny" :bordered="false">{{ t }}</n-tag>
      </n-space>
      <n-space wrap :size="4">
        <n-tag v-for="t in (agent.task_types || [])" :key="t" size="tiny" type="info" :bordered="false">{{ t }}</n-tag>
      </n-space>
      <n-text depth="3" style="font-size: 12px;">
        {{ (agent.domains || []).join(', ') || '—' }} · {{ agent.difficulty || 'medium' }}
      </n-text>
    </n-space>
    <template #action>
      <n-space>
        <n-button size="small" @click="$emit('view', agent.id)">View</n-button>
        <n-button size="small" @click="$emit('reverify', agent.id)">Re-verify</n-button>
      </n-space>
    </template>
  </n-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ agent: Object })
defineEmits(['view', 'reverify'])

const reliabilityColor = computed(() => {
  const r = props.agent.reliability_score
  if (r == null) return 'default'
  if (r > 0.7) return 'success'
  if (r > 0.3) return 'warning'
  return 'error'
})

const reliabilityLabel = computed(() => {
  const r = props.agent.reliability_score
  return r != null ? `reliability: ${r}` : 'unverified'
})
</script>
