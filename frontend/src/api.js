import axios from 'axios';

const API = axios.create({ baseURL: 'http://localhost:8000/api' });

export const registerUser = (data) => API.post('/users/register', data);
export const loginUser = (data) => API.post('/users/login', data);
export const uploadTrack = (formData) => API.post('/tracks/upload', formData);
export const getUserTracks = (userId) => API.get(`/tracks/user/${userId}`);
export const getTrack = (trackId) => API.get(`/tracks/${trackId}`);
export const analyzeTrack = (trackId) => API.post(`/analysis/analyze/${trackId}`);
export const getAnalysis = (trackId) => API.get(`/analysis/${trackId}`);
