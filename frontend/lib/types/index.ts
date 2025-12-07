/**
 * Central export for all TypeScript types
 */

export * from "./worker";
export * from "./payment";
export * from "./estimate";

/**
 * Common API response wrapper
 */
export interface ApiResponse<T> {
  data?: T;
  error?: ApiError;
}

export interface ApiError {
  message: string;
  code?: string;
  details?: unknown;
}
