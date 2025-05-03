// src/components/Chat/FixedChat.js
import React, { useState, useRef } from 'react';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import AgentSelector from '../AgentSelector/AgentSelector';
import { sendMessageToAgent, getStreamReader } from '../../services/api';
import {
  handleNewMessageEvent,
  handleDataEvent
} from '../../services/eventHandlers';  // Use the fixed handlers
import './Chat.css';

function Chat({ token, addDebugLog }) {
  // State for chat
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);

  // Agent selection
  const [selectedAgent, setSelectedAgent] = useState('example_agent');
  const [availableAgents, setAvailableAgents] = useState(['example_agent']);

  // Reference to track the current response string
  const currentResponseRef = useRef('');

  // Add a message to the chat
  const addMessage = (role, content) => {
    // Debug the message being added
    console.log(`Adding message - Role: ${role}, Content: "${content.substring(0, 30)}${content.length > 30 ? '...' : ''}"`);

    // Skip empty messages only for AI, never for user
    if (role === 'assistant' && (!content || content.trim() === '' || content === 'Loading...')) {
      console.log('Skipping empty assistant message');
      return;
    }

    // Add message to state and log for debugging
    setMessages(prev => {
      const newMessages = [...prev, { role, content }];
      console.log('Updated messages array:', newMessages);
      return newMessages;
    });
  };

  // Process an SSE stream chunk
  const processStreamChunk = async ({ reader, decoder, buffer = '' }) => {
    const { done, value } = await reader.read();

    if (done) {
      addDebugLog('Stream finished');
      setIsStreaming(false);
      setIsInitializing(false);
      return;
    }

    // Decode the chunk and add it to the buffer
    buffer += decoder.decode(value, { stream: true });

    // Process full SSE messages in the buffer
    const lines = buffer.split('\n\n');
    buffer = lines.pop() || ''; // Keep the last incomplete message in the buffer

    for (const line of lines) {
      // Process in priority order:

      // 1. New message events (separate messages) - CRITICAL: These must always create new messages
      if (line.startsWith('event: new_message')) {
        handleNewMessageEvent(line, addDebugLog, setMessages);
      }
      // 2. Data events (content for current message) - These update the current streaming message only
      else if (line.startsWith('data:')) {
        handleDataEvent(line, addDebugLog, setMessages, currentResponseRef);
      }
      // 3. Debug events
      else if (line.startsWith('event: debug')) {
        const debugData = line.split('\n')[1];
        if (debugData && debugData.startsWith('data:')) {
          addDebugLog(debugData.substring(5).trim());
        }
      }
      // 4. Completion events
      else if (line.startsWith('event: completion')) {
        addDebugLog('Streaming completed');
        setIsStreaming(false);
        setIsInitializing(false);
      }
      // 5. Error events
      else if (line.startsWith('event: error')) {
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

    // Continue reading the stream
    return processStreamChunk({ reader, decoder, buffer });
  };

  // Send a message and get streaming response
  const handleSendMessage = async () => {
    if (!input.trim()) return;

    // Save user input to a variable before clearing it
    const userMessage = input.trim();

    // Add user message to chat with the saved variable
    addDebugLog(`Adding user message to chat: "${userMessage}"`);
    addMessage('user', userMessage);

    // Clear input field
    setInput('');

    // Prepare message for API using the saved variable
    const apiMessages = [
      ...messages.map(m => ({ role: m.role, content: m.content })),
      { role: 'user', content: userMessage }
    ];

    // Log the messages array for debugging
    console.log('Messages array before API call:', JSON.stringify(apiMessages));
    addDebugLog(`Sending message to agent '${selectedAgent}': ${userMessage.substring(0, 30)}${userMessage.length > 30 ? '...' : ''}`);

    // Reset the current response
    currentResponseRef.current = '';

    // Set loading states
    setIsInitializing(true);

    // Create a temporary message for the assistant's response with loading indicator
    addMessage('assistant', 'Loading...');

    try {
      // Call the agent endpoint
      const response = await sendMessageToAgent(token, apiMessages, selectedAgent, addDebugLog);

      // Get stream reader and decoder
      const { reader, decoder } = getStreamReader(response);

      // Clear the loading message
      setMessages(prev => {
        const newMessages = [...prev];
        // Make sure we're only clearing the Loading... message and not removing user messages
        if (newMessages.length > 0 &&
            newMessages[newMessages.length - 1].role === 'assistant' &&
            newMessages[newMessages.length - 1].content === 'Loading...') {
          newMessages[newMessages.length - 1].content = '';
        }
        return newMessages;
      });

      // Prepare to start streaming
      setIsStreaming(true);

      // Process the stream
      await processStreamChunk({ reader, decoder });
    } catch (error) {
      addDebugLog(`Error: ${error.message}`);
      setIsStreaming(false);
      setIsInitializing(false);

      // Update the last message with an error
      setMessages(prev => {
        const newMessages = [...prev];

        // Find the last assistant message
        let lastAssistantIndex = newMessages.length - 1;
        while (lastAssistantIndex >= 0 && newMessages[lastAssistantIndex].role !== 'assistant') {
          lastAssistantIndex--;
        }

        // If found, update it with error
        if (lastAssistantIndex >= 0) {
          newMessages[lastAssistantIndex].content = `Error: ${error.message}`;
        } else {
          // If no assistant message found, add one
          newMessages.push({ role: 'assistant', content: `Error: ${error.message}` });
        }

        return newMessages;
      });
    }
  };

  // Determine button text based on state
  const getButtonStatus = () => {
    if (isInitializing) return 'Initializing...';
    if (isStreaming) return 'Streaming...';
    return 'Send';
  };

  return (
    <div className="main-interface">
      <AgentSelector
        selectedAgent={selectedAgent}
        setSelectedAgent={setSelectedAgent}
        isDisabled={isStreaming || isInitializing}
        availableAgents={availableAgents}
      />

      <div className="chat-container">
        <MessageList
          messages={messages}
          isInitializing={isInitializing}
        />

        <MessageInput
          input={input}
          setInput={setInput}
          handleSendMessage={handleSendMessage}
          isDisabled={isStreaming || isInitializing}
          status={getButtonStatus()}
        />
      </div>
    </div>
  );
}

export default Chat;