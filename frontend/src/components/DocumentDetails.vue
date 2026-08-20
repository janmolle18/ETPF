<template>
  <div class="details-container glass-panel">
    <div v-if="!document" class="no-doc-selected">
      <component :is="fileSearchIcon" class="no-doc-icon" />
      <h3>No Document Selected</h3>
      <p>Select a document from the list to view its extracted structured data and layouts.</p>
    </div>

    <div v-else-if="document.status === 'PROCESSING' || document.status === 'PENDING'" class="processing-state">
      <div class="loader-ring"></div>
      <h3>Analyzing Document...</h3>
      <p>The CV layout pipeline is identifying text regions and extracting receipt information.</p>
    </div>

    <div v-else-if="document.status === 'FAILED'" class="failed-state">
      <component :is="alertCircleIcon" class="error-icon" />
      <h3>Processing Failed</h3>
      <p>We could not process this document. Please check the file format and try again.</p>
    </div>

    <div v-else class="details-content">
      <!-- Header -->
      <div class="details-header">
        <div>
          <h3>{{ document.filename }}</h3>
          <span class="doc-id">ID: {{ document.id }}</span>
        </div>
        <div class="status-badge">Analysis Completed</div>
      </div>

      <!-- Navigation Tabs -->
      <div class="tabs-nav">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          class="tab-btn"
          :class="{ 'active': activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          <component :is="tab.icon" class="tab-icon" />
          <span>{{ tab.name }}</span>
        </button>
      </div>

      <!-- Tab Contents -->
      <div class="tab-body">

        <!-- Tab 0: Receipt Viewer -->
        <div v-if="activeTab === 'receipt'" class="tab-panel animate-fade receipt-panel">
          <div class="receipt-toolbar">
            <span class="receipt-label">{{ document.filename }}</span>
            <div class="receipt-actions">
              <a :href="fileUrl" :download="document.filename" class="receipt-action-btn">
                <component :is="downloadIcon" class="btn-icon" />
                Download
              </a>
              <button class="receipt-action-btn" @click="isReceiptFullscreen = true">
                <component :is="maximizeIcon" class="btn-icon" />
                Fullscreen
              </button>
            </div>
          </div>

          <div class="receipt-viewport">
            <img
              v-if="isImageFile"
              :src="imageUrl"
              @error="handleImageError"
              class="receipt-image"
              alt="Uploaded receipt"
            />
            <div v-else-if="isPdfFile" class="pdf-wrapper">
              <embed :src="fileUrl" type="application/pdf" class="receipt-pdf" />
            </div>
            <div v-else class="receipt-unsupported">
              <component :is="filePdfIcon" class="unsupported-icon" />
              <p>Preview not available for this file type.</p>
              <a :href="fileUrl" :download="document.filename" class="receipt-action-btn">
                <component :is="downloadIcon" class="btn-icon" />
                Download File
              </a>
            </div>
          </div>
        </div>

        <!-- Receipt fullscreen modal -->
        <Teleport to="body">
          <div v-if="isReceiptFullscreen" class="fullscreen-overlay animate-fade" @click.self="isReceiptFullscreen = false">
            <div class="fullscreen-container glass-panel">
              <div class="fullscreen-header">
                <h3>{{ document.filename }}</h3>
                <button class="close-fullscreen-btn" @click="isReceiptFullscreen = false">
                  <component :is="minimizeIcon" class="action-icon" />
                  <span>Close</span>
                </button>
              </div>
              <div class="fullscreen-body receipt-fullscreen-body">
                <img
                  v-if="isImageFile"
                  :src="imageUrl"
                  class="receipt-image-fullscreen"
                  alt="Uploaded receipt"
                />
                <embed
                  v-else-if="isPdfFile"
                  :src="fileUrl"
                  type="application/pdf"
                  class="receipt-pdf-fullscreen"
                />
              </div>
            </div>
          </div>
        </Teleport>

        <!-- Tab 1: Extracted Data -->
        <div v-if="activeTab === 'extracted'" class="tab-panel animate-fade">
          <div class="metadata-grid">
            <div class="meta-card">
              <component :is="buildingIcon" class="meta-card-icon" />
              <div class="meta-card-content">
                <span class="meta-label">Vendor</span>
                <span class="meta-value">{{ document.extracted_data?.vendor_name || 'N/A' }}</span>
                <span class="meta-sub">Tax ID: {{ document.extracted_data?.tax_id || 'N/A' }}</span>
              </div>
            </div>

            <div class="meta-card">
              <component :is="calendarIcon" class="meta-card-icon" />
              <div class="meta-card-content">
                <span class="meta-label">Date & ID</span>
                <span class="meta-value">{{ document.extracted_data?.date || 'N/A' }}</span>
                <span class="meta-sub">Phone: {{ document.extracted_data?.phone || 'N/A' }}</span>
              </div>
            </div>

            <div class="meta-card highlight">
              <component :is="receiptIcon" class="meta-card-icon" />
              <div class="meta-card-content">
                <span class="meta-label">Total Amount</span>
                <span class="meta-value currency">{{ document.extracted_data?.total_amount?.toFixed(2) }} {{ document.extracted_data?.currency || 'EUR' }}</span>
                <span class="meta-sub">VAT (19% Included): {{ document.extracted_data?.tax_amount?.toFixed(2) }} EUR</span>
              </div>
            </div>
          </div>

          <div class="line-items-section">
            <h4>Line Items</h4>
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Description</th>
                    <th class="text-right">Unit Price</th>
                    <th class="text-center">Qty</th>
                    <th class="text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(item, idx) in document.extracted_data?.line_items" :key="idx">
                    <td>{{ item.description }}</td>
                    <td class="text-right">{{ item.unit_price.toFixed(2) }}</td>
                    <td class="text-center">{{ item.quantity }}</td>
                    <td class="text-right font-semibold">{{ item.total.toFixed(2) }}</td>
                  </tr>
                  <tr v-if="!document.extracted_data?.line_items?.length">
                    <td colspan="4" class="text-center text-muted">No line items extracted.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Tab 2: Raw Text -->
        <div v-if="activeTab === 'raw'" class="tab-panel animate-fade raw-text-panel">
          <div class="panel-header">
            <span>OCR Plain Text Stream</span>
            <button class="copy-btn" @click="copyRawText">Copy Text</button>
          </div>
          <pre class="terminal-view"><code>{{ document.raw_text }}</code></pre>
        </div>

        <!-- Tab 3: Layout Bounding Boxes -->
        <div v-if="activeTab === 'layout'" class="tab-panel animate-fade layout-panel">
          <div class="layout-info-bar">
            <span>Interactive Layout Viewer</span>
            <div class="layout-actions">
              <button class="expand-btn" @click="toggleFullscreen">
                <component :is="maximizeIcon" class="action-icon" />
                <span>Fullscreen</span>
              </button>
              <small class="text-muted">Hover over coordinates to highlight bounding regions</small>
            </div>
          </div>

          <div class="layout-viewer-grid">
            <!-- Simulated Document Visualizer -->
            <div class="document-canvas-container">
              <div 
                class="document-canvas" 
                :style="{ 
                  aspectRatio: document.layout_data?.width && document.layout_data?.height 
                    ? `${document.layout_data.width}/${document.layout_data.height}` 
                    : '8.5/11' 
                }"
              >
                <!-- Original Image Underlay -->
                <img 
                  v-if="document"
                  :src="imageUrl" 
                  @error="handleImageError"
                  class="document-image-underlay" 
                  alt="Receipt Document"
                />
                <div class="canvas-grid-bg"></div>
                
                <!-- Bounding Box Overlays -->
                <OcrBlockIndicator 
                  v-for="(block, index) in document.layout_data?.blocks" 
                  :key="index"
                  :block="block"
                  :index="index"
                  :active="activeBlockIndex === index"
                  @mouseenter="activeBlockIndex = index"
                  @mouseleave="activeBlockIndex = null"
                />
              </div>
            </div>

            <!-- Bounding Box Coordinates List -->
            <div class="coordinates-list">
              <div 
                v-for="(block, index) in document.layout_data?.blocks" 
                :key="index"
                class="coordinate-row"
                :class="{ 'active': activeBlockIndex === index }"
                @mouseenter="activeBlockIndex = index"
                @mouseleave="activeBlockIndex = null"
              >
                <div class="coord-label">
                  <span class="coord-index">#{{ index + 1 }}</span>
                  <span class="coord-text">{{ block.text }}</span>
                </div>
                <div class="coord-metrics">
                  <span>x:{{ block.x.toFixed(0) }} y:{{ block.y.toFixed(0) }}</span>
                  <span class="coord-conf" :style="{ color: getConfColor(block.confidence) }">
                    {{ (block.confidence * 100).toFixed(0) }}%
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Fullscreen Modal Overlay (Teleported to body to bypass relative glassmorphism container clipping) -->
          <Teleport to="body">
            <div v-if="isFullscreen" class="fullscreen-overlay animate-fade" @click.self="toggleFullscreen">
              <div class="fullscreen-container glass-panel">
                <div class="fullscreen-header">
                  <h3>{{ document.filename }} — Fullscreen Layout Viewer</h3>
                  <button class="close-fullscreen-btn" @click="toggleFullscreen">
                    <component :is="minimizeIcon" class="action-icon" />
                    <span>Close</span>
                  </button>
                </div>
                <div class="fullscreen-body">
                  <div 
                    class="document-canvas fullscreen-canvas" 
                    :style="{ 
                      aspectRatio: document.layout_data?.width && document.layout_data?.height 
                        ? `${document.layout_data.width}/${document.layout_data.height}` 
                        : '8.5/11' 
                    }"
                  >
                    <!-- Original Image Underlay -->
                    <img 
                      v-if="document"
                      :src="imageUrl" 
                      @error="handleImageError"
                      class="document-image-underlay" 
                      alt="Receipt Document"
                    />
                    <div class="canvas-grid-bg"></div>
                    
                    <!-- Bounding Box Overlays -->
                    <OcrBlockIndicator 
                      v-for="(block, index) in document.layout_data?.blocks" 
                      :key="index"
                      :block="block"
                      :index="index"
                      :active="activeBlockIndex === index"
                      @mouseenter="activeBlockIndex = index"
                      @mouseleave="activeBlockIndex = null"
                    />
                  </div>
                </div>
              </div>
            </div>
          </Teleport>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import OcrBlockIndicator from './OcrBlockIndicator.vue';
import {
  FileSearch,
  Building,
  Calendar,
  Receipt,
  Terminal,
  Cpu,
  Database,
  AlertCircle,
  Maximize2,
  Minimize2,
  Download,
  FileText as FilePdf,
  ScanLine
} from '@lucide/vue';
import type { DocumentResponse } from '../services/api';
import { getDocumentFileUrl } from '../services/api';

const props = defineProps<{
  document: DocumentResponse | null;
}>();

const activeTab = ref<'receipt' | 'extracted' | 'raw' | 'layout'>('receipt');
const activeBlockIndex = ref<number | null>(null);
const isFullscreen = ref(false);
const isReceiptFullscreen = ref(false);

const imageErrorCount = ref(0);

const imageUrl = computed(() => {
  if (!props.document) return '';
  const baseUrl = getDocumentFileUrl(props.document.id, true);
  return imageErrorCount.value > 0
    ? `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}t=${Date.now()}`
    : baseUrl;
});

const fileUrl = computed(() => props.document ? getDocumentFileUrl(props.document.id) : '');
const isImageFile = computed(() => props.document?.content_type.startsWith('image/') ?? false);
const isPdfFile = computed(() => props.document?.content_type === 'application/pdf');

const handleImageError = () => {
  if (imageErrorCount.value < 5) {
    setTimeout(() => {
      imageErrorCount.value++;
    }, 2000);
  }
};

watch(() => props.document?.id, () => {
  imageErrorCount.value = 0;
  activeTab.value = 'receipt';
});

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value;
};

const fileSearchIcon = FileSearch;
const alertCircleIcon = AlertCircle;
const buildingIcon = Building;
const calendarIcon = Calendar;
const receiptIcon = Receipt;
const maximizeIcon = Maximize2;
const minimizeIcon = Minimize2;
const downloadIcon = Download;
const filePdfIcon = FilePdf;

const tabs = [
  { id: 'receipt', name: 'Beleg', icon: ScanLine },
  { id: 'extracted', name: 'Extracted Data', icon: Database },
  { id: 'raw', name: 'Raw OCR Text', icon: Terminal },
  { id: 'layout', name: 'Layout (CV)', icon: Cpu },
] as const;

const copyRawText = () => {
  if (props.document?.raw_text) {
    navigator.clipboard.writeText(props.document.raw_text);
    alert('Copied to clipboard!');
  }
};

const getConfColor = (conf: number) => {
  if (conf >= 0.9) return 'var(--color-success)';
  if (conf >= 0.7) return 'var(--color-warning)';
  return 'var(--color-danger)';
};


</script>

<style scoped>
.details-container {
  min-height: 520px;
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
}

.no-doc-selected, .processing-state, .failed-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-grow: 1;
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
  gap: 1rem;
}

.no-doc-icon, .error-icon {
  width: 3.5rem;
  height: 3.5rem;
  opacity: 0.25;
}

.error-icon {
  color: var(--color-danger);
  opacity: 0.8;
}

.loader-ring {
  width: 48px;
  height: 48px;
  border: 3px solid rgba(0, 212, 255, 0.1);
  border-radius: 50%;
  border-top-color: var(--secondary);
  animation: spin-slow 1s linear infinite;
  box-shadow: 0 0 10px rgba(0, 212, 255, 0.15);
}

.details-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  height: 100%;
}

.details-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1rem;
}

.doc-id {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.status-badge {
  background: rgba(123, 95, 246, 0.1);
  color: var(--primary);
  border: 1px solid var(--border-glow);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
}

/* Tab buttons */
.tabs-nav {
  display: flex;
  gap: 0.5rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.1rem;
}

.tab-btn {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary);
  padding: 0.6rem 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
  font-size: 0.9rem;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.02);
}

.tab-btn.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
}

.tab-icon {
  width: 1.1rem;
  height: 1.1rem;
}

.tab-body {
  flex-grow: 1;
}

.animate-fade {
  animation: slide-in 0.25s ease;
}

/* Metadata cards */
.metadata-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.meta-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  padding: 1rem;
  border-radius: 12px;
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.meta-card.highlight {
  background: rgba(123, 95, 246, 0.04);
  border-color: var(--border-glow);
}

.meta-card-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--primary);
  flex-shrink: 0;
  margin-top: 0.15rem;
}

.meta-card.highlight .meta-card-icon {
  color: var(--secondary);
}

.meta-card-content {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}

.meta-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  font-weight: 600;
}

.meta-value {
  font-size: 0.95rem;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.meta-value.currency {
  font-size: 1.15rem;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.meta-sub {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* Table styling */
.line-items-section h4 {
  margin-bottom: 0.75rem;
  font-size: 0.95rem;
}

.table-container {
  overflow-x: auto;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.875rem;
}

th, td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color);
}

th {
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-secondary);
  font-weight: 600;
}

tr:last-child td {
  border-bottom: none;
}

.text-right { text-align: right; }
.text-center { text-align: center; }
.font-semibold { font-weight: 600; }

/* Terminal view */
.raw-text-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.copy-btn {
  background: var(--border-glow);
  color: var(--primary);
  border: 1px solid rgba(123, 95, 246, 0.2);
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 600;
  transition: all 0.2s ease;
}

.copy-btn:hover {
  background: var(--primary-glow);
  color: var(--text-primary);
}

.terminal-view {
  background: #06080e;
  border: 1px solid var(--border-color);
  padding: 1.25rem;
  border-radius: 8px;
  font-family: 'Fira Code', 'Courier New', monospace;
  font-size: 0.825rem;
  color: #38bdf8;
  overflow-y: auto;
  max-height: 380px;
  white-space: pre-wrap;
}

/* Layout panel */
.layout-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.layout-info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
}

.layout-viewer-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 1.5rem;
  align-items: start;
}

@media (max-width: 768px) {
  .layout-viewer-grid {
    grid-template-columns: 1fr;
  }
}

.document-canvas-container {
  background: #0c0e15;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1rem;
  display: flex;
  justify-content: center;
}

.document-canvas {
  width: 100%;
  max-width: 320px;
  background: #ffffff;
  position: relative;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
  border-radius: 4px;
  overflow: hidden;
}

.document-image-underlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.85; /* Slightly semi-transparent so overlays stand out nicely */
  pointer-events: none; /* Crucial to let mouse hover pass through to bounding overlays */
}

.canvas-grid-bg {
  position: absolute;
  inset: 0;
  opacity: 0.03;
  background-image: linear-gradient(#000 1px, transparent 1px),
                    linear-gradient(90deg, #000 1px, transparent 1px);
  background-size: 20px 20px;
}

/* Bounding box overlays */
.bounding-overlay {
  position: absolute;
  border: 2px solid rgba(139, 92, 246, 0.85); /* Thicker neon violet border */
  background: rgba(139, 92, 246, 0.12); /* Slightly more present background fill */
  border-radius: 3px;
  transition: all 0.15s ease;
  cursor: help;
}

.bounding-overlay.highlighted {
  border-color: #00f0ff !important; /* Bright neon cyan */
  border-width: 2.5px !important;
  background: rgba(0, 240, 255, 0.25) !important; /* Semi-transparent cyan fill */
  box-shadow: 0 0 15px rgba(0, 240, 255, 0.9),
              inset 0 0 8px rgba(0, 240, 255, 0.5) !important; /* Strong outer & inner neon glow */
  z-index: 10;
}

.overlay-tooltip {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(-6px);
  background: #111827;
  color: #fff;
  border: 1px solid var(--border-color);
  padding: 0.35rem 0.5rem;
  border-radius: 4px;
  font-size: 0.7rem;
  white-space: nowrap;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
  z-index: 20;
}

.bounding-overlay:hover .overlay-tooltip {
  opacity: 1;
}

.tooltip-text {
  font-weight: 600;
}

.tooltip-conf {
  color: var(--text-muted);
  font-size: 0.65rem;
}

/* Coordinates list */
.coordinates-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-height: 380px;
  overflow-y: auto;
  padding-right: 4px;
}

.coordinate-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background: rgba(255, 255, 255, 0.01);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.coordinate-row:hover, .coordinate-row.active {
  background: rgba(255, 255, 255, 0.03);
  border-color: var(--border-glow);
}

.coordinate-row.active {
  box-shadow: inset 3px 0 0 0 var(--primary);
  border-color: rgba(123, 95, 246, 0.3);
}

.coord-label {
  display: flex;
  gap: 0.5rem;
  min-width: 0;
}

.coord-index {
  color: var(--text-muted);
  font-weight: 600;
}

.coord-text {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.coord-metrics {
  display: flex;
  gap: 0.75rem;
  color: var(--text-muted);
  font-family: monospace;
}

.coord-conf {
  font-weight: 700;
}

/* Fullscreen modal styling */
.fullscreen-overlay {
  position: fixed;
  inset: 0;
  background: rgba(3, 7, 18, 0.92); /* Darker backdrop to focus on image */
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem; /* Minimal padding to use all screen space */
}

.fullscreen-container {
  width: 98vw;
  height: 98vh;
  max-width: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  background: rgba(17, 24, 39, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 1rem;
  gap: 1rem;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
}

.fullscreen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.75rem;
}

.fullscreen-header h3 {
  font-size: 1.2rem;
  color: var(--text-primary);
  font-weight: 600;
}

.fullscreen-body {
  flex-grow: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  background: #020408; /* Darkest contrast backdrop */
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.03);
  padding: 0.5rem;
}

.fullscreen-canvas {
  height: 100%;
  width: auto;
  max-width: 100% !important; /* Override standard 320px bounds */
  max-height: 100% !important;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8);
  border: 1.5px solid rgba(255, 255, 255, 0.15);
}

.expand-btn, .close-fullscreen-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(123, 95, 246, 0.1);
  color: var(--primary);
  border: 1px solid rgba(123, 95, 246, 0.2);
  padding: 0.4rem 0.8rem;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  transition: all 0.2s ease;
}

.expand-btn:hover, .close-fullscreen-btn:hover {
  background: var(--primary-glow);
  color: #fff;
  border-color: var(--primary);
  box-shadow: 0 0 12px rgba(123, 95, 246, 0.35);
}

.action-icon {
  width: 1rem;
  height: 1rem;
}

.layout-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

/* Receipt viewer */
.receipt-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.receipt-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.receipt-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 55%;
}

.receipt-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.receipt-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: rgba(123, 95, 246, 0.08);
  color: var(--primary);
  border: 1px solid rgba(123, 95, 246, 0.2);
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.2s ease;
}

.receipt-action-btn:hover {
  background: var(--primary-glow);
  color: #fff;
  border-color: var(--primary);
  box-shadow: 0 0 10px rgba(123, 95, 246, 0.3);
}

.btn-icon {
  width: 0.95rem;
  height: 0.95rem;
}

.receipt-viewport {
  background: #f0f0f0;
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  min-height: 420px;
  max-height: 560px;
  border: 1px solid var(--border-color);
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.2);
}

.receipt-image {
  display: block;
  max-width: 100%;
  max-height: 560px;
  object-fit: contain;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}

.pdf-wrapper {
  width: 100%;
  height: 100%;
  min-height: 420px;
}

.receipt-pdf {
  width: 100%;
  height: 520px;
  border: none;
  display: block;
}

.receipt-unsupported {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 3rem;
  color: var(--text-muted);
}

.unsupported-icon {
  width: 3rem;
  height: 3rem;
  opacity: 0.3;
}

.receipt-fullscreen-body {
  background: #e8e8e8;
  padding: 1rem;
  overflow: auto;
}

.receipt-image-fullscreen {
  display: block;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  margin: auto;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
}

.receipt-pdf-fullscreen {
  width: 100%;
  height: 100%;
  border: none;
}
</style>
