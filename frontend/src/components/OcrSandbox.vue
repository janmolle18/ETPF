<template>
  <div class="sandbox-container animate-fade">
    <!-- Header -->
    <header class="sandbox-title-section">
      <h2>OCR Developer Sandbox</h2>
      <p class="subtitle">Execute extraction pipelines on synthetic documents to inspect logs, coordinate mappings, and extraction rules.</p>
    </header>

    <!-- Top Sandbox Mode Switcher -->
    <div class="mode-switcher glass-panel animate-fade">
      <button 
        class="mode-btn" 
        :class="{ 'active': activeMode === 'workspace' }" 
        @click="activeMode = 'workspace'"
      >
        <component :is="layersIcon" class="mode-icon" />
        <span>Layout Inspector Workspace</span>
      </button>
      <button 
        class="mode-btn" 
        :class="{ 'active': activeMode === 'stress' }" 
        @click="activeMode = 'stress'"
      >
        <component :is="cpuIcon" class="mode-icon" />
        <span>Image Degradation Stress Test Suite</span>
      </button>
    </div>

    <!-- Mode A: Layout Workspace -->
    <div v-if="activeMode === 'workspace'" class="sandbox-grid animate-fade">
      <!-- Left Column: Controls & Console Logs -->
      <div class="sandbox-left">
        <!-- Document Selection Card -->
        <div class="sandbox-card glass-panel">
          <h3>1. Select Synthetic Test Case</h3>
          <div class="cards-grid">
            <div 
              v-for="testCase in testCases" 
              :key="testCase.id"
              class="selection-card"
              :class="{ 'active': selectedType === testCase.id }"
              @click="selectedType = testCase.id"
            >
              <component :is="testCase.icon" class="case-icon" />
              <div class="case-info">
                <span class="case-title">{{ testCase.name }}</span>
                <span class="case-desc">{{ testCase.desc }}</span>
              </div>
            </div>
          </div>

          <button 
            class="run-btn" 
            :disabled="isRunning" 
            @click="executeSandbox"
          >
            <div v-if="isRunning" class="btn-loader"></div>
            <component v-else :is="playIcon" class="btn-icon" />
            <span>{{ isRunning ? 'Processing Sandbox Run...' : 'Execute Pipeline' }}</span>
          </button>
        </div>

        <!-- Terminal Console -->
        <div class="sandbox-card glass-panel terminal-card">
          <div class="terminal-header">
            <div class="header-dots">
              <span class="dot red"></span>
              <span class="dot yellow"></span>
              <span class="dot green"></span>
            </div>
            <span class="terminal-title">pipeline_console.log</span>
          </div>
          <div class="terminal-body" ref="terminalBody">
            <div v-for="(log, idx) in consoleLogs" :key="idx" class="log-line">
              <span class="log-timestamp">[{{ new Date().toLocaleTimeString() }}]</span>
              <span class="log-text" :class="{ 'highlight-log': log.startsWith('Extracted') || log.includes('COMPLETED') }">
                {{ log }}
              </span>
            </div>
            <div v-if="consoleLogs.length === 0" class="log-placeholder">
              Select a test case and click "Execute Pipeline" to view stage-by-stage execution logs...
            </div>
            <div v-if="isRunning" class="log-line blinking-cursor">
              <span class="log-text">> Running analysis...</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Visual Debugger & Output JSON -->
      <div class="sandbox-right">
        <!-- Visual Canvas Panel -->
        <div class="sandbox-card glass-panel canvas-panel" v-if="document">
          <div class="panel-header">
            <h3>Visual Layout Inspector</h3>
            <button class="expand-btn" @click="toggleFullscreen">
              <component :is="maximizeIcon" class="action-icon" />
              <span>Fullscreen</span>
            </button>
          </div>

          <div class="layout-viewer-grid">
            <div class="document-canvas-container">
              <div 
                class="document-canvas" 
                :style="{ 
                  aspectRatio: document.layout_data?.width && document.layout_data?.height 
                    ? `${document.layout_data.width}/${document.layout_data.height}` 
                    : '8.5/11' 
                }"
              >
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

            <!-- Sidebar container column -->
            <div class="sandbox-sidebar animate-fade" style="display: flex; flex-direction: column; gap: 1rem; max-height: 700px; width: 320px; overflow-y: auto;">
              <!-- De-Skewing Preprocessor Stats Card -->
              <div 
                v-if="document?.layout_data?.deskew_stats" 
                class="deskew-stats-card glass-panel animate-fade"
                style="padding: 1rem 1.25rem; border-radius: 12px; background: rgba(30, 41, 59, 0.45); border: 1px solid rgba(168, 85, 247, 0.3); display: flex; flex-direction: column; gap: 0.5rem; width: 100%; box-sizing: border-box;"
              >
                <div style="display: flex; align-items: center; justify-content: space-between;">
                  <span style="font-weight: 700; color: #c084fc; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 0.4rem;">
                    De-Skew Preprocessor
                  </span>
                  <span 
                    :style="{ 
                      background: document.layout_data.deskew_stats.deskew_applied ? 'rgba(168, 85, 247, 0.2)' : 'rgba(148, 163, 184, 0.15)',
                      color: document.layout_data.deskew_stats.deskew_applied ? '#c084fc' : '#94a3b8'
                    }"
                    style="font-size: 0.72rem; font-weight: 700; padding: 2px 6px; border-radius: 4px;"
                  >
                    {{ document.layout_data.deskew_stats.deskew_applied ? 'Rotated' : 'Aligned 0°' }}
                  </span>
                </div>

                <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.78rem; color: #cbd5e1;">
                  <span>Detected: <strong style="color: #f472b6;">{{ document.layout_data.deskew_stats.detected_angle_deg > 0 ? '+' : '' }}{{ document.layout_data.deskew_stats.detected_angle_deg }}°</strong></span>
                  <span>Correction: <strong style="color: #38bdf8;">{{ document.layout_data.deskew_stats.deskew_applied ? (document.layout_data.deskew_stats.correction_applied_deg > 0 ? '+' : '') + document.layout_data.deskew_stats.correction_applied_deg + '°' : 'None' }}</strong></span>
                </div>
              </div>

              <!-- Text Postprocessor Rules Stats Card -->
              <div 
                v-if="document?.layout_data?.postprocessing_stats" 
                class="postprocessing-stats-card glass-panel animate-fade"
                style="padding: 1rem 1.25rem; border-radius: 12px; background: rgba(30, 41, 59, 0.45); border: 1px solid rgba(16, 185, 129, 0.3); display: flex; flex-direction: column; gap: 0.5rem; width: 100%; box-sizing: border-box;"
              >
                <div style="display: flex; align-items: center; justify-content: space-between;">
                  <span style="font-weight: 700; color: #34d399; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em;">
                    Text Postprocessor Rules
                  </span>
                  <span style="font-size: 0.72rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; background: rgba(16, 185, 129, 0.2); color: #34d399;">
                    {{ document.layout_data.postprocessing_stats.modified_blocks_count }} Fixed
                  </span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.78rem; color: #cbd5e1;">
                  <span>Active Rules: <strong style="color: #60a5fa;">{{ document.layout_data.postprocessing_stats.rules_active }}</strong></span>
                  <span>Blocks Processed: <strong style="color: #94a3b8;">{{ document.layout_data.postprocessing_stats.total_blocks }}</strong></span>
                </div>
              </div>

              <!-- Bounding Blocks Coordinates List -->
              <div class="coordinates-list" style="margin-top: 0; width: 100%;">
                <div 
                  v-for="(block, index) in document.layout_data?.blocks" 
                  :key="index"
                  class="coordinate-row"
                  :class="{ 'active': activeBlockIndex === index }"
                  @mouseenter="activeBlockIndex = index"
                  @mouseleave="activeBlockIndex = null"
                  style="display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 10px; width: 100%; box-sizing: border-box;"
                >
                  <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                    <div class="coord-label" style="width: 100%; display: flex; align-items: center; gap: 6px;">
                      <span class="coord-index">#{{ index + 1 }}</span>
                      <span class="coord-text" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 210px;">{{ block.text }}</span>
                    </div>
                  </div>
                  <div class="coord-metrics" style="width: 100%; display: flex; align-items: center; justify-content: space-between; margin-top: 2px;">
                    <span style="font-size: 0.75rem; color: #64748b;">x:{{ block.x.toFixed(0) }} y:{{ block.y.toFixed(0) }}</span>
                    <div style="display: flex; gap: 6px; align-items: center;">
                      <span class="coord-conf" :style="{ color: getConfColor(block.confidence) }">
                        C: {{ (block.confidence * 100).toFixed(0) }}%
                      </span>
                      <span class="coord-acc" v-if="block.accuracy !== undefined" style="color: #60a5fa; font-weight: 700;">
                        M: {{ block.accuracy }}%
                      </span>
                    </div>
                  </div>
                  <!-- Visual Confidence & Accuracy indicator progress bars -->
                  <div class="coord-bars-wrapper" style="display: flex; flex-direction: column; gap: 4px; margin-top: 6px; width: 100%;">
                    <!-- Confidence Bar (Blue) -->
                    <div class="coord-bar-track" style="height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; width: 100%; overflow: hidden; position: relative;">
                      <div 
                        class="coord-bar-fill" 
                        :style="{ 
                          width: (block.confidence * 100) + '%',
                          background: '#3b82f6'
                        }" 
                        style="height: 100%; transition: width 0.3s ease;"
                      ></div>
                    </div>
                    <!-- Match Accuracy Bar (Green) -->
                    <div 
                      v-if="block.accuracy !== undefined" 
                      class="coord-bar-track" 
                      style="height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; width: 100%; overflow: hidden; position: relative;"
                    >
                      <div 
                        class="coord-bar-fill" 
                        :style="{ 
                          width: block.accuracy + '%',
                          background: '#10b981'
                        }" 
                        style="height: 100%; transition: width 0.3s ease;"
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Bottom Tabs -->
          <div class="sandbox-tabs">
            <button 
              class="tab-btn" 
              :class="{ 'active': activeTab === 'json' }" 
              @click="activeTab = 'json'"
            >
              Extracted JSON
            </button>
            <button 
              class="tab-btn" 
              :class="{ 'active': activeTab === 'text' }" 
              @click="activeTab = 'text'"
            >
              Plain Text
            </button>
          </div>

          <div class="tab-content">
            <pre v-if="activeTab === 'json'" class="json-code"><code>{{ JSON.stringify(document.extracted_data, null, 2) }}</code></pre>
            <pre v-else class="text-raw"><code>{{ document.raw_text }}</code></pre>
          </div>
        </div>

        <div v-else class="sandbox-card glass-panel placeholder-panel">
          <component :is="layersIcon" class="placeholder-icon" />
          <h3>No Active Workspace Output</h3>
          <p>Select a test case type on the left and run the pipeline. The visual coordinates viewer and OCR result JSON payload will render here.</p>
        </div>
      </div>
    </div>

    <!-- Mode B: Image Degradation Stress Test Suite -->
    <div v-else-if="activeMode === 'stress'" class="sandbox-grid animate-fade">
      <!-- Left Column: Controls & Scorecard List -->
      <div class="sandbox-left">
        <!-- Control Card -->
        <div class="sandbox-card glass-panel">
          <h3>OCR Degradation Loop Controller</h3>
          <p class="card-p">Runs a programmatic matrix of advanced image transformations (motion blur, shear skewing, crumpled creases, uneven lighting) and calculates character accuracy against the expected ground truth.</p>
          <p class="card-p font-bold text-primary" style="margin-top: -0.5rem;">💡 Click on any scorecard row to inspect the degraded receipt canvas directly!</p>
          
          <div style="display: flex; gap: 0.75rem; flex-wrap: wrap;">
            <button 
              class="run-btn stress-run-btn" 
              :disabled="isStressRunning" 
              @click="executeStressTest"
              style="flex: 1; min-width: 200px;"
            >
              <div v-if="isStressRunning" class="btn-loader"></div>
              <component v-else :is="playIcon" class="btn-icon" />
              <span>{{ isStressRunning ? 'Executing Stress Matrix...' : 'Start Stress Test Loop' }}</span>
            </button>
            
            <button 
              v-if="stressResults.length > 0"
              class="run-btn" 
              @click="downloadStressReportJson"
              title="Download JSON Report File"
              style="background: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.4); color: #34d399; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 0.75rem 1.25rem; border-radius: 8px; cursor: pointer;"
            >
              <component :is="downloadIcon" class="btn-icon" />
              <span>Export Report (JSON)</span>
            </button>
          </div>
        </div>

        <!-- Scorecard Table -->
        <div class="sandbox-card glass-panel stress-results-card" v-if="stressResults.length > 0">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.75rem;">
            <h3 style="margin: 0;">OCR Degradation Scorecard</h3>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <button 
                class="export-btn" 
                @click="copyStressReportJson"
                title="Copy JSON Report to Clipboard"
                style="display: flex; align-items: center; gap: 0.4rem; padding: 0.45rem 0.85rem; background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 6px; color: #60a5fa; font-size: 0.82rem; font-weight: 600; cursor: pointer; transition: all 0.2s ease;"
              >
                <component :is="copiedReport ? checkIcon : copyIcon" style="width: 15px; height: 15px;" />
                <span>{{ copiedReport ? 'Copied!' : 'Copy JSON' }}</span>
              </button>
              <button 
                class="export-btn" 
                @click="downloadStressReportJson"
                title="Download JSON Report File"
                style="display: flex; align-items: center; gap: 0.4rem; padding: 0.45rem 0.85rem; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; color: #34d399; font-size: 0.82rem; font-weight: 600; cursor: pointer; transition: all 0.2s ease;"
              >
                <component :is="downloadIcon" style="width: 15px; height: 15px;" />
                <span>Export Detailed Report (JSON)</span>
              </button>
            </div>
          </div>

          <div class="stress-table-wrapper">
            <table class="stress-table">
              <thead>
                <tr>
                  <th>Transformation</th>
                  <th>Intensity</th>
                  <th>Confidence</th>
                  <th>Accuracy (Match)</th>
                  <th>Optimizer Gain</th>
                  <th>Blocks</th>
                  <th>Latency</th>
                </tr>
              </thead>
              <tbody>
                <tr 
                  v-for="run in stressResults" 
                  :key="run.degradation + run.level"
                  class="stress-row-interactive"
                  :class="{ 'active-row': selectedStressRun?.document_id === run.document_id }"
                  @click="selectStressRun(run)"
                >
                  <td class="td-capitalize font-bold">{{ run.degradation.replace('_', ' ') }}</td>
                  <td>{{ run.label }}</td>
                  <td>
                    <span style="color: #3b82f6; background: rgba(59, 130, 246, 0.12); padding: 2px 6px; border-radius: 4px; font-weight: 700; font-family: monospace; font-size: 0.8rem;">
                      {{ run.confidence }}%
                    </span>
                  </td>
                  <td>
                    <span class="accuracy-badge" :style="{ 
                      backgroundColor: getAccuracyBg(run.accuracy), 
                      color: getAccuracyColor(run.accuracy) 
                    }">
                      {{ run.accuracy }}%
                    </span>
                  </td>
                  <td>
                    <span 
                      v-if="run.optimization_stats && run.optimization_stats.avg_confidence_gain > 0" 
                      style="color: #60a5fa; background: rgba(96, 165, 250, 0.12); padding: 2px 6px; border-radius: 4px; font-weight: 700; font-family: monospace; font-size: 0.8rem;"
                    >
                      +{{ run.optimization_stats.avg_confidence_gain }}%
                    </span>
                    <span v-else style="color: #64748b; font-family: monospace;">-</span>
                  </td>
                  <td>{{ run.blocks_found }}</td>
                  <td class="font-mono text-muted">{{ run.time_ms }}ms</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Raw Stress Test Report JSON Data Drawer -->
          <div class="stress-json-drawer" style="margin-top: 1.25rem; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 1rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; cursor: pointer; user-select: none;" @click="showReportJsonDrawer = !showReportJsonDrawer">
              <span style="font-size: 0.85rem; font-weight: 700; color: #94a3b8; display: flex; align-items: center; gap: 0.5rem;">
                <component :is="fileCodeIcon" style="width: 16px; height: 16px; color: #60a5fa;" />
                Raw Stress Test Report JSON Data
              </span>
              <span style="font-size: 0.8rem; color: #3b82f6; font-weight: 600; display: flex; align-items: center; gap: 0.25rem;">
                {{ showReportJsonDrawer ? '▲ Hide JSON' : '▼ View Full JSON' }}
              </span>
            </div>
            
            <div v-if="showReportJsonDrawer" style="margin-top: 0.75rem;" class="animate-fade">
              <pre class="json-code" style="max-height: 320px; overflow-y: auto; background: rgba(15, 23, 42, 0.85); border-radius: 8px; padding: 1rem; border: 1px solid rgba(255, 255, 255, 0.08); font-family: monospace; font-size: 0.8rem; color: #38bdf8; white-space: pre-wrap; word-break: break-word;"><code>{{ formattedStressReportJson }}</code></pre>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Canvas inspector OR decay curves -->
      <div class="sandbox-right">
        <!-- Canvas view of selected degradation run -->
        <div class="sandbox-card glass-panel canvas-panel" v-if="selectedStressRun && stressDocument">
          <div class="panel-header">
            <div class="header-titles">
              <h3 class="td-capitalize font-bold text-primary">{{ selectedStressRun.degradation.replace('_', ' ') }} ({{ selectedStressRun.label }})</h3>
              <small class="text-muted">Hover boxes to check text matches. Click 'Back to Chart' to view full scorecard scores.</small>
            </div>
            <div class="layout-actions">
              <button class="expand-btn" @click="toggleFullscreen">
                <component :is="maximizeIcon" class="action-icon" />
                <span>Fullscreen</span>
              </button>
              <button class="close-btn" @click="selectedStressRun = null; stressDocument = null">
                <span>Back to Chart</span>
              </button>
            </div>
          </div>

          <div class="layout-viewer-grid">
            <div class="document-canvas-container">
              <div 
                class="document-canvas" 
                :style="{ 
                  aspectRatio: stressDocument.layout_data?.width && stressDocument.layout_data?.height 
                    ? `${stressDocument.layout_data.width}/${stressDocument.layout_data.height}` 
                    : '8.5/11' 
                }"
              >
                <img 
                  v-if="stressDocument"
                  :src="imageUrl" 
                  @error="handleImageError"
                  class="document-image-underlay" 
                  alt="Receipt Document"
                />
                <div class="canvas-grid-bg"></div>
                
                <!-- Bounding Box Overlays -->
                <OcrBlockIndicator 
                  v-for="(block, index) in stressDocument.layout_data?.blocks" 
                  :key="index"
                  :block="block"
                  :index="index"
                  :active="activeBlockIndex === index"
                  @mouseenter="activeBlockIndex = index"
                  @mouseleave="activeBlockIndex = null"
                />
              </div>
            </div>

            <!-- Sidebar container column -->
            <div class="sandbox-sidebar animate-fade" style="display: flex; flex-direction: column; gap: 1rem; max-height: 700px; width: 320px; overflow-y: auto;">
              
              <!-- De-Skewing Preprocessor Stats Card -->
              <div 
                v-if="stressDocument?.layout_data?.deskew_stats" 
                class="deskew-stats-card glass-panel animate-fade"
                style="padding: 1rem 1.25rem; border-radius: 12px; background: rgba(30, 41, 59, 0.45); border: 1px solid rgba(168, 85, 247, 0.3); display: flex; flex-direction: column; gap: 0.5rem; width: 100%; box-sizing: border-box;"
              >
                <div style="display: flex; align-items: center; justify-content: space-between;">
                  <span style="font-weight: 700; color: #c084fc; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em;">
                    De-Skew Preprocessor
                  </span>
                  <span 
                    :style="{ 
                      background: stressDocument.layout_data.deskew_stats.deskew_applied ? 'rgba(168, 85, 247, 0.2)' : 'rgba(148, 163, 184, 0.15)',
                      color: stressDocument.layout_data.deskew_stats.deskew_applied ? '#c084fc' : '#94a3b8'
                    }"
                    style="font-size: 0.72rem; font-weight: 700; padding: 2px 6px; border-radius: 4px;"
                  >
                    {{ stressDocument.layout_data.deskew_stats.deskew_applied ? 'Rotated' : 'Aligned 0°' }}
                  </span>
                </div>

                <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.78rem; color: #cbd5e1;">
                  <span>Detected: <strong style="color: #f472b6;">{{ stressDocument.layout_data.deskew_stats.detected_angle_deg > 0 ? '+' : '' }}{{ stressDocument.layout_data.deskew_stats.detected_angle_deg }}°</strong></span>
                  <span>Correction: <strong style="color: #38bdf8;">{{ stressDocument.layout_data.deskew_stats.deskew_applied ? (stressDocument.layout_data.deskew_stats.correction_applied_deg > 0 ? '+' : '') + stressDocument.layout_data.deskew_stats.correction_applied_deg + '°' : 'None' }}</strong></span>
                </div>
              </div>

              <!-- Text Postprocessor Rules Stats Card -->
              <div 
                v-if="stressDocument?.layout_data?.postprocessing_stats" 
                class="postprocessing-stats-card glass-panel animate-fade"
                style="padding: 1rem 1.25rem; border-radius: 12px; background: rgba(30, 41, 59, 0.45); border: 1px solid rgba(16, 185, 129, 0.3); display: flex; flex-direction: column; gap: 0.5rem; width: 100%; box-sizing: border-box;"
              >
                <div style="display: flex; align-items: center; justify-content: space-between;">
                  <span style="font-weight: 700; color: #34d399; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em;">
                    Text Postprocessor Rules
                  </span>
                  <span style="font-size: 0.72rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; background: rgba(16, 185, 129, 0.2); color: #34d399;">
                    {{ stressDocument.layout_data.postprocessing_stats.modified_blocks_count }} Fixed
                  </span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.78rem; color: #cbd5e1;">
                  <span>Active Rules: <strong style="color: #60a5fa;">{{ stressDocument.layout_data.postprocessing_stats.rules_active }}</strong></span>
                  <span>Blocks Processed: <strong style="color: #94a3b8;">{{ stressDocument.layout_data.postprocessing_stats.total_blocks }}</strong></span>
                </div>
              </div>

              <!-- Self-Healing OCR Stats -->
              <div 
                v-if="stressDocument?.layout_data?.optimization_stats" 
                class="self-healing-stats-card glass-panel animate-fade"
                style="padding: 1.25rem; border-radius: 12px; background: rgba(30, 41, 59, 0.45); border: 1px solid rgba(96, 165, 250, 0.25); display: flex; flex-direction: column; gap: 0.75rem; width: 100%; box-sizing: border-box;"
              >
                <div class="sh-card-header" style="display: flex; align-items: center; justify-content: space-between;">
                  <span class="sh-title" style="font-weight: 700; color: #60a5fa; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.05em;">
                    Self-Healing Stats
                  </span>
                  <span class="sh-latency font-mono" style="font-size: 0.75rem; color: #94a3b8; background: rgba(148, 163, 184, 0.15); padding: 2px 6px; border-radius: 4px;">
                    +{{ stressDocument.layout_data.optimization_stats.healing_time_ms.toFixed(1) }}ms
                  </span>
                </div>
                
                <div class="sh-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
                  <div class="sh-stat-box" style="background: rgba(15, 23, 42, 0.55); padding: 0.75rem; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05); text-align: center; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                    <div style="font-size: 0.75rem; color: #94a3b8; margin-bottom: 0.25rem;">Recovery Rate</div>
                    <div style="font-size: 1.25rem; font-weight: 800; color: #10b981; line-height: 1;">
                      {{ stressDocument.layout_data.optimization_stats.low_conf_original > 0 
                        ? Math.round((stressDocument.layout_data.optimization_stats.healed_count / stressDocument.layout_data.optimization_stats.low_conf_original) * 100) 
                        : 100 }}%
                    </div>
                    <div style="font-size: 0.7rem; color: #64748b; margin-top: 0.35rem;">
                      {{ stressDocument.layout_data.optimization_stats.healed_count }}/{{ stressDocument.layout_data.optimization_stats.low_conf_original }} recovered
                    </div>
                  </div>
                  
                  <div class="sh-stat-box" style="background: rgba(15, 23, 42, 0.55); padding: 0.75rem; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05); text-align: center; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                    <div style="font-size: 0.75rem; color: #94a3b8; margin-bottom: 0.25rem;">Avg Conf Gain</div>
                    <div style="font-size: 1.25rem; font-weight: 800; color: #3b82f6; line-height: 1;">
                      +{{ stressDocument.layout_data.optimization_stats.avg_confidence_gain.toFixed(1) }}%
                    </div>
                    <div style="font-size: 0.7rem; color: #64748b; margin-top: 0.35rem;">
                      on low-conf cells
                    </div>
                  </div>
                </div>
              </div>

              <!-- Bounding Blocks Coordinates List -->
              <div class="coordinates-list" style="margin-top: 0; width: 100%;">
                <div 
                  v-for="(block, index) in stressDocument.layout_data?.blocks" 
                  :key="index"
                  class="coordinate-row"
                  :class="{ 'active': activeBlockIndex === index }"
                  @mouseenter="activeBlockIndex = index"
                  @mouseleave="activeBlockIndex = null"
                  style="display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 10px; width: 100%; box-sizing: border-box;"
                >
                  <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                    <div class="coord-label" style="width: 100%; display: flex; flex-direction: column; gap: 2px;">
                      <div style="display: flex; align-items: center; gap: 6px;">
                        <span class="coord-index">#{{ index + 1 }}</span>
                        <span class="coord-text" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 210px;" :title="'Predicted: ' + block.text">P: {{ block.text }}</span>
                      </div>
                      <div v-if="block.ground_truth" style="font-size: 0.72rem; color: #38bdf8; font-weight: 500; padding-left: 22px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 210px;" :title="'Actual Ground Truth: ' + block.ground_truth">
                        A: {{ block.ground_truth }}
                      </div>
                    </div>
                  </div>
                  <div class="coord-metrics" style="width: 100%; display: flex; align-items: center; justify-content: space-between; margin-top: 2px;">
                    <span style="font-size: 0.75rem; color: #64748b;">x:{{ block.x.toFixed(0) }} y:{{ block.y.toFixed(0) }}</span>
                    <div style="display: flex; gap: 6px; align-items: center;">
                      <span class="coord-conf" :style="{ color: getConfColor(block.confidence) }">
                        C: {{ (block.confidence * 100).toFixed(0) }}%
                      </span>
                      <span class="coord-acc" v-if="block.accuracy !== undefined" style="color: #60a5fa; font-weight: 700;">
                        M: {{ block.accuracy }}%
                      </span>
                    </div>
                  </div>
                  <!-- Visual Confidence & Accuracy indicator progress bars -->
                  <div class="coord-bars-wrapper" style="display: flex; flex-direction: column; gap: 4px; margin-top: 6px; width: 100%;">
                    <!-- Confidence Bar (Blue) -->
                    <div class="coord-bar-track" style="height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; width: 100%; overflow: hidden; position: relative;">
                      <div 
                        class="coord-bar-fill" 
                        :style="{ 
                          width: (block.confidence * 100) + '%',
                          background: '#3b82f6'
                        }" 
                        style="height: 100%; transition: width 0.3s ease;"
                      ></div>
                    </div>
                    <!-- Match Accuracy Bar (Green) -->
                    <div 
                      v-if="block.accuracy !== undefined" 
                      class="coord-bar-track" 
                      style="height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; width: 100%; overflow: hidden; position: relative;"
                    >
                      <div 
                        class="coord-bar-fill" 
                        :style="{ 
                          width: block.accuracy + '%',
                          background: '#10b981'
                        }" 
                        style="height: 100%; transition: width 0.3s ease;"
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Default: Decay Curve Chart -->
        <div v-else-if="stressResults.length > 0" class="sandbox-card glass-panel chart-panel animate-fade">
          <h3>OCR Accuracy Decay Curve</h3>
          <p class="subtitle">Evaluates character recognition thresholds against increasing degradation intensities.</p>
          
          <div class="bar-chart-container">
            <div 
              v-for="run in stressResults" 
              :key="run.degradation + run.level"
              class="chart-row"
            >
              <div class="chart-label">
                <span class="degr-name">{{ run.degradation.replace('_', ' ') }}</span>
                <span class="degr-val text-muted">{{ run.label }}</span>
              </div>
              <div class="chart-bar-wrapper" style="display: flex; flex-direction: column; gap: 6px; align-items: stretch; width: 100%;">
                <!-- Match Accuracy (Green) -->
                <div style="display: flex; align-items: center; gap: 8px; width: 100%;">
                  <div class="chart-bar-track" style="flex: 1; height: 10px; background: rgba(255,255,255,0.06); border-radius: 5px; overflow: hidden; position: relative;">
                    <div 
                      class="chart-bar-fill" 
                      :style="{ 
                        width: run.accuracy + '%',
                        background: getAccuracyColor(run.accuracy)
                      }" 
                      style="height: 100%; transition: width 0.3s ease;"
                    ></div>
                  </div>
                  <span class="chart-percentage font-mono" style="min-width: 50px; text-align: right; font-weight: 700; color: #10b981; font-size: 0.85rem;">
                    M: {{ run.accuracy }}%
                  </span>
                </div>

                <!-- Self-Healing Boost (Blue) -->
                <div 
                  v-if="run.optimization_stats && run.optimization_stats.avg_confidence_gain > 0" 
                  style="display: flex; align-items: center; gap: 8px; width: 100%;"
                >
                  <div class="chart-bar-track" style="flex: 1; height: 6px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden; position: relative;">
                    <div 
                      class="chart-bar-fill" 
                      :style="{ 
                        width: Math.min(100, run.optimization_stats.avg_confidence_gain * 2.5) + '%', 
                        background: '#3b82f6'
                      }" 
                      style="height: 100%; transition: width 0.3s ease;"
                    ></div>
                  </div>
                  <span class="chart-percentage font-mono" style="min-width: 50px; text-align: right; font-size: 0.75rem; color: #3b82f6; font-weight: 700;">
                    +{{ run.optimization_stats.avg_confidence_gain }}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Placeholder -->
        <div v-else class="sandbox-card glass-panel placeholder-panel">
          <component :is="cpuIcon" class="placeholder-icon" />
          <h3>No Stress Run Scorecard Available</h3>
          <p>Start the stress test loop on the left to evaluate ink blur, shear skewing, paper folds, and shadow recognition limits.</p>
        </div>
      </div>
    </div>

    <!-- Fullscreen Teleport Modal -->
    <Teleport to="body">
      <div v-if="isFullscreen" class="fullscreen-overlay animate-fade" @click.self="toggleFullscreen">
        <div class="fullscreen-container glass-panel">
          <div class="fullscreen-header">
            <h3>Fullscreen Layout Inspector — {{ activeMode === 'stress' && selectedStressRun ? selectedStressRun.degradation.replace('_', ' ') : selectedTestCaseName }}</h3>
            <button class="close-fullscreen-btn" @click="toggleFullscreen">
              <component :is="minimizeIcon" class="action-icon" />
              <span>Close</span>
            </button>
          </div>
          <div class="fullscreen-body" v-if="activeDocument">
            <div 
              class="document-canvas fullscreen-canvas" 
              :style="{ 
                aspectRatio: activeDocument.layout_data?.width && activeDocument.layout_data?.height 
                  ? `${activeDocument.layout_data.width}/${activeDocument.layout_data.height}` 
                  : '8.5/11' 
              }"
            >
              <img 
                :src="imageUrl" 
                @error="handleImageError"
                class="document-image-underlay" 
                alt="Receipt Document"
              />
              <div class="canvas-grid-bg"></div>
              
              <!-- Bounding Box Overlays -->
              <OcrBlockIndicator 
                v-for="(block, index) in activeDocument.layout_data?.blocks" 
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
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue';
import OcrBlockIndicator from './OcrBlockIndicator.vue';
import { 
  Play, 
  FileImage, 
  FileText, 
  Layers, 
  Cpu, 
  Maximize2, 
  Minimize2,
  Download,
  Copy,
  Check,
  FileCode
} from '@lucide/vue';
import { 
  triggerSandbox, 
  getDocument, 
  getDocumentFileUrl,
  triggerStressStep
} from '../services/api';
import type { DocumentResponse, StressTestRun } from '../services/api';
import { getConfColor } from '../lib/color';

const playIcon = Play;
const maximizeIcon = Maximize2;
const minimizeIcon = Minimize2;
const layersIcon = Layers;
const cpuIcon = Cpu;
const downloadIcon = Download;
const copyIcon = Copy;
const checkIcon = Check;
const fileCodeIcon = FileCode;

const activeMode = ref<'workspace' | 'stress'>('workspace');
const selectedType = ref<'png' | 'pdf_digital' | 'pdf_scanned' | 'jpg'>('png');
const isRunning = ref(false);
const consoleLogs = ref<string[]>([]);
const document = ref<DocumentResponse | null>(null);
const activeBlockIndex = ref<number | null>(null);
const activeTab = ref<'json' | 'text'>('json');
const isFullscreen = ref(false);
const terminalBody = ref<HTMLElement | null>(null);

const isStressRunning = ref(false);
const stressResults = ref<StressTestRun[]>([]);
const selectedStressRun = ref<StressTestRun | null>(null);
const stressDocument = ref<DocumentResponse | null>(null);

const showReportJsonDrawer = ref(false);
const copiedReport = ref(false);

const formattedStressReportJson = computed(() => {
  if (stressResults.value.length === 0) return '{}';

  const totalRuns = stressResults.value.length;
  const avgConf = Number((stressResults.value.reduce((acc, r) => acc + r.confidence, 0) / totalRuns).toFixed(1));
  const avgAcc = Number((stressResults.value.reduce((acc, r) => acc + r.accuracy, 0) / totalRuns).toFixed(1));
  const avgTime = Math.round(stressResults.value.reduce((acc, r) => acc + r.time_ms, 0) / totalRuns);
  const totalHealed = stressResults.value.reduce((acc, r) => acc + (r.optimization_stats?.healed_count || 0), 0);

  const reportPayload = {
    exported_at: new Date().toISOString(),
    environment: "ETPF OCR Stress Test Suite",
    summary: {
      total_runs: totalRuns,
      average_confidence_pct: avgConf,
      average_accuracy_pct: avgAcc,
      average_latency_ms: avgTime,
      total_self_healed_blocks: totalHealed
    },
    results: stressResults.value.map(run => ({
      degradation_type: run.degradation,
      intensity_level: run.level,
      label: run.label,
      confidence_score: run.confidence,
      match_accuracy_pct: run.accuracy,
      blocks_detected: run.blocks_found,
      execution_time_ms: run.time_ms,
      document_id: run.document_id,
      deskew_stats: run.deskew_stats || null,
      self_healing_stats: run.optimization_stats || null,
      postprocessing_stats: run.postprocessing_stats || null,
      blocks: (run.blocks || []).map(b => ({
        predicted_value: b.predicted_value,
        actual_value: b.actual_value,
        match_accuracy_pct: b.match_accuracy_pct,
        confidence_pct: b.confidence_pct,
        healed: b.healed || false,
        original_text: b.original_text || null,
        bounding_box: b.bounding_box || null
      }))
    }))
  };

  return JSON.stringify(reportPayload, null, 2);
});

const downloadStressReportJson = () => {
  const jsonStr = formattedStressReportJson.value;
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement('a');
  link.href = url;
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  link.download = `ocr_stress_test_report_${timestamp}.json`;
  window.document.body.appendChild(link);
  link.click();
  window.document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const copyStressReportJson = async () => {
  try {
    await navigator.clipboard.writeText(formattedStressReportJson.value);
    copiedReport.value = true;
    setTimeout(() => {
      copiedReport.value = false;
    }, 2000);
  } catch (err) {
    console.error('Failed to copy JSON to clipboard:', err);
  }
};

const imageErrorCount = ref(0);

const activeDocument = computed(() => {
  return activeMode.value === 'stress' ? stressDocument.value : document.value;
});

const imageUrl = computed(() => {
  if (!activeDocument.value) return '';
  const baseUrl = getDocumentFileUrl(activeDocument.value.id, true);
  const cacheBuster = `t=${Date.now()}`;
  return `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}${cacheBuster}`;
});

const handleImageError = () => {
  if (imageErrorCount.value < 5) {
    setTimeout(() => {
      imageErrorCount.value++;
    }, 2000);
  }
};

watch(() => document.value?.id, () => {
  imageErrorCount.value = 0;
});

watch(() => stressDocument.value?.id, () => {
  imageErrorCount.value = 0;
});

const testCases = [
  { 
    id: 'png', 
    name: 'PNG Receipt Image', 
    desc: 'Uses EasyOCR (PyTorch) to scan pixels and extract bounding boxes.',
    icon: FileImage 
  },
  { 
    id: 'pdf_digital', 
    name: 'Searchable PDF', 
    desc: 'Uses PyMuPDF to extract text digitally in milliseconds (low CPU).',
    icon: FileText 
  },
  { 
    id: 'pdf_scanned', 
    name: 'Scanned PDF Image', 
    desc: 'Renders PDF pages to high-res PNGs and falls back to EasyOCR.',
    icon: Cpu 
  },
  { 
    id: 'jpg', 
    name: 'Real JPG Invoice', 
    desc: 'Processes musterrechnung-6p.jpg through grayscale, contrast enhancement, and EasyOCR.',
    icon: FileImage 
  }
] as const;

const selectedTestCaseName = computed(() => {
  return testCases.find(tc => tc.id === selectedType.value)?.name || '';
});

const executeSandbox = async () => {
  isRunning.value = true;
  consoleLogs.value = [];
  document.value = null;
  
  try {
    consoleLogs.value.push("Contacting developer sandbox endpoint...");
    const res = await triggerSandbox(selectedType.value);
    
    // Simulate real-time printing of logs (50ms offset)
    for (const log of res.logs) {
      consoleLogs.value.push(log);
      await nextTick();
      scrollToBottom();
      await new Promise(resolve => setTimeout(resolve, 80));
    }
    
    consoleLogs.value.push("Fetching completed layout mapping details...");
    const docData = await getDocument(res.document_id);
    document.value = docData;
    consoleLogs.value.push("Layout Visualizer mounted successfully.");
    scrollToBottom();
  } catch (error: any) {
    consoleLogs.value.push(`Pipeline CRASHED: ${error.message}`);
  } finally {
    isRunning.value = false;
  }
};

const executeStressTest = async () => {
  isStressRunning.value = true;
  stressResults.value = [];
  selectedStressRun.value = null;
  stressDocument.value = null;
  
  const steps = [
    { degradation: 'rotation', level: 5.0 },
    { degradation: 'shear', level: 0.15 },
    { degradation: 'motion_blur', level: 2.0 },
    { degradation: 'creases', level: 15.0 },
    { degradation: 'shadow', level: 120.0 },
    { degradation: 'dark_blur', level: 160.0 },
    { degradation: 'crumpled_skew', level: 25.0 },
    { degradation: 'faded_thermal', level: 0.25 }
  ];
  
  try {
    for (const step of steps) {
      // Execute the single step on the backend
      const result = await triggerStressStep(step.degradation, step.level);
      
      // Append the step result to the scorecard list in real-time
      stressResults.value.push(result);
      
      // Mount the document details to render the visual degraded image immediately
      selectedStressRun.value = result;
      if (result.document_id) {
        const docData = await getDocument(result.document_id);
        stressDocument.value = docData;
      }
      
      // Delay for 2.5 seconds per step to allow visual inspection
      await new Promise(resolve => setTimeout(resolve, 2500));
    }
  } catch (error) {
    console.error("Stress test step failed:", error);
  } finally {
    isStressRunning.value = false;
  }
};

const selectStressRun = async (run: StressTestRun) => {
  selectedStressRun.value = run;
  stressDocument.value = null;
  if (run.document_id) {
    try {
      const details = await getDocument(run.document_id);
      stressDocument.value = details;
    } catch (e) {
      console.error("Failed to fetch stress document details:", e);
    }
  }
};

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value;
};

const scrollToBottom = () => {
  if (terminalBody.value) {
    terminalBody.value.scrollTop = terminalBody.value.scrollHeight;
  }
};

const getAccuracyBg = (acc: number) => {
  if (acc >= 90) return 'rgba(34, 197, 94, 0.12)';
  if (acc >= 70) return 'rgba(234, 179, 8, 0.12)';
  return 'rgba(239, 68, 68, 0.12)';
};

const getAccuracyColor = (acc: number) => {
  if (acc >= 90) return 'rgb(74, 222, 128)';
  if (acc >= 70) return 'rgb(250, 204, 21)';
  return 'rgb(248, 113, 113)';
};
</script>

<style scoped src="./OcrSandbox.css"></style>
