import axios from 'axios';

const API = axios.create({ baseURL: 'http://localhost:8000/api' });

export const createGuestUser = () => API.post('/users/guest');
export const registerUser = (data) => API.post('/users/register', data);
export const loginUser = (data) => API.post('/users/login', data);
export const uploadTrack = (formData) => API.post('/tracks/upload', formData);
export const getUserTracks = (userId) => API.get(`/tracks/user/${userId}`);
export const getTrack = (trackId) => API.get(`/tracks/${trackId}`);
export const analyzeTrack = (trackId) => API.post(`/analysis/analyze/${trackId}`);
export const getAnalysis = (trackId) => API.get(`/analysis/${trackId}`);
export const getAudioUrl = (trackId) => `http://localhost:8000/api/tracks/${trackId}/audio`;

// search and filter tracks
export const searchTracks = (userId, params) => API.get(`/tracks/user/${userId}`, { params });

// export library as CSV
export const exportCSV = (userId) => `http://localhost:8000/api/tracks/user/${userId}/export`;

// playlists
export const createPlaylist = (name, userId) => API.post(`/playlists/create?name=${name}&user_id=${userId}`);
export const getUserPlaylists = (userId) => API.get(`/playlists/user/${userId}`);
export const getPlaylistTracks = (playlistId) => API.get(`/playlists/${playlistId}/tracks`);
export const addToPlaylist = (playlistId, trackId) => API.post(`/playlists/${playlistId}/add/${trackId}`);
export const removeFromPlaylist = (playlistId, trackId) => API.delete(`/playlists/${playlistId}/remove/${trackId}`);
export const deletePlaylist = (playlistId) => API.delete(`/playlists/${playlistId}`);
export const getSharedPlaylist = (token) => API.get(`/playlists/shared/${token}`);

// album artwork image url for a track
export const getArtworkUrl = (trackId) => `http://localhost:8000/api/tracks/${trackId}/artwork`;
