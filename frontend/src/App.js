// src/App.js

import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// Configuration constants
const MAX_TOKENS = 4000;  // Default max tokens
const MAX_MESSAGE_LENGTH = 50000;  // Maximum characters to show in UI
const API_URL = 'http://localhost:5001';

function App() {
  // State for user authentication
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [token, setToken] = useState('');
  const [username, setUsername] = useState('user');
  const [password, setPassword] = useState('password');

  // State for chat
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);

  // Agent selection
  const [selectedAgent, setSelectedAgent] = useState('example_agent');
  const [availableAgents, setAvailableAgents] = useState(['example_agent']);

  // State for debug logs
  const [debugLogs, setDebugLogs] = useState([]);

  // Reference for the message container (for auto-scrolling)
  const messageEndRef = useRef(null);
  const debugEndRef = useRef(null);

  // EventSource reference
  const [eventSource, setEventSource] = useState(null);

  // Reference to track the current response string
  const currentResponseRef = useRef('');

  // Auto-scroll when messages are updated
  useEffect(() => {
    if (messageEndRef.current) {
      messageEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
    if (debugEndRef.current) {
      debugEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, debugLogs]);

  // Cleanup EventSource when component unmounts
  useEffect(() => {
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [eventSource]);

  // Handle login
  const handleLogin = async (e) => {
    e.preventDefault();

    addDebugLog(`Attempting to login as ${username}...`);

    try {
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

      if (response.ok) {
        setToken(data.token);
        setIsLoggedIn(true);
        addDebugLog(`Logged in successfully with token: ${data.token.substring(0, 6)}...`);

        // Check server health and available agents
        checkServerHealth();
      } else {
        addDebugLog(`Login failed: ${data.detail || data.message}`);
      }
    } catch (error) {
      addDebugLog(`Login error: ${error.message}`);
    }
  };

  // Check server health and available agents
  const checkServerHealth = async () => {
    try {
      const response = await fetch(`${API_URL}/api/health`);
      const data = await response.json();

      if (response.ok) {
        addDebugLog(`Server is healthy: ${data.status}`);
      }

      // In a real implementation, you'd fetch available agents here
      // For now, we're using the hardcoded list
    } catch (error) {
      addDebugLog(`Health check error: ${error.message}`);
    }
  };

  // Add a message to the chat
  const addMessage = (role, content) => {
    setMessages(prev => [...prev, { role, content }]);
  };

  // Add a debug log
  const addDebugLog = (log) => {
    const timestamp = new Date().toLocaleTimeString();
    setDebugLogs(prev => [...prev, `[${timestamp}] ${log}`]);
  };

  // Send a message and get streaming response using new endpoint
  const sendMessage = async () => {
    if (!input.trim()) return;

    // Add user message to chat
    addMessage('user', input);
    addDebugLog(`Sending message to agent '${selectedAgent}': ${input.substring(0, 30)}${input.length > 30 ? '...' : ''}`);

    // Clear input field
    const message = input.trim();
    setInput('');

    // Prepare message for API
    const apiMessages = [
      ...messages.map(m => ({ role: m.role, content: m.content })),
      { role: 'user', content: message }
    ];

    // Close existing EventSource
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
    }

    // Reset the current response
    currentResponseRef.current = '';

    // Set loading states
    setIsInitializing(true);

    // Create a temporary message for the assistant's response with loading indicator
    addMessage('assistant', 'Loading...');

    try {
      // Call the new /chat/completions endpoint
      addDebugLog(`Initializing chat with agent: ${selectedAgent}`);

      if (selectedAgent) {
        // Use the new agent-based endpoint
        const response = await fetch(`${API_URL}/chat/completions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            agent_name: selectedAgent,
            messages: apiMessages,
            stream: true,
            max_tokens: MAX_TOKENS
          })
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(`HTTP error ${response.status}: ${errorData.detail || response.statusText}`);
        }

        // Since the response is already streaming, we need to read the SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        // Clear the loading message
        setMessages(prev => {
          const newMessages = [...prev];
          newMessages[newMessages.length - 1].content = '';
          return newMessages;
        });

        // Prepare to start streaming
        setIsStreaming(true);

        // Read the stream
        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            addDebugLog('Stream finished');
            setIsStreaming(false);
            setIsInitializing(false);
            break;
          }

          // Decode the chunk and add it to the buffer
          buffer += decoder.decode(value, { stream: true });

          // Process full SSE messages in the buffer
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || ''; // Keep the last incomplete message in the buffer

          for (const line of lines) {
            if (line.startsWith('data:')) {
              try {
                const eventData = JSON.parse(line.substring(5).trim());

                if (eventData.content) {
                  // Append to our reference string
                  currentResponseRef.current += eventData.content;

                  // Update the message
                  setMessages(prev => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1].content = currentResponseRef.current;
                    return newMessages;
                  });
                }
              } catch (e) {
                addDebugLog(`Error parsing message: ${e.message}`);
              }
            } else if (line.startsWith('event: debug')) {
              const debugData = line.split('\n')[1];
              if (debugData && debugData.startsWith('data:')) {
                addDebugLog(debugData.substring(5).trim());
              }
            } else if (line.startsWith('event: completion')) {
              addDebugLog('Streaming completed');
              setIsStreaming(false);
              setIsInitializing(false);
            } else if (line.startsWith('event: error')) {
              const errorData = line.split('\n')[1];
              if (errorData && errorData.startsWith('data:')) {
                try {
                  const errorObj = JSON.parse(errorData.substring(5).trim());
                  addDebugLog(`Stream error: ${errorObj.error || 'Unknown error'}`);
                } catch (e) {
                  addDebugLog(`Stream error: ${errorData.substring(5).trim()}`);
                }
              } else {
                addDebugLog('Stream error: Unknown error');
              }
              setIsStreaming(false);
              setIsInitializing(false);
            }
          }
        }
      } else {
        // Fall back to the old endpoint if no agent is selected
        // This is the same as your existing implementation
        const response = await fetch(`${API_URL}/api/chat-stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            messages: apiMessages
          })
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(`HTTP error ${response.status}: ${errorData.detail || response.statusText}`);
        }

        // Prepare to start streaming
        setIsStreaming(true);

        // Clear the loading message
        setMessages(prev => {
          const newMessages = [...prev];
          newMessages[newMessages.length - 1].content = '';
          return newMessages;
        });

        // Set up EventSource for streaming
        const sse_url = `${API_URL}/api/chat-stream?token=${token}&max_tokens=${MAX_TOKENS}`;
        addDebugLog(`Creating SSE connection with URL: ${sse_url}`);
        const newEventSource = new EventSource(sse_url);
        setEventSource(newEventSource);

        // Set up event handlers (same as your existing implementation)
        newEventSource.onopen = () => {
          addDebugLog("SSE connection opened successfully");
        };

        newEventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.content) {
              // Append to our reference string
              currentResponseRef.current += data.content;

              // Update the entire message at once
              setMessages(prev => {
                const newMessages = [...prev];
                newMessages[newMessages.length - 1].content = currentResponseRef.current;
                return newMessages;
              });
            }
          } catch (error) {
            addDebugLog(`Error parsing message: ${error.message}`);
          }
        };

        newEventSource.addEventListener('debug', (event) => {
          addDebugLog(event.data);
        });

        newEventSource.addEventListener('completion', (event) => {
          addDebugLog('Streaming completed');
          newEventSource.close();
          setEventSource(null);
          setIsInitializing(false);
          setIsStreaming(false);
        });

        newEventSource.addEventListener('error', (event) => {
          let errorMessage = 'Connection closed or error occurred';
          try {
            if (event.data) {
              const errorData = JSON.parse(event.data);
              errorMessage = errorData.error || errorMessage;
            }
          } catch (e) {
            // If parsing fails, use default message
          }
          addDebugLog(`Stream error: ${errorMessage}`);
          newEventSource.close();
          setEventSource(null);
          setIsStreaming(false);
          setIsInitializing(false);
        });
      }
    } catch (error) {
      addDebugLog(`Error: ${error.message}`);
      setIsStreaming(false);
      setIsInitializing(false);

      // Update the last message with an error
      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1].content = `Error: ${error.message}`;
        return newMessages;
      });
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>NEAR AI Agent Runner</h1>
      </header>

      <div className="container">
        {!isLoggedIn ? (
          // Login form
          <div className="login-container">
            <h2>Login</h2>
            <form onSubmit={handleLogin}>
              <div className="form-group">
                <label>Username:</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="user"
                  required
                />
              </div>
              <div className="form-group">
                <label>Password:</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="password"
                  required
                />
              </div>
              <button type="submit">Login</button>
            </form>
            <div className="help-text">
              <p><strong>Note:</strong> Default credentials are already filled in.</p>
            </div>
          </div>
        ) : (
          // Chat interface with agent selector
          <div className="main-interface">
            <div className="agent-selector">
              <label>Select Agent:</label>
              <select
                value={selectedAgent}
                onChange={(e) => setSelectedAgent(e.target.value)}
                disabled={isStreaming || isInitializing}
              >
                {availableAgents.map(agent => (
                  <option key={agent} value={agent}>{agent}</option>
                ))}
              </select>
            </div>

            <div className="chat-container">
              <div className="chat-messages">
                {messages.map((message, index) => (
                  <div
                    key={index}
                    className={`message ${message.role === 'user' ? 'user' : 'assistant'}`}
                  >
                    <div className="message-role">{message.role === 'user' ? 'You' : 'AI'}</div>
                    <div className="message-content">
                      {message.content}
                      {message.role === 'assistant' && isInitializing && index === messages.length - 1 && (
                        <div className="loading-indicator">
                          <div className="loading-dot"></div>
                          <div className="loading-dot"></div>
                          <div className="loading-dot"></div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messageEndRef} />
              </div>

              <div className="chat-input">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Type your message..."
                  disabled={isStreaming || isInitializing}
                  onKeyPress={(e) => e.key === 'Enter' && !isStreaming && !isInitializing && sendMessage()}
                />
                <button
                  onClick={sendMessage}
                  disabled={isStreaming || isInitializing}
                >
                  {isInitializing ? 'Initializing...' : isStreaming ? 'Streaming...' : 'Send'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Debug log panel */}
        <div className="debug-container">
          <h3>Debug Logs</h3>
          <div className="debug-logs">
            {debugLogs.map((log, index) => (
              <div key={index} className="debug-log">{log}</div>
            ))}
            <div ref={debugEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;