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
import { getConfColor } from '../lib/color';

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

</script>

<style scoped src="./DocumentDetails.css"></style>
