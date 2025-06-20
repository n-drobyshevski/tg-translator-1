// Cache data and lookup debugging - declared as var to be accessible across modules
var cacheData = null;
let currentEventObj = null;
let originalValues = null; // Store original values for change detection

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

// Track changed fields
function trackChanges(formElement) {
    const changes = {};
    const formData = new FormData(formElement);
    
    for (const [key, value] of formData.entries()) {
        if (originalValues[key] !== value) {
            changes[key] = value;
        }
    }
    
    return Object.keys(changes).length > 0 ? changes : null;
}

// Validate form fields
function validateField(field) {
    const value = field.value.trim();
    const pattern = field.getAttribute('pattern');
    
    if (pattern && value) {
        const regex = new RegExp(`^${pattern}$`);
        if (!regex.test(value)) {
            field.setCustomValidity(field.title || 'Invalid format');
            return false;
        }
    }
    
    field.setCustomValidity('');
    return true;
}

// Handle form submission
async function handleFormSubmit(e) {
    e.preventDefault();
    
    const form = e.target;
    const submitButton = form.querySelector('button[type="submit"]');
    const changes = trackChanges(form);
    
    if (!changes) {
        showToast('No changes to save', 'info');
        return;
    }
    
    // Validate all fields
    let isValid = true;
    form.querySelectorAll('input[pattern]').forEach(field => {
        if (!validateField(field)) {
            isValid = false;
            field.classList.add('border-red-500');
        } else {
            field.classList.remove('border-red-500');
        }
    });
    
    if (!isValid) {
        showToast('Please correct the errors before saving', 'error');
        return;
    }
    
    try {
        // Show loading state
        submitButton.disabled = true;
        submitButton.innerHTML = `
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Saving...
        `;
        
        // Send changes to server
        const response = await fetch('/admin/events/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                eventId: currentEventObj.id,
                changes: changes
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to save changes');
        }
        
        // Update current event object with changes
        Object.assign(currentEventObj, changes);
        
        // Show success message
        showToast('Changes saved successfully', 'success');
        
        // Close the modal
        hideModal('edit-modal');
        
        // Refresh the events table
        if (typeof refreshEventsTable === 'function') {
            refreshEventsTable();
        }
    } catch (error) {
        console.error('Error saving changes:', error);
        showToast('Failed to save changes. Please try again.', 'error');
    } finally {
        // Reset button state
        submitButton.disabled = false;
        submitButton.innerHTML = 'Save Changes';
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 px-6 py-3 rounded-lg shadow-lg transition-all duration-300 transform translate-y-full z-50 ${
        type === 'error' ? 'bg-red-500 text-white' :
        type === 'success' ? 'bg-green-500 text-white' :
        'bg-blue-500 text-white'
    }`;
    
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.style.transform = 'translateY(0)';
    }, 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.transform = 'translateY(full)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Helper function to safely set field value and handle readonly state
function setFieldValue(modalId, fieldId, value, isReadOnly = false) {
    const element = document.querySelector(`#${modalId} #${fieldId}`);
    if (!element) {
        console.warn(`Element ${fieldId} not found in modal ${modalId}`);
        return;
    }

    if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
        element.value = value || '';
        element.disabled = isReadOnly;
        
        if (!isReadOnly) {
            // Store original value for change tracking
            originalValues = originalValues || {};
            originalValues[element.name] = value;
            
            // Add validation event listeners
            if (element.pattern) {
                element.addEventListener('input', () => {
                    validateField(element);
                });
                element.addEventListener('blur', () => {
                    validateField(element);
                });
            }
        }
    } else {
        element.textContent = value || '';
    }
}

async function updateMessagePreview(container, content, mediaInfo = null) {
    if (!container) return;

    // Show loading state
    container.innerHTML = `
        <div class="loading-spinner">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
    `;

    try {
        // Process content asynchronously to not block the UI
        const processedContent = await new Promise((resolve) => {
            setTimeout(() => {
                // If we have media info, show it first
                let html = '';
                  if (mediaInfo && mediaInfo.type && mediaInfo.type !== 'text') {
                    html += `
                        <div class="media-info">
                            <strong>Media Type:</strong> ${mediaInfo.type}<br>
                            ${mediaInfo.size ? `<strong>File Size:</strong> ${formatFileSize(mediaInfo.size)}<br>` : ''}
                            ${mediaInfo.path ? `<strong>File:</strong> <a href="${mediaInfo.path}" target="_blank" rel="noopener noreferrer">View Media</a>` : ''}
                        </div>
                    `;
                }

                // Format and sanitize the main content
                if (content) {
                    const formattedContent = formatMessageContent(content);
                    if (formattedContent.length > 10000) {
                        html += `<div class="content-warning mb-2">
                            <i class="fas fa-exclamation-triangle text-yellow-500 mr-2"></i>
                            Large message (${formattedContent.length.toLocaleString()} characters)
                        </div>`;
                    }
                    html += `<div class="message-content">${formattedContent}</div>`;
                } else {
                    html += `<div class="message-fallback">No content available</div>`;
                }

                resolve(html);
            }, 0);
        });

        // Update the container with processed content
        container.innerHTML = processedContent;

        // Initialize any syntax highlighting if needed
        if (window.Prism) {
            container.querySelectorAll('pre code').forEach((block) => {
                Prism.highlightElement(block);
            });
        }
    } catch (error) {
        console.error('Error updating message preview:', error);
        container.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-circle text-red-500 mr-2"></i>
                Error loading message content
            </div>
        `;
    }
}

function updateModalFields(modalId, eventObj, isReadOnly = false) {
    // Basic event info
    setFieldValue(modalId, 'field-event', eventObj.event || 'create', isReadOnly);
    setFieldValue(modalId, 'field-timestamp', toLocalDatetime(eventObj.timestamp), isReadOnly);
    setFieldValue(modalId, 'field-edit_timestamp', toLocalDatetime(eventObj.edit_timestamp), isReadOnly);
      // Source channel info
    const sourceChannelId = eventObj.source_channel_id || eventObj.source_channel || '';
    const destChannelId = eventObj.dest_channel_id || eventObj.dest_channel || '';
    
    setFieldValue(modalId, 'field-source_channel', formatChannelId(sourceChannelId), isReadOnly);
    setFieldValue(modalId, 'field-source_channel_name', eventObj.source_channel_name || '', isReadOnly);
    setFieldValue(modalId, 'field-message_id', eventObj.message_id || '', isReadOnly);
    
    // Destination channel info
    setFieldValue(modalId, 'field-dest_channel', formatChannelId(destChannelId), isReadOnly);
    setFieldValue(modalId, 'field-dest_channel_name', eventObj.dest_channel_name || '', isReadOnly);
    setFieldValue(modalId, 'field-dest_message_id', eventObj.dest_message_id || '', isReadOnly);

    // Status indicators
    const status = document.querySelector(`#${modalId} #field-status`);
    if (status) {
        const isSuccess = eventObj.posting_success === true;
        status.textContent = isSuccess ? 'SUCCESS' : 'FAILED';
        status.className = `status-badge status-${isSuccess ? 'success' : 'error'}`;
    }

    // Error message if any
    const error = document.querySelector(`#${modalId} #field-error`);
    if (error) {
        if (eventObj.exception_message) {
            error.textContent = eventObj.exception_message;
            error.classList.remove('hidden');
        } else {
            error.classList.add('hidden');
        }
    }

    // Message previews
    const sourcePreview = document.querySelector(`#${modalId} #source-message-preview`);
    const translatedPreview = document.querySelector(`#${modalId} #translated-message-preview`);

    // Update source message preview
    if (sourcePreview) {
        const mediaInfo = eventObj.media_type ? {
            type: eventObj.media_type,
            size: eventObj.file_size_bytes,
            path: eventObj.file_path
        } : null;
        
        updateMessagePreview(sourcePreview, eventObj.source_message, mediaInfo);
    }

    // Update translated message preview
    if (translatedPreview) {
        updateMessagePreview(translatedPreview, eventObj.translated_message);
    }

    // Additional metrics
    const retryCount = document.querySelector(`#${modalId} #field-retry-count`);
    if (retryCount) {
        const count = eventObj.retry_count || 0;
        retryCount.textContent = `${count} attempt${count !== 1 ? 's' : ''}`;
        retryCount.className = `status-badge ${count > 0 ? 'status-warning' : 'status-info'}`;
    }

    // Process duration
    const duration = document.querySelector(`#${modalId} #field-process-duration`);
    if (duration) {
        const ms = eventObj.translation_time ? Math.round(eventObj.translation_time * 1000) : 0;
        duration.textContent = formatDuration(ms);
    }

    // Update size information with proper formatting
    const originalSize = document.querySelector(`#${modalId} #field-original-size`);
    const translatedSize = document.querySelector(`#${modalId} #field-translated-size`);
    const sizeChanges = document.querySelector(`#${modalId} #size-changes`);
    const previousSize = document.querySelector(`#${modalId} #field-previous-size`);
    const newSize = document.querySelector(`#${modalId} #field-new-size`);

    if (originalSize) {
        originalSize.textContent = formatNumber(eventObj.original_size);
    }
    if (translatedSize) {
        translatedSize.textContent = formatNumber(eventObj.translated_size);
    }

    // Handle size changes for edit events
    if (eventObj.event === 'edit' && eventObj.previous_size && eventObj.new_size) {
        if (sizeChanges) sizeChanges.classList.remove('hidden');
        if (previousSize) previousSize.textContent = formatNumber(eventObj.previous_size);
        if (newSize) newSize.textContent = formatNumber(eventObj.new_size);
        updateSizeChangeIndicator(eventObj.previous_size, eventObj.new_size);
    } else {
        if (sizeChanges) sizeChanges.classList.add('hidden');
    }
}

function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) {
        console.error(`Modal ${modalId} not found`);
        return;
    }

    modal.classList.remove('hidden');
    // Use requestAnimationFrame to ensure the display change happens after hidden is removed
    requestAnimationFrame(() => {
        modal.style.display = 'flex';
        modal.style.opacity = '1';
    });

    // Setup click-outside-to-close
    const handleOutsideClick = (e) => {
        if (e.target.classList.contains('modal-overlay')) {
            hideModal(modalId);
        }
    };
    modal.addEventListener('click', handleOutsideClick);
}

function hideModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    modal.style.opacity = '0';
    setTimeout(() => {
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }, 200);
}

function showEditModal(eventObj) {
    if (!eventObj) {
        console.error('No event object provided to showEditModal');
        return;
    }

    currentEventObj = eventObj;
    originalValues = {};  // Reset original values
    showModal('edit-modal');
    updateModalFields('edit-modal', eventObj, false);

    // Set up the edit modal footer with Save and Cancel buttons
    const modalFooter = document.querySelector('#edit-modal .modal-footer');
    if (modalFooter) {
        modalFooter.innerHTML = `
            <button type="button" 
                    onclick="hideModal('edit-modal')"
                    class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors">
                Cancel
            </button>
            <button type="submit" 
                    form="event-edit-form"
                    class="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors">
                Save Changes
            </button>
        `;
    }

    // Re-initialize form event listeners
    const form = document.getElementById('event-edit-form');
    if (form) {
        form.removeEventListener('submit', handleFormSubmit);
        form.addEventListener('submit', handleFormSubmit);
    }
}

function showDetailsModal(eventObj) {
    if (!eventObj) {
        console.error('No event object provided to showDetailsModal');
        return;
    }

    showModal('details-modal');
    updateModalFields('details-modal', eventObj, true);

    // Set up the details modal footer with only a Close button
    const modalFooter = document.querySelector('#details-modal .modal-footer');
    if (modalFooter) {
        modalFooter.innerHTML = `
            <button type="button" 
                    onclick="hideModal('details-modal')"
                    class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-400 transition-colors">
                Close
            </button>
        `;
    }

    // Ensure all form fields are read-only in details view
    const form = document.querySelector('#details-modal form');
    if (form) {
        form.querySelectorAll('input, textarea, select').forEach(field => {
            field.setAttribute('readonly', true);
            field.classList.add('bg-gray-50', 'cursor-not-allowed');
        });
    }
}

// Format channel ID for display
function formatChannelId(id) {
    if (!id) return '';
    
    // Remove any non-numeric characters
    const numericId = String(id).replace(/[^0-9-]/g, '');
    
    // Validate the channel ID format (should be a large negative number for channels)
    if (!numericId.match(/^-?\d{10,20}$/)) {
        console.warn(`Invalid channel ID format: ${id}`);
        return id; // Return original if invalid
    }
    
    return numericId;
}

// Validate channel ID format
function isValidChannelId(id) {
    if (!id) return false;
    const numericId = String(id).replace(/[^0-9-]/g, '');
    return numericId.match(/^-?\d{10,20}$/) !== null;
}

// Helper functions for size formatting and comparison
function formatNumber(num) {
    return num ? num.toLocaleString() : '0';
}

function updateSizeChangeIndicator(previousSize, newSize) {
    if (!previousSize || !newSize) return;
    
    const sizeDiff = newSize - previousSize;
    const percentChange = ((newSize - previousSize) / previousSize * 100).toFixed(1);
    const indicator = document.getElementById('size-change-indicator');
    
    if (sizeDiff === 0) {
        indicator.innerHTML = `
            <span class="text-gray-600">
                <i class="fas fa-equals"></i>
                No change
            </span>
        `;
    } else if (sizeDiff > 0) {
        indicator.innerHTML = `
            <span class="text-red-600">
                <i class="fas fa-arrow-up"></i>
                +${percentChange}%
            </span>
        `;
    } else {
        indicator.innerHTML = `
            <span class="text-green-600">
                <i class="fas fa-arrow-down"></i>
                ${percentChange}%
            </span>
        `;
    }
}

// Initialize event handlers when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Set up form submission handler
    const editForm = document.getElementById('event-edit-form');
    if (editForm) {
        editForm.addEventListener('submit', handleFormSubmit);
    }
    
    // Set up close buttons
    document.querySelectorAll('.modal-close-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const modalId = btn.closest('.modal-overlay').id;
            hideModal(modalId);
        });
    });
});
