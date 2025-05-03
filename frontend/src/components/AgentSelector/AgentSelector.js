// src/components/AgentSelector/AgentSelector.js
import React from 'react';
import './AgentSelector.css';

function AgentSelector({ selectedAgent, setSelectedAgent, isDisabled, availableAgents }) {
  return (
    <div className="agent-selector">
      <label>Select Agent:</label>
      <select
        value={selectedAgent}
        onChange={(e) => setSelectedAgent(e.target.value)}
        disabled={isDisabled}
      >
        {availableAgents.map(agent => (
          <option key={agent} value={agent}>{agent}</option>
        ))}
      </select>
    </div>
  );
}

export default AgentSelector;