<template>
  <div 
    class="game-bounding-overlay"
    :class="{ 'highlighted': active }"
    :style="{
      left: block.x + '%',
      top: block.y + '%',
      width: block.width + '%',
      height: block.height + '%',
      borderColor: getBoxBorderColor(block),
      backgroundColor: getBoxBgColor(block)
    }"
    @mouseenter="$emit('mouseenter')"
    @mouseleave="$emit('mouseleave')"
  >
    <!-- Healed / Rule Text Tag at top-right corner -->
    <div 
      v-if="block.healed || block.original_text" 
      class="healed-lightning-badge"
      :title="block.healed ? 'Optimized via Self-Healing' : 'Postprocessed via Rules'"
    >
      {{ block.healed ? 'H' : 'R' }}
    </div>

    <!-- Floating HUD status capsule (visible on hover / active selection) -->
    <div class="game-hud-capsule" :class="{ 'visible': active }">
      
      <!-- Top Title row showing status -->
      <div class="hud-header">
        <span class="hud-index">BLOCK #{{ index + 1 }}</span>
        <span v-if="block.healed" class="hud-healed-tag">
          OPTIMIZED<template v-if="block.confidence_gain"> (+{{ Math.round(block.confidence_gain) }}%)</template>
        </span>
        <span v-else-if="block.original_text && block.original_text !== block.text" class="hud-rule-tag">
          RULE FIXED
        </span>
        <span v-else class="hud-scan-tag">RAW SCAN</span>
      </div>

      <!-- Bars Row -->
      <div class="hud-bars">
        <!-- Confidence (Blue HP Bar) -->
        <div class="hud-bar-container">
          <div class="hud-bar-label text-blue">CONF</div>
          <div class="hud-bar-track">
            <template v-if="block.healed && block.confidence_gain">
              <div 
                class="hud-bar-fill fill-dark-blue" 
                :style="{ width: Math.max(0, Math.round(block.confidence * 100 - block.confidence_gain)) + '%' }"
              ></div>
              <div 
                class="hud-bar-fill fill-gain-blue" 
                :style="{ width: Math.round(block.confidence_gain) + '%' }"
              ></div>
            </template>
            <template v-else>
              <div 
                class="hud-bar-fill fill-blue" 
                :style="{ width: (block.confidence * 100) + '%' }"
              ></div>
            </template>
          </div>
          
          <div class="hud-bar-val text-blue">
            {{ (block.confidence * 100).toFixed(0) }}%
          </div>
        </div>

        <!-- Match Accuracy (Green Bar, if present) -->
        <div v-if="block.accuracy !== undefined" class="hud-bar-container">
          <div class="hud-bar-label text-green">MATCH</div>
          <div class="hud-bar-track">
            <div 
              class="hud-bar-fill fill-green" 
              :style="{ width: block.accuracy + '%' }"
            ></div>
          </div>
          <div class="hud-bar-val text-green">{{ block.accuracy.toFixed(0) }}%</div>
        </div>
      </div>

      <!-- Before and After Text Spelling Upgrade Row -->
      <div 
        v-if="block.original_text && block.original_text !== block.text" 
        class="hud-text-change"
      >
        <span class="hud-label-text">FIX</span>
        <span class="hud-text-before" :title="block.original_text">"{{ block.original_text }}"</span>
        <span class="hud-arrow">→</span>
        <span class="hud-text-after" :title="block.text">"{{ block.text }}"</span>
      </div>

    </div>

  </div>
</template>

<script setup lang="ts">
import type { LayoutBlock } from '../services/api';

defineProps<{
  block: LayoutBlock;
  active: boolean;
  index: number;
}>();

defineEmits<{
  (e: 'mouseenter'): void;
  (e: 'mouseleave'): void;
}>();

// Helper functions for border and bg colors based on spelling match accuracy first (else confidence)
function getBoxBorderColor(block: LayoutBlock): string {
  if (block.accuracy !== undefined) {
    const acc = block.accuracy;
    if (acc >= 90) return 'rgba(16, 185, 129, 0.9)'; // emerald green
    if (acc >= 70) return 'rgba(234, 179, 8, 0.9)';  // yellow
    return 'rgba(239, 68, 68, 0.95)';                 // red
  }
  const conf = block.confidence;
  if (conf >= 0.85) return 'rgba(16, 185, 129, 0.9)';
  if (conf >= 0.70) return 'rgba(234, 179, 8, 0.9)';
  return 'rgba(239, 68, 68, 0.95)';
}

function getBoxBgColor(block: LayoutBlock): string {
  if (block.accuracy !== undefined) {
    const acc = block.accuracy;
    if (acc >= 90) return 'rgba(16, 185, 129, 0.08)';
    if (acc >= 70) return 'rgba(234, 179, 8, 0.08)';
    return 'rgba(239, 68, 68, 0.08)';
  }
  const conf = block.confidence;
  if (conf >= 0.85) return 'rgba(16, 185, 129, 0.08)';
  if (conf >= 0.70) return 'rgba(234, 179, 8, 0.08)';
  return 'rgba(239, 68, 68, 0.08)';
}
</script>

<style scoped>
.game-bounding-overlay {
  position: absolute;
  border-radius: 4px;
  border-style: solid;
  border-width: 1.5px;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  cursor: help;
  z-index: 2;
}

.game-bounding-overlay.highlighted {
  border-color: #00f0ff !important;
  border-width: 2.2px !important;
  background: rgba(0, 240, 255, 0.15) !important;
  box-shadow: 0 0 15px rgba(0, 240, 255, 0.7),
              inset 0 0 6px rgba(0, 240, 255, 0.3) !important;
  z-index: 100;
}

/* Healed badge */
.healed-lightning-badge {
  position: absolute;
  top: -8px;
  right: -8px;
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  color: white;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 800;
  border: 1px solid #1e293b;
  box-shadow: 0 0 8px rgba(59, 130, 246, 0.8);
  z-index: 10;
}

/* Video Game style floating HUD status capsule */
.game-hud-capsule {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(2px) scale(0.98);
  display: flex;
  flex-direction: column;
  gap: 5px;
  background: rgba(15, 23, 42, 0.96);
  border: 1.5px solid rgba(94, 163, 250, 0.4);
  border-radius: 6px;
  padding: 8px 12px;
  box-shadow: 0 10px 25px -4px rgba(0, 0, 0, 0.7);
  z-index: 200;
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  min-width: 180px;
}

.game-bounding-overlay:hover .game-hud-capsule,
.game-bounding-overlay.highlighted .game-hud-capsule,
.game-hud-capsule.visible {
  opacity: 1;
  visibility: visible;
  transform: translateX(-50%) translateY(-8px) scale(1.0);
  border-color: #60a5fa;
  box-shadow: 0 16px 32px -4px rgba(0, 0, 0, 0.8),
              0 0 15px rgba(96, 165, 250, 0.4);
}

/* HUD Header styling */
.hud-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  font-family: monospace;
  font-weight: 800;
  letter-spacing: 0.5px;
  border-bottom: 1.5px solid rgba(255, 255, 255, 0.12);
  padding-bottom: 4px;
}

.hud-index {
  color: #94a3b8;
}

.hud-healed-tag {
  color: #60a5fa;
  text-shadow: 0 0 4px rgba(96, 165, 250, 0.6);
}

.hud-scan-tag {
  color: #64748b;
}

/* Bar columns list */
.hud-bars {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-top: 3px;
}

.hud-bar-container {
  display: flex;
  align-items: center;
  gap: 5px;
}

.hud-bar-label {
  font-family: monospace;
  font-size: 9px;
  font-weight: 800;
  width: 32px;
}

.hud-bar-track {
  flex-grow: 1;
  width: 80px;
  height: 9px;
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 3px;
  position: relative;
  overflow: hidden;
  display: flex;
}

.hud-bar-fill {
  height: 100%;
  position: relative;
}

.fill-blue {
  background: linear-gradient(90deg, #2563eb, #3b82f6);
  box-shadow: 0 0 4px rgba(59, 130, 246, 0.5);
  border-radius: 1.5px;
}

.fill-dark-blue {
  background: #1e3a8a;
  border-radius: 1.5px 0 0 1.5px;
}

.fill-gain-blue {
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  box-shadow: 0 0 6px rgba(96, 165, 250, 0.8);
  border-radius: 0 1.5px 1.5px 0;
}

.fill-green {
  background: linear-gradient(90deg, #059669, #10b981);
  box-shadow: 0 0 4px rgba(16, 185, 129, 0.5);
  border-radius: 1.5px;
}

.hud-bar-pulse {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.25),
    transparent
  );
  transform: translateX(-100%);
  animation: bar-pulse 2s infinite linear;
}

@keyframes bar-pulse {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

.hud-bar-val {
  font-family: monospace;
  font-size: 10px;
  font-weight: 700;
  text-align: right;
}

/* Before & After edit styling */
.hud-text-change {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: monospace;
  font-size: 8px;
  border-top: 1px dashed rgba(255, 255, 255, 0.15);
  padding-top: 4px;
  margin-top: 2px;
  white-space: nowrap;
}

.hud-label-text {
  color: #94a3b8;
  font-weight: 800;
  font-size: 7px;
  width: 32px;
}

.hud-text-before {
  color: #f87171;
  text-decoration: line-through;
  max-width: 50px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hud-arrow {
  color: #64748b;
  font-weight: bold;
}

.hud-text-after {
  color: #60a5fa;
  font-weight: 700;
  max-width: 65px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Color text helpers */
.text-blue {
  color: #93c5fd;
}
.text-green {
  color: #a7f3d0;
}

/* standard tooltip fallback styling */
.overlay-tooltip {
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(6px);
  background: #0f172a;
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.65rem;
  white-space: nowrap;
  display: flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
  z-index: 210;
}

.game-bounding-overlay:hover .overlay-tooltip {
  opacity: 1;
}

.tooltip-text {
  font-weight: 600;
}

.tooltip-conf {
  color: #64748b;
  font-size: 0.6rem;
}
</style>
