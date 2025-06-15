// Cache data and lookup debugging - declared as var to be accessible across modules
var cacheData = null;
let currentEventObj = null;

function initCache(data) {
    console.log('Initializing cache with data:', data);
    cacheData = data;
}

function findCachedMessage(channelId, messageId) {
    if (!cacheData || !channelId || !messageId) return null;
    
    const channelMessages = cacheData[channelId];
    if (!channelMessages) {
        console.warn(`No messages found in cache for channel ${channelId}`);
        return null;
    }
    
    const message = channelMessages.find(m => String(m.message_id) === String(messageId));
    if (!message) {
        console.warn(`Message ${messageId} not found in cache for channel ${channelId}`);
    }
    return message;
}

// Convert ISO timestamp to local datetime string for datetime-local inputs
function toLocalDatetime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const pad = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function formatDuration(ms) {
    if (!ms) return "N/A";
    if (ms < 1000) return `${ms}ms`;
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
}

function formatFileSize(bytes) {
    if (!bytes) return "N/A";
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

function showEditModal(eventObj, isReadOnly = false) {
    console.log("showEditModal called with eventObj:", eventObj);
    currentEventObj = eventObj;
    // Use the correct modal id
    const modalContainer = document.getElementById('edit-modal');
    if (!modalContainer) {
        console.error('Edit modal container not found!');
        return;
    }

    // Helper function to safely set field value
    const setFieldValue = (id, value, defaultValue = "") => {
        const element = document.getElementById(id);
        if (element) {
            if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                element.value = value || defaultValue;
            } else {
                element.textContent = value || defaultValue;
            }
        }
    };

    // Set modal title
    const modalTitle = modalContainer.querySelector('.modal-title');
    if (modalTitle) {
        modalTitle.textContent = isReadOnly ? 'Event Details' : 'Edit Event';
    }

    // Populate basic fields
    setFieldValue("field-timestamp", toLocalDatetime(eventObj.timestamp));
    setFieldValue("field-event", eventObj.event);
    setFieldValue("field-edit_timestamp", toLocalDatetime(eventObj.edit_timestamp));
    
    // Channel and message fields
    setFieldValue("field-source_channel", eventObj.source_channel);
    setFieldValue("field-source_channel_name", eventObj.source_channel_name);
    setFieldValue("field-dest_channel", eventObj.dest_channel);
    setFieldValue("field-dest_channel_name", eventObj.dest_channel_name);
    setFieldValue("field-message_id", eventObj.message_id);
    setFieldValue("field-dest_message_id", eventObj.dest_message_id);

    // Status and Error Information
    const statusElement = document.getElementById("field-status");
    if (statusElement) {
        statusElement.textContent = eventObj.status || "Unknown";
        statusElement.className = `mt-1 p-2 rounded-md text-sm ${
            eventObj.status === 'success' ? 'bg-green-100 text-green-800' :
            eventObj.status === 'error' ? 'bg-red-100 text-red-800' :
            eventObj.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
            'bg-gray-100 text-gray-800'
        }`;
    }

    const errorElement = document.getElementById("field-error");
    if (eventObj.error) {
        errorElement.textContent = eventObj.error;
        errorElement.style.display = "block";
    } else {
        errorElement.textContent = "No errors";
        errorElement.classList.add("text-gray-500");
    }

    // Retry information
    document.getElementById("field-retry-count").textContent = 
        eventObj.retry_count ? `${eventObj.retry_count} attempts` : "No retries";

    // Process Duration
    const duration = eventObj.process_duration || 
        (eventObj.end_time && eventObj.start_time ? 
            new Date(eventObj.end_time) - new Date(eventObj.start_time) : null);
    document.getElementById("field-process-duration").textContent = duration ? 
        formatDuration(duration) : "N/A";

    // Message Preview Sections
    const sourceMessage = findCachedMessage(eventObj.source_channel, eventObj.message_id);
    const sourcePreview = document.getElementById("source-message-preview");
    if (sourcePreview) {
        if (sourceMessage) {
            sourcePreview.textContent = sourceMessage.text || sourceMessage.caption || "No text content";
            if (sourceMessage.media) {
                sourcePreview.innerHTML += `<div class="mt-2 text-blue-600">[Contains media: ${sourceMessage.media.type}]</div>`;
            }
        } else {
            sourcePreview.textContent = "Message not found in cache";
            sourcePreview.classList.add("text-gray-500", "italic");
        }
    }

    const destMessage = findCachedMessage(eventObj.dest_channel, eventObj.dest_message_id);
    const translatedPreview = document.getElementById("translated-message-preview");
    if (translatedPreview) {
        if (destMessage) {
            translatedPreview.textContent = destMessage.text || destMessage.caption || "No text content";
            if (destMessage.media) {
                translatedPreview.innerHTML += `<div class="mt-2 text-blue-600">[Contains media: ${destMessage.media.type}]</div>`;
            }
        } else {
            translatedPreview.textContent = "Message not found in cache";
            translatedPreview.classList.add("text-gray-500", "italic");
        }
    }

    // Media Section
    const mediaSection = document.getElementById("media-section");
    if (sourceMessage?.media || destMessage?.media) {
        mediaSection.style.display = "block";
        const media = sourceMessage?.media || destMessage?.media;
        
        document.getElementById("field-media-type").textContent = media.type || "Unknown";
        document.getElementById("field-file-size").textContent = media.file_size ? 
            formatFileSize(media.file_size) : "Unknown";
        
        if (media.duration) {
            document.getElementById("field-media-duration").textContent = 
                formatDuration(media.duration * 1000);
        } else {
            document.getElementById("field-media-duration").textContent = "N/A";
        }

        if (media.width && media.height) {
            document.getElementById("field-resolution").textContent = 
                `${media.width}×${media.height}`;
        } else {
            document.getElementById("field-resolution").textContent = "N/A";
        }
    } else {
        mediaSection.style.display = "none";
    }

    // Show the modal
    modalContainer.style.display = 'block';
}

// Function to show the details modal - reuses the edit modal with readonly fields
function showDetailsModal(eventObj) {
    console.log("showDetailsModal called with eventObj:", eventObj);
    // Use the correct modal id
    const modalContainer = document.getElementById('details-modal');
    if (!modalContainer) {
        console.error('Details modal container not found!');
        return;
    }
    // Reuse showEditModal but make fields readonly
    showEditModal(eventObj, true);
    
    // Change modal title and buttons for details view
    const modalTitle = document.querySelector('#modal .modal-title');
    if (modalTitle) {
        modalTitle.textContent = 'Event Details';
    }

    const modalFooter = document.querySelector('#modal .modal-footer');
    if (modalFooter) {
        modalFooter.innerHTML = `
            <button type="button" class="bg-gray-100 text-gray-700 px-4 py-2 rounded-md" 
                    onclick="hideEditModal()">Close</button>`;
    }

    // Make all input fields readonly
    const inputs = document.querySelectorAll('#modal input, #modal textarea');
    inputs.forEach(input => {
        input.readOnly = true;
        input.classList.add('bg-gray-50');
    });
}

function hideEditModal() {
    const modalContainer = document.getElementById('modal');
    if (modalContainer) modalContainer.style.display = 'none';
    currentEventObj = null;
}

async function saveEventChanges() {
    if (!currentEventObj) {
        console.error('No event object to save');
        return;
    }

    const updatedEvent = {
        ...currentEventObj,
        timestamp: new Date(document.getElementById("field-timestamp").value).toISOString(),
        edit_timestamp: new Date(document.getElementById("field-edit_timestamp").value).toISOString(),
        event: document.getElementById("field-event").value,
        source_channel_name: document.getElementById("field-source_channel_name").value,
        dest_channel_name: document.getElementById("field-dest_channel_name").value,
    };

    try {
        const response = await fetch('/api/admin/events/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(updatedEvent)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        console.log('Save successful:', result);
        
        // Refresh the events table
        if (typeof refreshEventsTable === 'function') {
            refreshEventsTable();
        }

        hideEditModal();
    } catch (error) {
        console.error('Error saving event:', error);
        alert('Failed to save changes. Please try again.');
    }
}

// Update "OK/FAIL" label whenever toggle changes
document.addEventListener("input", function(e) {
    if (e.target && e.target.id === "field-posting_success") {
        document.getElementById("success-status").textContent = e.target.checked ? "OK" : "FAIL";
    }
});
