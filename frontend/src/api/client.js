import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const fetchProduction  = (params = {}) => api.get('/production', { params }).then(r => r.data)
export const fetchForecasts   = (params = {}) => api.get('/forecasts',  { params }).then(r => r.data)
export const fetchScores      = ()             => api.get('/scores').then(r => r.data)
export const fetchQuarterly   = (params = {}) => api.get('/quarterly',  { params }).then(r => r.data)
export const fetchRigs        = (params = {}) => api.get('/rigs',       { params }).then(r => r.data)
export const fetchValidation  = ()             => api.get('/validation').then(r => r.data)
export const fetchRegionPresets = ()           => api.get('/region-presets').then(r => r.data)

export const fetchColoradoMonthly    = () => api.get('/colorado/monthly').then(r => r.data)
export const fetchColoradoFormations = () => api.get('/colorado/formations').then(r => r.data)
export const fetchColoradoOperators  = () => api.get('/colorado/operators').then(r => r.data)
export const fetchColoradoDecline    = () => api.get('/colorado/decline').then(r => r.data)

export const postAiChat       = (body) => api.post('/ai/chat', body).then(r => r.data)
export const postWellEcon     = (body) => api.post('/well-economics', body).then(r => r.data)
export const postSensitivity  = (body) => api.post('/sensitivity', body).then(r => r.data)
