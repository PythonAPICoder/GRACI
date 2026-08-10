/**
 * Ollama HTTP API client for G.R.A.C.I.
 * Handles connectivity checks and inference requests to Ollama endpoints.
 */

import { getConfig } from '../../core/config/loader.js';
import { logger } from '../../core/logging/logger.js';

// Define types for Ollama responses
export interface OllamaResponse {
  model: string;
  response: string;
  done: boolean;
  context?: number[];
  total_duration?: number;
  load_duration?: number;
  prompt_eval_count?: number;
  prompt_eval_duration?: number;
  eval_count?: number;
  eval_duration?: number;
}

export interface OllamaVersionResponse {
  version: string;
}

export interface OllamaError {
  error: string;
}

export class OllamaClient {
  private readonly endpoint: string;
  private readonly timeoutMs: number;

  constructor(endpoint?: string) {
    const config = getConfig();
    this.endpoint = endpoint || config.ollama.default_endpoint;
    this.timeoutMs = config.ollama.request_timeout_ms;
    // logger.debug(`Ollama client initialized for endpoint: ${this.endpoint}`); // Removed debug as not part of existing API
  }

  /**
   * Check if the Ollama server is reachable and healthy
   */
  async checkHealth(): Promise<{ success: boolean; error?: string }> {
    let timeoutId: NodeJS.Timeout | null = null;

    try {
      const controller = new AbortController();

      timeoutId = setTimeout(() => {
        controller.abort();
      }, this.timeoutMs);

      const response = await fetch(`${this.endpoint}/api/version`, {
        method: 'GET',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      if (!response.ok) {
        return {
          success: false,
          error: `HTTP ${response.status}: ${response.statusText}`,
        };
      }

      const data: OllamaVersionResponse = await response.json();

      // Validate structural integrity of version response
      if (!data || typeof data.version !== 'string' || data.version.length === 0) {
        return {
          success: false,
          error: `Malformed version response from Ollama server`,
        };
      }

      // logger.debug(`Ollama server at ${this.endpoint} is healthy`); // Removed debug as not part of existing API
      return { success: true };
    } catch (error) {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      if (error instanceof Error && error.name === 'AbortError') {
        logger.error(`Timeout connecting to Ollama at ${this.endpoint}`);
        return {
          success: false,
          error: `Connection timeout after ${this.timeoutMs}ms`
        };
      }

      if (error instanceof Error) {
        logger.error(`Failed to connect to Ollama at ${this.endpoint}: ${error.message}`);
        return {
          success: false,
          error: `Connection failed: ${error.message}`
        };
      }

      logger.error(`Unexpected error when connecting to Ollama at ${this.endpoint}`);
      return {
        success: false,
        error: 'An unexpected error occurred'
      };
    }
  }

  /**
   * Run inference using a specific model
   */
  async runInference(
    model: string,
    prompt: string
  ): Promise<{ success: boolean; response?: OllamaResponse; error?: string }> {
    let timeoutId: NodeJS.Timeout | null = null;

    try {
      const controller = new AbortController();

      timeoutId = setTimeout(() => {
        controller.abort();
      }, this.timeoutMs);

      const response = await fetch(`${this.endpoint}/api/generate`, {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model,
          prompt,
          stream: false,
        }),
      });

      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      if (!response.ok) {
        return {
          success: false,
          error: `HTTP ${response.status}: ${response.statusText}`,
        };
      }

      const data: OllamaResponse = await response.json();

      // Validate structural integrity of inference response
      if (!data || typeof data.response !== 'string') {
        return {
          success: false,
          error: `Malformed inference response from Ollama server`,
        };
      }

      if (data.done !== true) {
        return {
          success: false,
          error: `Incomplete inference response - done flag not set to true`,
        };
      }

      // logger.debug(`Inference completed successfully for model ${model}`); // Removed debug as not part of existing API
      return {
        success: true,
        response: data
      };
    } catch (error) {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      if (error instanceof Error && error.name === 'AbortError') {
        logger.error(`Timeout running inference on Ollama at ${this.endpoint}`);
        return {
          success: false,
          error: `Inference timeout after ${this.timeoutMs}ms`
        };
      }

      if (error instanceof Error) {
        logger.error(`Failed to run inference on Ollama at ${this.endpoint}: ${error.message}`);
        return {
          success: false,
          error: `Inference failed: ${error.message}`
        };
      }

      logger.error(`Unexpected error when running inference on Ollama at ${this.endpoint}`);
      return {
        success: false,
        error: 'An unexpected error occurred during inference'
      };
    }
  }

  /**
   * Get the endpoint URL
   */
  getEndpoint(): string {
    return this.endpoint;
  }
}