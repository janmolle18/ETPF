const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';

export interface LineItem {
  description: string;
  unit_price: number;
  quantity: number;
  total: number;
}

export interface ExtractedData {
  vendor_name?: string;
  tax_id?: string;
  phone?: string;
  date?: string;
  total_amount?: number;
  tax_amount?: number;
  currency?: string;
  line_items?: LineItem[];
}

export interface LayoutBlock {
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
  accuracy?: number;
  ground_truth?: string;
  healed?: boolean;
  confidence_gain?: number;
  original_text?: string;
}

export interface OptimizationStats {
  low_conf_original: number;
  healed_count: number;
  avg_confidence_gain: number;
  healing_time_ms: number;
}

export interface DeskewStats {
  detected_angle_deg: number;
  correction_applied_deg: number;
  deskew_applied: boolean;
  error?: string;
}

export interface PostprocessingStats {
  total_blocks: number;
  modified_blocks_count: number;
  rules_active: number;
  rule_trigger_counts: Record<string, number>;
  change_logs: string[];
}

export interface LayoutData {
  width: number;
  height: number;
  blocks: LayoutBlock[];
  optimization_stats?: OptimizationStats;
  deskew_stats?: DeskewStats;
  postprocessing_stats?: PostprocessingStats;
}

export interface DocumentResponse {
  id: string;
  filename: string;
  content_type: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  file_path: string;
  raw_text?: string;
  layout_data?: LayoutData;
  extracted_data?: ExtractedData;
  created_at: string;
  updated_at: string;
}

export interface StressTestBlock {
  predicted_value: string;
  actual_value: string;
  confidence_pct: number;
  match_accuracy_pct: number;
  healed?: boolean;
  original_text?: string | null;
  bounding_box?: {
    x_pct: number;
    y_pct: number;
    width_pct: number;
    height_pct: number;
  };
}

export interface StressTestRun {
  document_id: string | null;
  degradation: string;
  level: number;
  label: string;
  confidence: number;
  accuracy: number;
  time_ms: number;
  blocks_found: number;
  optimization_stats?: OptimizationStats;
  deskew_stats?: DeskewStats;
  postprocessing_stats?: PostprocessingStats;
  ground_truth_lines?: string[];
  blocks?: StressTestBlock[];
}

export async function uploadDocument(file: File): Promise<DocumentResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }

  return response.json();
}

export async function listDocuments(): Promise<DocumentResponse[]> {
  const response = await fetch(`${API_BASE_URL}/documents/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch documents: ${response.statusText}`);
  }
  return response.json();
}

export async function getDocument(id: string): Promise<DocumentResponse> {
  const response = await fetch(`${API_BASE_URL}/documents/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch document: ${response.statusText}`);
  }
  return response.json();
}

export async function deleteDocument(id: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/documents/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Deletion failed: ${response.statusText}`);
  }
}

export async function updateDocument(id: string, updates: Partial<DocumentResponse>): Promise<DocumentResponse> {
  const response = await fetch(`${API_BASE_URL}/documents/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    throw new Error(`Update failed: ${response.statusText}`);
  }

  return response.json();
}

export function getDocumentFileUrl(id: string, preview: boolean = false): string {
  return `${API_BASE_URL}/documents/${id}/file${preview ? '?preview=true' : ''}`;
}

export async function triggerSandbox(type: string): Promise<{ document_id: string; logs: string[] }> {
  const response = await fetch(`${API_BASE_URL}/documents/sandbox/trigger`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ type }),
  });

  if (!response.ok) {
    throw new Error(`Sandbox run failed: ${response.statusText}`);
  }

  return response.json();
}

export async function triggerStressTest(): Promise<StressTestRun[]> {
  const response = await fetch(`${API_BASE_URL}/documents/sandbox/stress`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Stress test failed: ${response.statusText}`);
  }

  return response.json();
}

export async function triggerStressStep(degradation: string, level: number): Promise<StressTestRun> {
  const response = await fetch(`${API_BASE_URL}/documents/sandbox/stress/step`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ degradation, level }),
  });

  if (!response.ok) {
    throw new Error(`Stress step failed: ${response.statusText}`);
  }

  return response.json();
}
