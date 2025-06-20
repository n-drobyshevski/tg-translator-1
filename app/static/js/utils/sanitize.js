// HTML Sanitization Utility

// Configuration for HTML sanitization
const ALLOWED_TAGS = new Set([
    'p', 'b', 'i', 'em', 'strong', 'a', 'br', 'ul', 'ol', 'li', 
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'code',
    'span', 'div'  // Common container elements
]);

const ALLOWED_ATTRIBUTES = new Set(['href', 'target', 'rel', 'class']);

function sanitizeHTML(html) {
    if (!html) return '';
    
    try {
        // Create a new div element
        const tempDiv = document.createElement('div');
        
        // Set the HTML content
        tempDiv.innerHTML = html.trim();

        // Create a new container for sanitized content
        const sanitizedContainer = document.createElement('div');

        // Process all child nodes
        Array.from(tempDiv.childNodes).forEach(child => {
            const sanitizedChild = sanitizeNode(child);
            if (sanitizedChild) {
                sanitizedContainer.appendChild(sanitizedChild);
            }
        });

        return sanitizedContainer.innerHTML;
    } catch (error) {
        console.error('Error sanitizing HTML:', error);
        // Return the input encoded as text if sanitization fails
        return html.replace(/[<>&"']/g, char => ({
            '<': '&lt;',
            '>': '&gt;',
            '&': '&amp;',
            '"': '&quot;',
            "'": '&#39;'
        }[char]));
    }    function sanitizeNode(node) {
        try {
            // Handle text nodes
            if (node.nodeType === 3) {
                return node.cloneNode(true);
            }
            
            // Handle element nodes
            if (node.nodeType === 1) {
                const tag = node.tagName.toLowerCase();
                
                // Check if this tag is allowed
                if (!ALLOWED_TAGS.has(tag)) {
                    // For disallowed tags, return just their text content
                    return document.createTextNode(node.textContent);
                }
                
                // Create a new element of the allowed type
                const newElement = document.createElement(tag);
                
                // Copy allowed attributes
                Array.from(node.attributes).forEach(attr => {
                    if (ALLOWED_ATTRIBUTES.has(attr.name)) {
                        newElement.setAttribute(attr.name, attr.value);
                    }
                });
                
                // Special handling for links
                if (tag === 'a') {
                    newElement.setAttribute('target', '_blank');
                    newElement.setAttribute('rel', 'noopener noreferrer');
                }
                
                // Recursively sanitize and append child nodes
                Array.from(node.childNodes).forEach(child => {
                    const sanitizedChild = sanitizeNode(child);
                    if (sanitizedChild) {
                        newElement.appendChild(sanitizedChild);
                    }
                });
                
                return newElement;
            }
            
            // Ignore other node types
            return null;
        } catch (error) {
            console.error('Error sanitizing node:', error);
            return document.createTextNode(node.textContent || '');
        }
    }
}

function formatMessageContent(content, type = 'text') {
    if (!content || typeof content !== 'string') {
        console.warn('Invalid content provided to formatMessageContent:', content);
        return '';
    }
    
    try {
        // First decode HTML entities if needed
        const decodedContent = content.trim()
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"')
            .replace(/&amp;/g, '&');
        
        // Then sanitize the HTML
        let sanitizedContent = sanitizeHTML(decodedContent);
        
        // Add syntax highlighting for code blocks if any
        if (sanitizedContent.includes('<pre><code>')) {
            sanitizedContent = sanitizedContent.replace(
                /<pre><code>([\s\S]*?)<\/code><\/pre>/g,
                (_, code) => `<pre><code class="language-${type}">${code}</code></pre>`
            );
        }
        
        return sanitizedContent;
    } catch (error) {
        console.error('Error formatting message content:', error);
        // Return a safe version of the input as plain text if formatting fails
        return content.replace(/[<>&"']/g, char => ({
            '<': '&lt;',
            '>': '&gt;',
            '&': '&amp;',
            '"': '&quot;',
            "'": '&#39;'
        }[char]));
    }
}
