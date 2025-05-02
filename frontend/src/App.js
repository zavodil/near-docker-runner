// src/App.js

import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// Configuration constants
const MAX_TOKENS = 4000;  // Default max tokens
const MAX_MESSAGE_LENGTH = 50000;  // Maximum characters to show in UI
const API_URL = 'http://localhost:5001/api';

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
      const response = await fetch(`${API_URL}/login`, {
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
      } else {
        addDebugLog(`Login failed: ${data.detail || data.message}`);
      }
    } catch (error) {
      addDebugLog(`Login error: ${error.message}`);
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

  // Send a message and get streaming response
  const sendMessage = async () => {
    if (!input.trim()) return;

    // Add user message to chat
    addMessage('user', input);
    addDebugLog(`Sending message: ${input.substring(0, 30)}${input.length > 30 ? '...' : ''}`);

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
      // 1. Initiate POST request to set up the session
      addDebugLog("Initializing chat session with POST request");
      const response = await fetch(`${API_URL}/chat-stream`, {
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

      // 2. Set up EventSource for streaming
      const sse_url = `${API_URL}/chat-stream?token=${token}&max_tokens=${MAX_TOKENS}`;
      addDebugLog(`Creating SSE connection with URL: ${sse_url}`);
      const newEventSource = new EventSource(sse_url);
      setEventSource(newEventSource);

      // 3. Debug - important for understanding how events arrive
      newEventSource.onopen = () => {
        addDebugLog("SSE connection opened successfully");
      };

      // 4. Handle regular message events
      newEventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.content) {
            // Append to our reference string
            currentResponseRef.current += data.content;

            // Check if the response is getting too long
            if (currentResponseRef.current.length > MAX_MESSAGE_LENGTH) {
              // Add a note about truncation
              addDebugLog(`Response exceeded ${MAX_MESSAGE_LENGTH} characters, may be truncated`);
            }

            // Update the entire message at once
            setMessages(prev => {
              // Create a new array for React to detect the change
              const newMessages = [...prev];

              // Replace the entire content with our accumulated string
              newMessages[newMessages.length - 1].content = currentResponseRef.current;

              return newMessages;
            });
          }

          // Update for completion event
          if (data.status === 'complete' && data.total_chars) {
            addDebugLog(`Streaming completed: ${data.total_chars} characters received`);
          }
        } catch (error) {
          addDebugLog(`Error parsing message: ${error.message}`);
        }
      };

      // 5. Handle specific event types
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
        <h1>NEAR AI Agent runner</h1>
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
          // Chat interface
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
        )}

        {/* Debug log panel */}
        <div className="debug-container">
          <h3>Debug Logs{isInitializing.toString()}</h3>
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