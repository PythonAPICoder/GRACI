/**
 * Main Ollama service for G.R.A.C.I.
 * Orchestrates Ollama client operations and integrates with the registry system.
 */

import { OllamaClient } from './client.js';
import { getConfig } from '../../core/config/loader.js';
import { logger } from '../../core/logging/logger.js';

export class OllamaService {
  private readonly client: OllamaClient;
  private static instance: OllamaService | null = null;

  private constructor() {
    // Use configuration to determine endpoint
    const config = getConfig();
    this.client = new OllamaClient(config.ollama.default_endpoint);
    logger.info('Ollama service initialized');
  }

  /**
   * Get the singleton instance of OllamaService
   */
  static getInstance(): OllamaService {
    if (!OllamaService.instance) {
      OllamaService.instance = new OllamaService();
    }
    return OllamaService.instance;
  }

  /**
   * Check if the Ollama server is reachable and healthy
   */
  async checkHealth(): Promise<{ success: boolean; error?: string }> {
    return await this.client.checkHealth();
  }

  /**
   * Run inference using the default model from configuration
   */
  async runInference(
    prompt: string
  ): Promise<{ success: boolean; response?: string; error?: string }> {
    const config = getConfig();
    const model = config.ollama.default_model;

    const result = await this.client.runInference(model, prompt);

    if (result.success && result.response) {
      return {
        success: true,
        response: result.response.response
      };
    }

    return {
      success: false,
      error: result.error || 'Unknown error during inference'
    };
  }

  /**
   * Get the configured endpoint URL
   */
  getEndpoint(): string {
    return this.client.getEndpoint();
  }
}