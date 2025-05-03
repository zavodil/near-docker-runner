// src/services/auth.js
import { API_URL } from '../App';

// Login user and get token
export const loginUser = async (username, password) => {
  const response = await fetch(`${API_URL}/api/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      username,
      password,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || data.message || 'Login failed');
  }

  return data;
};

// Check server health
export const checkServerHealth = async (addDebugLog) => {
  try {
    const response = await fetch(`${API_URL}/api/health`);
    const data = await response.json();

    if (response.ok) {
      addDebugLog(`Server is healthy: ${data.status}`);
    }

    return data;
  } catch (error) {
    addDebugLog(`Health check error: ${error.message}`);
    throw error;
  }
};