<template>
  <div class="app-container">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="brand">
        <component :is="layersIcon" class="brand-icon" />
        <div class="brand-info">
          <h2>ETPF</h2>
          <span>Tax Engine Scaffold</span>
        </div>
      </div>

      <nav class="nav-menu">
        <a href="#" class="nav-item" :class="{ 'active': currentTab === 'dashboard' }" @click.prevent="currentTab = 'dashboard'">
          <component :is="activityIcon" class="nav-icon" />
          <span>Dashboard</span>
        </a>
        <a href="#" class="nav-item" :class="{ 'active': currentTab === 'sandbox' }" @click.prevent="currentTab = 'sandbox'">
          <component :is="beakerIcon" class="nav-icon" />
          <span>OCR Sandbox</span>
        </a>
      </nav>

      <div class="status-footer">
        <div class="connection-status" :class="{ 'connected': isBackendConnected }">
          <component :is="serverIcon" class="status-icon" />
          <div class="status-info">
            <span class="status-title">Backend Status</span>
            <span class="status-label">{{ isBackendConnected ? 'Online' : 'Offline' }}</span>
          </div>
          <span class="status-indicator"></span>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
      <header class="content-header">
        <div>
          <h1>Document Processing Hub</h1>
          <p class="subtitle">Extract tax metadata, line items, and bounding box layouts from receipts & invoices.</p>
        </div>
      </header>

      <!-- Statistics Dashboard Row (Only on Dashboard tab) -->
      <section v-if="currentTab === 'dashboard'" class="stats-row animate-fade">
        <div class="stats-card glass-panel glass-panel-glow">
          <div class="stats-icon-container bg-primary-glow">
            <component :is="landmarkIcon" class="stats-card-icon text-primary" />
          </div>
          <div class="stats-info">
            <span class="stats-label">Total Expenditures</span>
            <h3 class="stats-value">{{ totalExpenses.toFixed(2) }} EUR</h3>
            <span class="stats-sub">From processed receipts</span>
          </div>
        </div>

        <div class="stats-card glass-panel glass-panel-glow">
          <div class="stats-icon-container bg-secondary-glow">
            <component :is="trendingUpIcon" class="stats-card-icon text-secondary" />
          </div>
          <div class="stats-info">
            <span class="stats-label">Extracted VAT</span>
            <h3 class="stats-value">{{ totalVat.toFixed(2) }} EUR</h3>
            <span class="stats-sub">Total deductible tax</span>
          </div>
        </div>

        <div class="stats-card glass-panel glass-panel-glow">
          <div class="stats-icon-container bg-success-glow">
            <component :is="fileCheckIcon" class="stats-card-icon text-success" />
          </div>
          <div class="stats-info">
            <span class="stats-label">Documents</span>
            <h3 class="stats-value">{{ docCounts.completed }}/{{ docCounts.total }}</h3>
            <span class="stats-sub">
              {{ docCounts.processing }} active, {{ docCounts.failed }} failed
            </span>
          </div>
        </div>

        <div class="stats-card glass-panel glass-panel-glow">
          <div class="stats-icon-container bg-accent-glow">
            <component :is="percentIcon" class="stats-card-icon text-accent" />
          </div>
          <div class="stats-info">
            <span class="stats-label">OCR Reliability</span>
            <h3 class="stats-value">{{ avgConfidence.toFixed(0) }}%</h3>
            <span class="stats-sub">Average conf score</span>
          </div>
        </div>
      </section>

      <!-- Dashboard Grid -->
      <div v-if="currentTab === 'dashboard'" class="dashboard-grid animate-fade">
        <!-- Left Side: Actions and Lists -->
        <div class="dashboard-left">
          <DocumentUpload @document-uploaded="handleDocumentUploaded" />
          <div class="divider"></div>
          <DocumentList 
            :documents="documents" 
            :selectedId="selectedId" 
            @select="handleDocumentSelect"
            @document-deleted="handleDocumentDeleted"
          />
        </div>

        <!-- Right Side: Details and Analysis -->
        <div class="dashboard-right">
          <DocumentDetails :document="selectedDocument" />
        </div>
      </div>

      <!-- OCR Developer Sandbox Component -->
      <OcrSandbox v-else-if="currentTab === 'sandbox'" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { Layers, Activity, Server, TrendingUp, Percent, FileCheck, Landmark, Beaker } from '@lucide/vue';
import DocumentUpload from './components/DocumentUpload.vue';
import DocumentList from './components/DocumentList.vue';
import DocumentDetails from './components/DocumentDetails.vue';
import OcrSandbox from './components/OcrSandbox.vue';
import { listDocuments, getDocument } from './services/api';
import type { DocumentResponse } from './services/api';

const layersIcon = Layers;
const activityIcon = Activity;
const serverIcon = Server;
const trendingUpIcon = TrendingUp;
const percentIcon = Percent;
const fileCheckIcon = FileCheck;
const landmarkIcon = Landmark;
const beakerIcon = Beaker;

const currentTab = ref('dashboard');

const totalExpenses = computed(() => {
  return documents.value
    .filter(doc => doc.status === 'COMPLETED' && doc.extracted_data?.total_amount)
    .reduce((sum, doc) => sum + (doc.extracted_data?.total_amount || 0), 0);
});

const totalVat = computed(() => {
  return documents.value
    .filter(doc => doc.status === 'COMPLETED' && doc.extracted_data?.tax_amount)
    .reduce((sum, doc) => sum + (doc.extracted_data?.tax_amount || 0), 0);
});

const docCounts = computed(() => {
  const total = documents.value.length;
  const completed = documents.value.filter(d => d.status === 'COMPLETED').length;
  const failed = documents.value.filter(d => d.status === 'FAILED').length;
  const processing = documents.value.filter(d => d.status === 'PROCESSING' || d.status === 'PENDING').length;
  return { total, completed, failed, processing };
});

const avgConfidence = computed(() => {
  const completedDocs = documents.value.filter(
    doc => doc.status === 'COMPLETED' && doc.layout_data?.blocks
  );
  if (completedDocs.length === 0) return 0;
  
  let totalConf = 0;
  let totalBlocks = 0;
  completedDocs.forEach(doc => {
    doc.layout_data?.blocks?.forEach(block => {
      totalConf += block.confidence || 0;
      totalBlocks++;
    });
  });
  return totalBlocks > 0 ? (totalConf / totalBlocks) * 100 : 0;
});

const documents = ref<DocumentResponse[]>([]);
const selectedDocument = ref<DocumentResponse | null>(null);
const selectedId = ref<string | null>(null);
const isBackendConnected = ref(false);

let pollInterval: number | null = null;

const fetchDocumentsList = async () => {
  try {
    const list = await listDocuments();
    documents.value = list;
    isBackendConnected.value = true;
    
    // Check if we need to start/stop polling
    checkPollingRequirements();
  } catch (err) {
    console.error('Failed to connect to backend:', err);
    isBackendConnected.value = false;
  }
};

const handleDocumentSelect = async (doc: DocumentResponse) => {
  selectedId.value = doc.id;
  // If completed, fetch full details (including layout and raw text)
  if (doc.status === 'COMPLETED' || doc.status === 'FAILED') {
    try {
      const fullDoc = await getDocument(doc.id);
      selectedDocument.value = fullDoc;
    } catch (err) {
      console.error('Error fetching document details:', err);
      selectedDocument.value = doc;
    }
  } else {
    // If pending/processing, show the list version (with details-loader)
    selectedDocument.value = doc;
  }
};

const handleDocumentUploaded = async (newDoc: DocumentResponse) => {
  await fetchDocumentsList();
  // Auto-select the newly uploaded doc
  await handleDocumentSelect(newDoc);
};

const handleDocumentDeleted = (deletedId: string) => {
  documents.value = documents.value.filter(d => d.id !== deletedId);
  if (selectedId.value === deletedId) {
    selectedId.value = null;
    selectedDocument.value = null;
  }
};

// Check if any documents are in processing state. If so, poll them.
const checkPollingRequirements = () => {
  const activeProcessing = documents.value.some(
    doc => doc.status === 'PROCESSING' || doc.status === 'PENDING'
  );

  if (activeProcessing) {
    if (!pollInterval) {
      pollInterval = setInterval(pollActiveDocuments, 2000) as unknown as number;
    }
  } else {
    stopPolling();
  }
};

const pollActiveDocuments = async () => {
  try {
    const list = await listDocuments();
    documents.value = list;
    isBackendConnected.value = true;
    
    // Update active document details if currently selected item was updated
    if (selectedId.value) {
      const currentDoc = documents.value.find(d => d.id === selectedId.value);
      if (currentDoc) {
        if (currentDoc.status === 'COMPLETED' || currentDoc.status === 'FAILED') {
          // It just finished processing! Fetch full info.
          const fullDoc = await getDocument(selectedId.value);
          selectedDocument.value = fullDoc;
        } else {
          // Still processing, update general status
          selectedDocument.value = currentDoc;
        }
      }
    }

    checkPollingRequirements();
  } catch (err) {
    console.error('Error polling documents:', err);
  }
};

const stopPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
};

onMounted(() => {
  fetchDocumentsList();
  // Poll general status occasionally even if no active uploads, to detect backend reconnects
  setInterval(() => {
    if (!pollInterval) {
      fetchDocumentsList();
    }
  }, 10000);
});

onUnmounted(() => {
  stopPolling();
});
</script>

<style scoped>
.brand {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.5rem;
  margin-bottom: 2rem;
}

.brand-icon {
  width: 2.25rem;
  height: 2.25rem;
  color: var(--primary);
  filter: drop-shadow(0 0 8px var(--primary-glow));
}

.brand-info h2 {
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #fff 30%, var(--primary) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.brand-info span {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  font-weight: 600;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex-grow: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.8rem 1rem;
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: 10px;
  font-size: 0.95rem;
  font-weight: 500;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.nav-item:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.02);
}

.nav-item.active {
  color: var(--primary);
  background: rgba(123, 95, 246, 0.06);
  border-color: rgba(123, 95, 246, 0.1);
}

.nav-icon {
  width: 1.25rem;
  height: 1.25rem;
}

.status-footer {
  border-top: 1px solid var(--border-color);
  padding-top: 1.5rem;
}

/* Connection status container */
.connection-status {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  padding: 0.75rem 1rem;
  border-radius: 12px;
  position: relative;
}

.status-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: var(--color-danger);
}

.connection-status.connected .status-icon {
  color: var(--color-success);
}

.status-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex-grow: 1;
}

.status-title {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
}

.status-label {
  font-size: 0.85rem;
  font-weight: 700;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-danger);
  box-shadow: 0 0 6px var(--color-danger);
}

.connection-status.connected .status-indicator {
  background: var(--color-success);
  box-shadow: 0 0 6px var(--color-success);
}

/* Dashboard main layouts */
.content-header h1 {
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  background: linear-gradient(135deg, #fff 40%, var(--text-secondary) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 0.4rem;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 1rem;
}

.dashboard-left {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.divider {
  height: 1px;
  background: var(--border-color);
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.5rem;
  width: 100%;
}

.stats-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.15rem 1.25rem;
  background: rgba(18, 24, 38, 0.4);
  border: 1px solid var(--border-color);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.stats-icon-container {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 3rem;
  height: 3rem;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  flex-shrink: 0;
}

.bg-primary-glow {
  background: rgba(123, 95, 246, 0.08);
  border-color: rgba(123, 95, 246, 0.2);
}
.bg-secondary-glow {
  background: rgba(0, 212, 255, 0.08);
  border-color: rgba(0, 212, 255, 0.2);
}
.bg-success-glow {
  background: rgba(29, 185, 84, 0.08);
  border-color: rgba(29, 185, 84, 0.2);
}
.bg-accent-glow {
  background: rgba(186, 85, 211, 0.08);
  border-color: rgba(186, 85, 211, 0.2);
}

.stats-card-icon {
  width: 1.35rem;
  height: 1.35rem;
}

.text-primary { color: var(--primary); }
.text-secondary { color: var(--secondary); }
.text-success { color: var(--color-success); }
.text-accent { color: var(--accent); }

.stats-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}

.stats-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.stats-value {
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  line-height: 1.2;
}

.stats-sub {
  font-size: 0.7rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
