/**
 * Cost estimation types matching backend schemas
 * Maps to backend/app/schemas/estimate.py
 */

export enum EstimateStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
}

export interface BOMItem {
  material_name: string;
  quantity: number;
  unit: string;
  unit_price_idr: number;
  total_price_idr: number;
  source: string;
  confidence: number;
  marketplace_url: string | null;
}

export interface EstimateResponse {
  estimate_id: string;
  status: EstimateStatus;
  project_type: string;
  bom_items: BOMItem[];
  total_cost_idr: number;
  labor_cost_idr: number;
  grand_total_idr: number;
  created_at: string;
  updated_at: string;
  error_message: string | null;
}

export interface EstimateStatusResponse {
  estimate_id: string;
  status: EstimateStatus;
  progress_percentage: number;
  message: string | null;
}
