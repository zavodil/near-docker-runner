// src/services/api.js
import { API_URL, MAX_TOKENS } from '../App';

// Send a message to the agent
export const sendMessageToAgent = async (token, messages, agent_name, addDebugLog) => {
  addDebugLog(`Initializing chat with agent: ${agent_name}`);

  const response = await fetch(`${API_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      agent_name: agent_name,
      messages: messages,
      stream: true,
      max_tokens: MAX_TOKENS
    })
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(`HTTP error ${response.status}: ${errorData.detail || response.statusText}`);
  }

  return response;
};

// Process the SSE stream and return a reader and decoder
export const getStreamReader = (response) => {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  return { reader, decoder };
};