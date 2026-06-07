<template>
  <n-message-provider>
    <n-config-provider>
      <div style="max-width: 1200px; margin: 0 auto; padding: 20px;">
        <n-space align="center" justify="space-between" style="margin-bottom: 24px;">
          <n-h1 style="margin: 0; font-size: 28px;">AgentForge</n-h1>
          <n-select v-model:value="project" :options="projectOptions" style="width: 180px;" />
        </n-space>

        <n-tabs v-model:value="activeTab" type="bar" animated>
          <n-tab-pane name="agents" tab="Agents">
            <AgentsTab />
          </n-tab-pane>
          <n-tab-pane name="skills" tab="Skills">
            <SkillsTab />
          </n-tab-pane>
          <n-tab-pane name="tasks" tab="Tasks">
            <TasksTab />
          </n-tab-pane>
        </n-tabs>
      </div>
    </n-config-provider>
  </n-message-provider>
</template>

<script setup>
import { ref, watch } from 'vue'
import { project as apiProject } from './api.js'
import AgentsTab from './views/AgentsTab.vue'
import SkillsTab from './views/SkillsTab.vue'
import TasksTab from './views/TasksTab.vue'

const activeTab = ref('agents')
const project = ref('it-department')
const projectOptions = [
  { label: 'it-department', value: 'it-department' },
  { label: 'engineering', value: 'engineering' },
]

watch(project, (v) => { apiProject.value = v }, { immediate: true })
</script>
