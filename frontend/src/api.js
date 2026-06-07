import axios from 'axios'
import { ref, watch } from 'vue'

const api = axios.create({ baseURL: '/api/v1' })

export const project = ref('it-department')

// Watch project changes to rebuild api calls? No — each function reads project.value at call time.

// Agents
export function getAgents() { return api.get(`/${project.value}/agents`).then(r => r.data) }
export function getAgent(id) { return api.get(`/${project.value}/agents/${id}`).then(r => r.data) }
export function registerAgent(data) { return api.post(`/${project.value}/agents/register`, data).then(r => r.data) }
export function matchAgent(task, topK = 3) { return api.post(`/${project.value}/agents/match`, { task, top_k: topK }).then(r => r.data) }
export function executeAgent(id, task, context) { return api.post(`/${project.value}/agents/${id}/execute`, { task, context }).then(r => r.data) }
export function reVerifyAgent(id) { return api.post(`/${project.value}/agents/${id}/verify`).then(r => r.data) }
export function getVerification(id) { return api.get(`/${project.value}/agents/${id}/verification`).then(r => r.data) }

// Skills
export function getSkills() { return api.get(`/${project.value}/skills`).then(r => r.data) }
export function searchSkills(q) { return api.get(`/${project.value}/skills/search`, { params: { q } }).then(r => r.data) }
export function uploadSkill(content) { return api.post(`/${project.value}/skills/upload`, content, { headers: { 'Content-Type': 'text/plain' } }).then(r => r.data) }

// Health
export function getProjectHealth() { return api.get(`/${project.value}/health`).then(r => r.data) }
