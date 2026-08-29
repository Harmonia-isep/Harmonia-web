import axios from 'axios';

// Where the backend lives. In production this is set via VITE_API_URL at build
// time. Locally falls back to localhost.
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const API = axios.create({ baseURL: `${BASE}/api` });

// Harmonia is local-first and single-user: there are no accounts, so nothing
// here takes a user id.

// tracks
export const uploadTrack = (formData) => API.post('/tracks/upload', formData);
export const getTracks = (params) => API.get('/tracks/', { params });
export const getTrack = (trackId) => API.get(`/tracks/${trackId}`);
export const analyzeTrack = (trackId) => API.post(`/analysis/analyze/${trackId}`);
export const getAnalysis = (trackId) => API.get(`/analysis/${trackId}`);
export const getAudioUrl = (trackId) => `${BASE}/api/tracks/${trackId}/audio`;

// export library as CSV
export const exportCSV = () => `${BASE}/api/tracks/export`;

// playlists
export const createPlaylist = (name) => API.post(`/playlists/create?name=${encodeURIComponent(name)}`);
export const getPlaylists = () => API.get('/playlists/');
export const getPlaylistTracks = (playlistId) => API.get(`/playlists/${playlistId}/tracks`);
export const addToPlaylist = (playlistId, trackId) => API.post(`/playlists/${playlistId}/add/${trackId}`);
export const removeFromPlaylist = (playlistId, trackId) => API.delete(`/playlists/${playlistId}/remove/${trackId}`);
export const deletePlaylist = (playlistId) => API.delete(`/playlists/${playlistId}`);
export const getSharedPlaylist = (token) => API.get(`/playlists/shared/${token}`);

// album artwork image url for a track
export const getArtworkUrl = (trackId) => `${BASE}/api/tracks/${trackId}/artwork`;

// reorder tracks in a playlist - pass array of track ids in new order
export const reorderPlaylist = (playlistId, trackIds) => API.put(`/playlists/${playlistId}/reorder`, trackIds);

// frequency spectrum data for a track's FFT chart
export const getSpectrum = (trackId) => API.get(`/analysis/${trackId}/spectrum`);

// harmonic mixing recommendations for a track
export const getRecommendations = (trackId) => API.get(`/analysis/${trackId}/recommendations`);
