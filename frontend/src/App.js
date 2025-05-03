// src/App.js
import React, { useState, useEffect } from 'react';
import Login from './components/Login/Login';
import Chat from './components/Chat/Chat';
import DebugPanel from './components/Debug/DebugPanel';
import { loginUser, checkServerHealth } from './services/auth';
import './App.css';

// Configuration constants
export const MAX_TOKENS = 4000;
export const MAX_MESSAGE_LENGTH = 50000;
export const API_URL = 'http://localhost:5001';

function App() {
  // State for user authentication
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [token, setToken] = useState('');

  // State for debug logs
  const [debugLogs, setDebugLogs] = useState([]);

  // Add a debug log
  const addDebugLog = (log) => {
    const timestamp = new Date().toLocaleTimeString();
    setDebugLogs(prev => [...prev, `[${timestamp}] ${log}`]);
  };

  // Handle login
  const handleLogin = async (username, password) => {
    addDebugLog(`Attempting to login as ${username}...`);

    try {
      const data = await loginUser(username, password);
      setToken(data.token);
      setIsLoggedIn(true);
      addDebugLog(`Logged in successfully with token: ${data.token.substring(0, 6)}...`);

      // Check server health
      await checkServerHealth(addDebugLog);
    } catch (error) {
      addDebugLog(`Login error: ${error.message}`);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>NEAR AI Agent Runner</h1>
      </header>

      <div className="container">
        {!isLoggedIn ? (
          <Login onLogin={handleLogin} />
        ) : (
          <Chat
            token={token}
            addDebugLog={addDebugLog}
          />
        )}

        <DebugPanel logs={debugLogs} />
      </div>
    </div>
  );
}

export default App;