// Default column configuration
let tableColumns = [
    { id: 'id', label: 'ID', visible: true, order: 0 },
    { id: 'message', label: 'Message', visible: true, order: 1 },
    { id: 'type', label: 'Type', visible: true, order: 2 },
    { id: 'status', label: 'Status', visible: true, order: 3 },
    { id: 'created_at', label: 'Created At', visible: true, order: 4 },
    { id: 'updated_at', label: 'Updated At', visible: true, order: 5 },
    { id: 'actions', label: 'Actions', visible: true, order: 6, locked: true }
];

class TableManager {
    constructor(tableId, modalId) {
        this.table = document.getElementById(tableId);
        this.modal = document.getElementById(modalId);
        this.columnList = this.modal.querySelector('#column-list');
        this.columnSearch = this.modal.querySelector('#column-search');
        this.resetButton = this.modal.querySelector('#reset-columns');
        this.applyButton = this.modal.querySelector('#apply-columns');
        this.cancelButton = this.modal.querySelector('#cancel-columns');
        
        this.columns = [...tableColumns];
        this.tempColumns = null; // For storing temporary changes
        
        // Load saved configuration from localStorage
        this.loadConfiguration();
        
        // Initialize the column chooser modal
        this.initColumnChooser();
        
        // Initialize event listeners
        this.initEventListeners();
        
        // Initial table update
        this.updateTableColumns();
    }

    loadConfiguration() {
        const savedConfig = localStorage.getItem('tableColumnConfig');
        if (savedConfig) {
            try {
                const config = JSON.parse(savedConfig);
                this.columns = this.columns.map(col => ({
                    ...col,
                    visible: config[col.id]?.visible ?? col.visible,
                    order: config[col.id]?.order ?? col.order
                }));
            } catch (e) {
                console.error('Error loading column configuration:', e);
            }
        }
    }

    saveConfiguration() {
        const config = {};
        this.columns.forEach(col => {
            config[col.id] = {
                visible: col.visible,
                order: col.order
            };
        });
        localStorage.setItem('tableColumnConfig', JSON.stringify(config));
    }

    initColumnChooser() {
        this.updateColumnList();
        this.setupDragAndDrop();
        this.setupSearch();
    }

    initEventListeners() {
        // Reset button
        this.resetButton?.addEventListener('click', () => {
            this.tempColumns = [...tableColumns];
            this.updateColumnList();
        });

        // Apply button
        this.applyButton?.addEventListener('click', () => {
            if (this.tempColumns) {
                this.columns = [...this.tempColumns];
                this.saveConfiguration();
                this.updateTableColumns();
            }
            this.closeModal();
        });

        // Cancel button
        this.cancelButton?.addEventListener('click', () => {
            this.closeModal();
        });
    }

    setupSearch() {
        this.columnSearch?.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const items = this.columnList.querySelectorAll('.column-item');
            
            items.forEach(item => {
                const columnName = item.querySelector('.column-name').textContent.toLowerCase();
                const matches = columnName.includes(searchTerm);
                item.style.display = matches ? '' : 'none';
            });
        });
    }

    setupDragAndDrop() {
        const items = this.columnList.querySelectorAll('.column-item');
        
        items.forEach(item => {
            if (item.dataset.locked === 'true') return;
            
            item.setAttribute('draggable', true);
            
            item.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', item.dataset.id);
                item.classList.add('dragging');
            });

            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
            });

            item.addEventListener('dragover', (e) => {
                e.preventDefault();
                const draggingItem = this.columnList.querySelector('.dragging');
                if (draggingItem !== item) {
                    item.classList.add('drag-over');
                }
            });

            item.addEventListener('dragleave', () => {
                item.classList.remove('drag-over');
            });

            item.addEventListener('drop', (e) => {
                e.preventDefault();
                item.classList.remove('drag-over');
                const draggedId = e.dataTransfer.getData('text/plain');
                const draggedIndex = this.tempColumns.findIndex(col => col.id === draggedId);
                const dropIndex = this.tempColumns.findIndex(col => col.id === item.dataset.id);
                
                if (draggedIndex !== -1 && dropIndex !== -1) {
                    const [draggedColumn] = this.tempColumns.splice(draggedIndex, 1);
                    this.tempColumns.splice(dropIndex, 0, draggedColumn);
                    this.updateColumnOrders();
                    this.updateColumnList();
                }
            });
        });
    }

    updateColumnOrders() {
        this.tempColumns.forEach((col, index) => {
            col.order = index;
        });
    }

    updateColumnList() {
        if (!this.tempColumns) {
            this.tempColumns = [...this.columns];
        }

        const sortedColumns = [...this.tempColumns].sort((a, b) => a.order - b.order);
        this.columnList.innerHTML = sortedColumns.map(column => `
            <li class="column-item${column.locked ? ' locked' : ''}" 
                data-id="${column.id}"
                data-locked="${column.locked || false}">
                <div class="drag-handle" aria-hidden="true">
                    <i class="fas fa-grip-vertical"></i>
                </div>
                <div class="column-info">
                    <div class="column-name">${column.label}</div>
                    ${column.description ? `<div class="column-description">${column.description}</div>` : ''}
                </div>
                <label class="switch-container">
                    <div class="switch">
                        <input type="checkbox" 
                               ${column.visible ? 'checked' : ''} 
                               ${column.locked ? 'disabled' : ''}
                               onchange="window.tableManager.toggleColumnVisibility('${column.id}')">
                        <span class="slider"></span>
                    </div>
                </label>
            </li>
        `).join('');

        this.setupDragAndDrop();
    }

    toggleColumnVisibility(columnId) {
        const column = this.tempColumns.find(col => col.id === columnId);
        if (column && !column.locked) {
            column.visible = !column.visible;
        }
    }

    updateTableColumns() {
        // Implement table column visibility and order update logic here
        const sortedColumns = [...this.columns].sort((a, b) => a.order - b.order);
        sortedColumns.forEach(column => {
            const cells = this.table.querySelectorAll(`[data-column="${column.id}"]`);
            cells.forEach(cell => {
                cell.style.display = column.visible ? '' : 'none';
            });
        });
    }

    closeModal() {
        this.tempColumns = null;
        this.columnSearch.value = '';
        this.modal.classList.add('hidden');
    }
}

// Initialize table manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const tableManager = new TableManager('events-table', 'column-chooser-modal');
    
    // Add click handler for the customize columns button
    const customizeBtn = document.querySelector('#customize-columns-btn');
    if (customizeBtn) {
        customizeBtn.addEventListener('click', () => {
            tableManager.showModal();
        });
    }
});
