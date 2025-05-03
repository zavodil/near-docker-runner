// src/services/eventHandlers.js

// Helper function to safely parse JSON content
const safeJsonParse = (content, addDebugLog) => {
  try {
    return JSON.parse(content);
  } catch (e) {
    addDebugLog(`Warning: Failed to parse JSON: ${e.message}`);
    return content;
  }
};

// Helper function to normalize and clean newlines in content
const cleanNewlines = (content) => {
  if (typeof content !== 'string') {
    return content;
  }

  // First, normalize all newlines to \n
  let cleaned = content
    .replace(/\r\n/g, '\n')     // Windows newlines
    .replace(/\r/g, '\n');      // Old Mac newlines

  // Remove duplicate newlines (consecutive \n characters)
  cleaned = cleaned.replace(/\n+/g, '\n');

  return cleaned;
};

// Handle data events (streaming content)
export const handleDataEvent = (line, addDebugLog, setMessages, currentResponseRef) => {
  try {
    // Extract the data from the SSE message
    const dataContent = line.substring(5).trim();

    // Parse the JSON data
    const parsedData = JSON.parse(dataContent);

    // Get the content from the parsed data
    let content;

    // Check if this is directly a string or if it's in the content field
    if (typeof parsedData === 'string') {
      // If the data is already a string (simple JSON)
      content = parsedData;
    } else if (parsedData.content) {
      // If the data has a content field
      content = parsedData.content;
    } else {
      // Default case, try to use the data as is
      content = JSON.stringify(parsedData);
    }

    // Try to parse content as JSON if it might be double-encoded
    if (typeof content === 'string' && (content.startsWith('"') || content.startsWith('{'))) {
      content = safeJsonParse(content, addDebugLog);
    }

    // Handle JSON-encoded newlines in the content
    if (content) {
      // If current response is empty, add content without leading newline
      if (currentResponseRef.current === '') {
        // Clean any leading newlines
        content = content.replace(/^\n+/, '');
      }

      // Clean and normalize the content
      content = cleanNewlines(content);

      // Update the current response
      currentResponseRef.current += content;
    }

    // Debug log
    if (content && content.length > 0) {
      addDebugLog(`Data event: ${content.substring(0, 30).replace(/\n/g, '\\n')}${content.length > 30 ? '...' : ''}`);
    }

    // Update the last message in the chat with the current response
    setMessages(prev => {
      const newMessages = [...prev];
      if (newMessages.length > 0) {
        // Find the last assistant message
        let lastAssistantIndex = newMessages.length - 1;
        while (lastAssistantIndex >= 0 && newMessages[lastAssistantIndex].role !== 'assistant') {
          lastAssistantIndex--;
        }

        // If found, update it with cleaned content
        if (lastAssistantIndex >= 0) {
          // Additional final cleaning - remove any duplicate newlines
          let cleanedResponse = currentResponseRef.current.replace(/\n{2,}/g, '\n');

          // Remove any stray newlines at the beginning or end
          cleanedResponse = cleanedResponse.replace(/^\n+/, '').replace(/\n+$/, '');

          newMessages[lastAssistantIndex].content = cleanedResponse;
        }
      }
      return newMessages;
    });
  } catch (error) {
    addDebugLog(`Error processing data event: ${error.message}`);
  }
};

// Handle new message events (separate messages)
export const handleNewMessageEvent = (line, addDebugLog, setMessages) => {
  try {
    // Extract the data part of the event
    const dataStartIndex = line.indexOf('data:');
    if (dataStartIndex === -1) {
      addDebugLog('Error: No data found in new_message event');
      return;
    }

    // Parse the JSON data
    const dataJson = line.substring(dataStartIndex + 5).trim();
    const data = JSON.parse(dataJson);

    // Extract content
    let content;
    if (data.content) {
      // Try to parse content as JSON (it might be JSON-encoded from the backend)
      content = safeJsonParse(data.content, addDebugLog);
    } else {
      content = JSON.stringify(data);
    }

    // Clean and normalize newlines
    if (typeof content === 'string') {
      content = cleanNewlines(content);

      // Remove any stray newlines at the beginning or end
      content = content.replace(/^\n+/, '').replace(/\n+$/, '');
    }

    // Debug log
    addDebugLog(`New message event: ${String(content).substring(0, 30).replace(/\n/g, '\\n')}${String(content).length > 30 ? '...' : ''}`);

    // Add the new message to the chat
    if (content && String(content).trim() !== '') {
      setMessages(prev => [...prev, { role: 'assistant', content }]);
    } else {
      addDebugLog('Skipping empty new_message event');
    }
  } catch (error) {
    addDebugLog(`Error processing new_message event: ${error.message}`);
  }
};

// Handle debug events
export const handleDebugEvent = (line, addDebugLog) => {
  try {
    // Extract the data from the debug event
    const dataStartIndex = line.indexOf('data:');
    if (dataStartIndex !== -1) {
      const dataJson = line.substring(dataStartIndex + 5).trim();
      const data = JSON.parse(dataJson);
      addDebugLog(`Debug event: ${data}`);
    }
  } catch (error) {
    addDebugLog(`Error processing debug event: ${error.message}`);
  }
};

// Handle completion events
export const handleCompletionEvent = (addDebugLog, setIsStreaming, setIsInitializing, setMessages) => {
  addDebugLog('Completion event received');
  setIsStreaming(false);
  setIsInitializing(false);

  // Make sure the last message is not empty and clean up any remaining newline issues
  setMessages(prev => {
    const newMessages = [...prev];

    // Find the last assistant message
    let lastAssistantIndex = newMessages.length - 1;
    while (lastAssistantIndex >= 0 && newMessages[lastAssistantIndex].role !== 'assistant') {
      lastAssistantIndex--;
    }

    // If found and it's empty, remove it
    if (lastAssistantIndex >= 0) {
      if (!newMessages[lastAssistantIndex].content || newMessages[lastAssistantIndex].content.trim() === '') {
        addDebugLog('Removing empty message');
        newMessages.splice(lastAssistantIndex, 1);
      } else {
        // Final cleanup of any duplicate newlines
        let content = newMessages[lastAssistantIndex].content;
        content = content.replace(/\n{2,}/g, '\n');
        content = content.replace(/^\n+/, '').replace(/\n+$/, '');
        newMessages[lastAssistantIndex].content = content;
      }
    }

    return newMessages;
  });
};

// Handle error events
export const handleErrorEvent = (line, addDebugLog, setIsStreaming, setIsInitializing) => {
  try {
    // Extract the error from the event
    const dataStartIndex = line.indexOf('data:');
    if (dataStartIndex !== -1) {
      const dataJson = line.substring(dataStartIndex + 5).trim();
      const data = JSON.parse(dataJson);
      addDebugLog(`Error event: ${data.error || JSON.stringify(data)}`);
    }

    // Reset streaming states
    setIsStreaming(false);
    setIsInitializing(false);
  } catch (error) {
    addDebugLog(`Error processing error event: ${error.message}`);
  }
};