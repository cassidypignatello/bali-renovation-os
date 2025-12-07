/**
 * Materials and pricing API methods
 */

import { apiClient } from "./client";
import type { ApiResponse } from "../types";

export interface Material {
  id: string;
  name: string;
  category: string;
  unit: string;
  current_price_idr: number;
  source: string;
  confidence: number;
  last_updated: string;
  marketplace_url?: string;
}

export interface MaterialHistory {
  material_id: string;
  price_history: {
    date: string;
    price_idr: number;
    source: string;
  }[];
}

export const materialsApi = {
  /**
   * Get materials list with current pricing
   * GET /materials
   */
  list: async (params?: {
    category?: string;
    search?: string;
  }): Promise<ApiResponse<{ materials: Material[] }>> => {
    return apiClient.get<{ materials: Material[] }>("/materials", params);
  },

  /**
   * Get price history for a material
   * GET /materials/{id}/history
   */
  getHistory: async (
    materialId: string
  ): Promise<ApiResponse<MaterialHistory>> => {
    return apiClient.get<MaterialHistory>(`/materials/${materialId}/history`);
  },
};
