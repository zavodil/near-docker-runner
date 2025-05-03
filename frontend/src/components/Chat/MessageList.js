// src/components/Chat/MessageList.js
import React, { useRef, useEffect } from 'react';

function MessageList({ messages, isInitializing }) {
  // Reference for auto-scrolling
  const messageEndRef = useRef(null);

  // Auto-scroll when messages are updated
  useEffect(() => {
    if (messageEndRef.current) {
      messageEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Function to properly format message content with line breaks
  const formatContent = (content) => {
    if (!content) return '';

    // Split content by newlines and map each line to a separate element
    return content.split('\n').map((line, i) => (
      <React.Fragment key={i}>
        {line}
        {i < content.split('\n').length - 1 && <br />}
      </React.Fragment>
    ));
  };

  return (
    <div className="chat-messages">
      {messages.map((message, index) => (
        <div
          key={index}
          className={`message ${message.role === 'user' ? 'user' : 'assistant'}`}
        >
          <div className="message-role">{message.role === 'user' ? 'You' : 'AI'}</div>
          <div className="message-content">
            {formatContent(message.content)}
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
  );
}

export default MessageList;