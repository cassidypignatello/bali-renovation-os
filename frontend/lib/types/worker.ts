/**
 * Worker and contractor types matching backend schemas
 * Maps to backend/app/schemas/worker.py
 */

export enum TrustLevel {
  VERIFIED = "VERIFIED",
  HIGH = "HIGH",
  MEDIUM = "MEDIUM",
  LOW = "LOW",
}

export interface TrustScoreDetailed {
  total_score: number;
  trust_level: TrustLevel;
  breakdown: {
    source: number;
    reviews: number;
    rating: number;
    verification: number;
    freshness: number;
  };
  source_tier: string;
  review_count: number;
  rating: number | null;
}

export interface WorkerContact {
  phone: string | null;
  whatsapp: string | null;
  email: string | null;
  website: string | null;
}

export interface WorkerLocation {
  address: string | null;
  area: string;
  latitude: number | null;
  longitude: number | null;
  maps_url: string | null;
}

export interface WorkerReview {
  rating: number;
  text: string;
  reviewer: string;
  date: string;
  source: string;
}

export interface WorkerPreview {
  id: string;
  preview_name: string;
  trust_score: TrustScoreDetailed;
  location: string;
  specializations: string[];
  preview_review: string | null;
  photos_count: number;
  opening_hours: string | null;
  price_idr_per_day: number | null;
  contact_locked: boolean;
  unlock_price_idr: number;
}

export interface WorkerFullDetails {
  id: string;
  business_name: string;
  trust_score: TrustScoreDetailed;
  contact: WorkerContact;
  location: WorkerLocation;
  reviews: WorkerReview[];
  specializations: string[];
  photos_count: number;
  opening_hours: string | null;
  categories: string[];
  price_idr_per_day: number | null;
  negotiation_script: string | null;
  unlocked_at: string;
}

export interface WorkerSearchRequest {
  project_type: string;
  location: string;
  min_trust_score?: number;
  budget_range?: "low" | "medium" | "high" | null;
  max_results?: number;
}

export interface WorkerSearchResponse {
  workers: WorkerPreview[];
  total_found: number;
  showing: number;
  unlock_price_idr: number;
  ok: boolean;
}
