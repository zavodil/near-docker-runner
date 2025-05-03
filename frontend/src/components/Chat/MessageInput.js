// src/components/Chat/MessageInput.js
import React from 'react';

function MessageInput({ input, setInput, handleSendMessage, isDisabled, status }) {
  return (
    <div className="chat-input">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Type your message..."
        disabled={isDisabled}
        onKeyPress={(e) => e.key === 'Enter' && !isDisabled && handleSendMessage()}
      />
      <button
        onClick={handleSendMessage}
        disabled={isDisabled}
      >
        {status}
      </button>
    </div>
  );
}

export default MessageInput;