export const logger = {
  info(message: string, ...meta: unknown[]): void {
    console.log(`[INFO] ${new Date().toISOString()} ${message}`, ...meta);
  },
  error(error: Error | string, meta?: Record<string, unknown>): void {
    const errorInfo = error instanceof Error ? { message: error.message, stack: error.stack, ...meta } : { message: error, ...meta };
    console.error(`[ERROR] ${new Date().toISOString()}`, JSON.stringify(errorInfo, null, 2));
  },
  warn(message: string, ...meta: unknown[]): void {
    console.warn(`[WARN] ${new Date().toISOString()} ${message}`, ...meta);
  }
};