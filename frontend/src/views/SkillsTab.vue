<template>
  <div>
    <n-space justify="space-between" style="margin-bottom: 16px;">
      <n-input v-model:value="query" placeholder="Semantic search..." clearable style="width: 300px;" @keyup.enter="search" />
      <n-button @click="showUpload = true">Upload SKILL.md</n-button>
    </n-space>

    <n-spin :show="loading">
      <n-table v-if="skills.length" :bordered="false" size="small">
        <thead><tr><th>Name</th><th>Description</th><th>Version</th><th>Similarity</th></tr></thead>
        <tbody>
          <tr v-for="s in skills" :key="s.id">
            <td><n-text strong>{{ s.name }}</n-text></td>
            <td>{{ s.description }}</td>
            <td>{{ s.version }}</td>
            <td>{{ s.similarity != null ? s.similarity.toFixed(2) : '—' }}</td>
          </tr>
        </tbody>
      </n-table>
      <n-empty v-if="!loading && skills.length === 0" description="No skills found" />
    </n-spin>

    <n-modal v-model:show="showUpload" preset="card" title="Upload SKILL.md" style="width: 600px;">
      <n-input v-model:value="skillContent" type="textarea" :rows="12" placeholder="Paste SKILL.md content here..." />
      <template #footer>
        <n-space justify="end">
          <n-button @click="showUpload = false">Cancel</n-button>
          <n-button type="primary" :loading="uploading" @click="upload">Upload</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getSkills, searchSkills, uploadSkill } from '../api.js'
import { useMessage } from 'naive-ui'

const message = useMessage()
const query = ref('')
const skills = ref([])
const loading = ref(false)
const showUpload = ref(false)
const skillContent = ref('')
const uploading = ref(false)

async function load() {
  loading.value = true
  try { skills.value = ((await getSkills()).skills || []) }
  catch (e) { message.error('Failed to load skills') }
  finally { loading.value = false }
}

async function search() {
  if (!query.value) return load()
  loading.value = true
  try { skills.value = ((await searchSkills(query.value)).results || []) }
  catch (e) { message.error('Search failed') }
  finally { loading.value = false }
}

async function upload() {
  if (!skillContent.value) return
  uploading.value = true
  try {
    const result = await uploadSkill(skillContent.value)
    if (result.status === 'rejected') message.warning(result.message)
    else message.success('Skill uploaded')
    showUpload.value = false
    skillContent.value = ''
    load()
  } catch (e) { message.error('Upload failed') }
  finally { uploading.value = false }
}

onMounted(load)
</script>
