<template>
  <div 
    class="upload-zone glass-panel glass-panel-glow"
    :class="{ 'drag-over': isDragOver, 'uploading': isUploading }"
    @dragover.prevent="onDragOver"
    @dragleave="onDragLeave"
    @drop.prevent="onDrop"
    @click="triggerFileInput"
  >
    <input 
      type="file" 
      ref="fileInput" 
      class="file-input" 
      accept="image/*,application/pdf"
      @change="onFileSelected"
    />
    
    <div class="upload-content">
      <div class="icon-wrapper">
        <component :is="uploadIcon" class="icon-element" :class="{ 'pulsing': isUploading }" />
      </div>
      
      <h3>{{ uploadTitle }}</h3>
      <p class="upload-subtitle">{{ uploadSubtitle }}</p>
      
      <div v-if="errorMsg" class="error-banner">
        <component :is="alertIcon" class="error-icon" />
        <span>{{ errorMsg }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { UploadCloud, Loader, AlertTriangle } from '@lucide/vue';
import { uploadDocument } from '../services/api';

const emit = defineEmits(['document-uploaded']);

const fileInput = ref<HTMLInputElement | null>(null);
const isDragOver = ref(false);
const isUploading = ref(false);
const errorMsg = ref('');

const uploadIcon = computed(() => isUploading.value ? Loader : UploadCloud);
const alertIcon = AlertTriangle;

const uploadTitle = computed(() => {
  if (isUploading.value) return 'Processing Document...';
  return 'Upload Receipt or PDF';
});

const uploadSubtitle = computed(() => {
  if (isUploading.value) return 'Sending file to CV & OCR parser...';
  return 'Drag & drop your file here, or click to browse (PDF, PNG, JPG, WEBP)';
});

const triggerFileInput = () => {
  if (!isUploading.value) {
    fileInput.value?.click();
  }
};

const onDragOver = () => {
  isDragOver.value = true;
};

const onDragLeave = () => {
  isDragOver.value = false;
};

const processFile = async (file: File) => {
  // Validate file type (allow PDFs and any standard image format like PNG, JPG, WEBP)
  const isImage = file.type.startsWith('image/');
  const isPdf = file.type === 'application/pdf';
  if (!isImage && !isPdf) {
    errorMsg.value = 'Invalid file type. Please upload a PDF or an Image (PNG, JPG, WEBP).';
    return;
  }

  isUploading.value = true;
  errorMsg.value = '';

  try {
    const doc = await uploadDocument(file);
    emit('document-uploaded', doc);
  } catch (err: any) {
    errorMsg.value = err.message || 'Failed to upload document.';
  } finally {
    isUploading.value = false;
    isDragOver.value = false;
  }
};

const onDrop = (event: DragEvent) => {
  isDragOver.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (file) {
    processFile(file);
  }
};

const onFileSelected = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (file) {
    processFile(file);
  }
  // Clear the value so the same file can be uploaded again if needed
  if (fileInput.value) {
    fileInput.value.value = '';
  }
};
</script>

<style scoped>
.upload-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  border: 2px dashed rgba(255, 255, 255, 0.1);
  cursor: pointer;
  text-align: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  min-height: 220px;
}

.upload-zone:hover, .upload-zone.drag-over {
  border-color: var(--primary);
  background: rgba(123, 95, 246, 0.05);
}

.upload-zone.uploading {
  cursor: not-allowed;
  border-style: solid;
  border-color: var(--secondary);
  background: rgba(0, 212, 255, 0.02);
}

.file-input {
  display: none;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.icon-wrapper {
  background: rgba(255, 255, 255, 0.03);
  padding: 1.25rem;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  margin-bottom: 0.5rem;
}

.upload-zone:hover .icon-wrapper {
  border-color: var(--primary-glow);
  background: rgba(123, 95, 246, 0.1);
}

.icon-element {
  width: 2.5rem;
  height: 2.5rem;
  color: var(--text-secondary);
  transition: color 0.3s, transform 0.3s;
}

.upload-zone:hover .icon-element {
  color: var(--primary);
  transform: translateY(-2px);
}

.upload-zone.uploading .icon-element {
  color: var(--secondary);
}

.pulsing {
  animation: spin-slow 2s linear infinite;
}

h3 {
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.upload-subtitle {
  color: var(--text-muted);
  font-size: 0.875rem;
  max-width: 320px;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(244, 63, 94, 0.1);
  border: 1px solid rgba(244, 63, 94, 0.2);
  padding: 0.75rem 1rem;
  border-radius: 8px;
  color: var(--color-danger);
  font-size: 0.875rem;
  margin-top: 1rem;
  animation: slide-in 0.3s ease;
}

.error-icon {
  width: 1.25rem;
  height: 1.25rem;
  flex-shrink: 0;
}
</style>
