import { describe, it, expect } from 'vitest';
import { logger } from '../src/core/logging/logger.js';

describe('Logger', () => {
  it('should log info without throwing', () => {
    expect(() => logger.info('test')).not.toThrow();
  });
});