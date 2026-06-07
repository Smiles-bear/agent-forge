<template>
  <n-modal v-model:show="showModal" preset="card" title="Register Agent" style="width: 600px;">
    <n-form :model="form" label-placement="left" label-width="100px">
      <n-form-item label="Name" required><n-input v-model:value="form.name" /></n-form-item>
      <n-form-item label="Endpoint" required><n-input v-model:value="form.endpoint" placeholder="http://agent:8001/run" /></n-form-item>
      <n-form-item label="Tech Stack"><n-select v-model:value="form.tech_stack" multiple :options="techOpts" /></n-form-item>
      <n-form-item label="Task Types"><n-select v-model:value="form.task_types" multiple :options="taskOpts" /></n-form-item>
      <n-form-item label="Domains"><n-select v-model:value="form.domains" multiple :options="domainOpts" /></n-form-item>
      <n-form-item label="Difficulty"><n-select v-model:value="form.difficulty" :options="diffOpts" /></n-form-item>
      <n-form-item label="Department"><n-input v-model:value="form.department" placeholder="IT" /></n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="showModal = false">Cancel</n-button>
        <n-button type="primary" :loading="submitting" @click="submit">Register</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed } from 'vue'
import { registerAgent } from '../api.js'
import { useMessage } from 'naive-ui'

const props = defineProps({ show: Boolean })
const emit = defineEmits(['update:show', 'registered'])
const showModal = computed({ get: () => props.show, set: (v) => emit('update:show', v) })

const message = useMessage()
const submitting = ref(false)
const form = ref({
  name: '', endpoint: '', tech_stack: [], task_types: [], domains: [],
  difficulty: 'medium', department: 'IT'
})

const techOpts = 'react vue python typescript go java fastapi flask postgresql redis docker css html tailwind'.split(' ').map(v => ({ label: v, value: v }))
const taskOpts = 'develop review debug refactor test document design deploy'.split(' ').map(v => ({ label: v, value: v }))
const domainOpts = 'frontend backend fullstack devops security data mobile embedded ai_ml'.split(' ').map(v => ({ label: v, value: v }))
const diffOpts = 'easy medium hard'.split(' ').map(v => ({ label: v, value: v }))

async function submit() {
  if (!form.value.name || !form.value.endpoint) { message.warning('Name and endpoint required'); return }
  submitting.value = true
  try {
    const result = await registerAgent({ ...form.value })
    if (result.endpoint_reachable === false) message.warning('Agent registered but endpoint unreachable')
    else message.success('Agent registered')
    showModal.value = false
    emit('registered')
    form.value = { name: '', endpoint: '', tech_stack: [], task_types: [], domains: [], difficulty: 'medium', department: 'IT' }
  } catch (e) { message.error(e.response?.data?.detail || 'Registration failed') }
  finally { submitting.value = false }
}
</script>
