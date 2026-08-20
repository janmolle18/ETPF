<template>
  <div class="document-list-container">
    <div class="list-header">
      <h2>Recent Documents</h2>
      <span class="count-badge">{{ filteredDocuments.length }}</span>
    </div>

    <!-- Search & Filter Controls -->
    <div class="filter-controls">
      <div class="search-box">
        <component :is="searchIcon" class="search-icon-element" />
        <input 
          type="text" 
          v-model="searchQuery" 
          placeholder="Search by name or vendor..." 
          class="search-input"
        />
        <button v-if="searchQuery" class="clear-btn" @click="searchQuery = ''">&times;</button>
      </div>

      <div class="filter-row">
        <button 
          v-for="status in statusOptions" 
          :key="status.value"
          class="filter-tab"
          :class="{ 'active': statusFilter === status.value }"
          @click="statusFilter = status.value"
        >
          {{ status.label }}
        </button>
      </div>
    </div>

    <div v-if="documents.length === 0" class="empty-state">
      <component :is="fileTextIcon" class="empty-icon" />
      <p>No documents uploaded yet.</p>
    </div>

    <div v-else-if="filteredDocuments.length === 0" class="empty-state">
      <component :is="searchIcon" class="empty-icon" />
      <p>No documents match your filters.</p>
    </div>

    <div v-else class="list-wrapper">
      <div 
        v-for="doc in filteredDocuments" 
        :key="doc.id"
        class="document-item glass-panel"
        :class="{ 'active': selectedId === doc.id, 'failed': doc.status === 'FAILED' }"
        @click="$emit('select', doc)"
      >
        <div class="doc-icon-container">
          <component :is="getFileIcon(doc.content_type)" class="doc-type-icon" />
        </div>
        
        <div class="doc-details">
          <h4 class="doc-name" :title="doc.filename">{{ doc.filename }}</h4>
          <span class="doc-date">{{ formatDate(doc.created_at) }}</span>
        </div>

        <div class="doc-status-and-action">
          <div class="status-pill" :class="doc.status.toLowerCase()">
            <span class="status-dot"></span>
            <span class="status-text">{{ doc.status }}</span>
          </div>

          <button 
            class="delete-btn" 
            @click.stop="confirmDelete(doc.id)"
            title="Delete document"
          >
            <component :is="trashIcon" class="trash-icon" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { 
  FileText, 
  FileSpreadsheet, 
  FileImage, 
  Trash2,
  Search
} from '@lucide/vue';
import { deleteDocument } from '../services/api';
import type { DocumentResponse } from '../services/api';

const props = defineProps<{
  documents: DocumentResponse[];
  selectedId: string | null;
}>();

const emit = defineEmits(['select', 'document-deleted']);

const fileTextIcon = FileText;
const trashIcon = Trash2;
const searchIcon = Search;

const searchQuery = ref('');
const statusFilter = ref<'ALL' | 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'>('ALL');

const statusOptions = [
  { label: 'All', value: 'ALL' },
  { label: 'Pending', value: 'PENDING' },
  { label: 'Processing', value: 'PROCESSING' },
  { label: 'Completed', value: 'COMPLETED' },
  { label: 'Failed', value: 'FAILED' }
] as const;

const filteredDocuments = computed(() => {
  return props.documents.filter(doc => {
    const matchesSearch = searchQuery.value
      ? doc.filename.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
        doc.extracted_data?.vendor_name?.toLowerCase().includes(searchQuery.value.toLowerCase())
      : true;

    const matchesStatus = statusFilter.value === 'ALL'
      ? true
      : doc.status === statusFilter.value;

    return matchesSearch && matchesStatus;
  });
});

const getFileIcon = (contentType: string) => {
  if (contentType.includes('pdf')) return FileText;
  if (contentType.includes('spreadsheet') || contentType.includes('excel')) return FileSpreadsheet;
  if (contentType.includes('image/')) return FileImage;
  return FileText;
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString(undefined, { 
    month: 'short', 
    day: 'numeric', 
    hour: '2-digit', 
    minute: '2-digit' 
  });
};

const confirmDelete = async (id: string) => {
  if (confirm('Are you sure you want to delete this document?')) {
    try {
      await deleteDocument(id);
      emit('document-deleted', id);
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  }
};
</script>

<style scoped>
.document-list-container {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.list-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

h2 {
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.count-badge {
  background: var(--border-glow);
  color: var(--primary);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  border: 1px solid rgba(123, 95, 246, 0.2);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  border: 1px dashed var(--border-color);
  border-radius: 16px;
  color: var(--text-muted);
  text-align: center;
  gap: 0.75rem;
}

.empty-icon {
  width: 2.5rem;
  height: 2.5rem;
  opacity: 0.4;
}

.list-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 520px;
  overflow-y: auto;
  padding-right: 4px;
}

.document-item {
  display: flex;
  align-items: center;
  padding: 0.85rem 1rem;
  gap: 1rem;
  cursor: pointer;
  background: rgba(18, 24, 38, 0.4);
  border: 1px solid var(--border-color);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.document-item:hover {
  transform: translateX(4px);
  border-color: rgba(255, 255, 255, 0.15);
  background: rgba(18, 24, 38, 0.6);
}

.document-item.active {
  border-color: var(--primary);
  background: rgba(123, 95, 246, 0.04);
  box-shadow: inset 3px 0 0 0 var(--primary);
}

.doc-icon-container {
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.03);
  padding: 0.65rem;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.document-item.active .doc-icon-container {
  color: var(--primary);
  border-color: var(--border-glow);
  background: rgba(123, 95, 246, 0.08);
}

.doc-type-icon {
  width: 1.25rem;
  height: 1.25rem;
}

.doc-details {
  flex-grow: 1;
  min-width: 0;
}

.doc-name {
  font-size: 0.925rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 0.2rem;
}

.doc-date {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.doc-status-and-action {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* Status Pills */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.status-pill.completed {
  background: rgba(29, 185, 84, 0.1);
  color: var(--color-success);
  border: 1px solid rgba(29, 185, 84, 0.15);
}

.status-pill.completed .status-dot {
  background: var(--color-success);
  box-shadow: 0 0 6px var(--color-success);
}

.status-pill.processing {
  background: rgba(0, 212, 255, 0.1);
  color: var(--color-processing);
  border: 1px solid rgba(0, 212, 255, 0.15);
  animation: pulse-glow 2s infinite ease-in-out;
}

.status-pill.processing .status-dot {
  background: var(--color-processing);
}

.status-pill.pending {
  background: rgba(245, 158, 11, 0.1);
  color: var(--color-warning);
  border: 1px solid rgba(245, 158, 11, 0.15);
}

.status-pill.pending .status-dot {
  background: var(--color-warning);
}

.status-pill.failed {
  background: rgba(244, 63, 94, 0.1);
  color: var(--color-danger);
  border: 1px solid rgba(244, 63, 94, 0.15);
}

.status-pill.failed .status-dot {
  background: var(--color-danger);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.delete-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.4rem;
  border-radius: 6px;
  opacity: 0;
  transition: all 0.2s ease;
}

.document-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: var(--color-danger);
  background: rgba(244, 63, 94, 0.08);
}

.trash-icon {
  width: 1.1rem;
  height: 1.1rem;
}

/* Filter Controls Styles */
.filter-controls {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
}

.search-icon-element {
  position: absolute;
  left: 0.85rem;
  width: 1rem;
  height: 1rem;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.55rem 2.2rem 0.55rem 2.2rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 0.875rem;
  outline: none;
  transition: all 0.2s ease;
}

.search-input:focus {
  border-color: var(--primary);
  background: rgba(123, 95, 246, 0.02);
  box-shadow: 0 0 8px var(--primary-glow);
}

.clear-btn {
  position: absolute;
  right: 0.75rem;
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 1.1rem;
  cursor: pointer;
}

.clear-btn:hover {
  color: var(--text-primary);
}

.filter-row {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
}

.filter-tab {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  padding: 0.25rem 0.55rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-tab:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.04);
}

.filter-tab.active {
  color: var(--primary);
  background: rgba(123, 95, 246, 0.06);
  border-color: rgba(123, 95, 246, 0.2);
}
</style>
