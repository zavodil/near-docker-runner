// src/components/Debug/DebugPanel.js
import React, { useRef, useEffect } from 'react';
import './DebugPanel.css';

function DebugPanel({ logs }) {
  // Reference for auto-scrolling
  const debugEndRef = useRef(null);

  // Auto-scroll when logs are updated
  useEffect(() => {
    if (debugEndRef.current) {
      debugEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  return (
    <div className="debug-container">
      <h3>Debug Logs</h3>
      <div className="debug-logs">
        {logs.map((log, index) => (
          <div key={index} className="debug-log">{log}</div>
        ))}
        <div ref={debugEndRef} />
      </div>
    </div>
  );
}

export default DebugPanel;