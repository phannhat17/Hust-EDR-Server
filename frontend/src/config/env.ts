/**
 * Environment configuration variables
 */

/**
 * Environment configuration
 */
export const env = {
  /**
   * API base URL
   */
  API_URL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',

  /**
   * API key for authentication
   */
  API_KEY: import.meta.env.VITE_API_KEY || 'development-key',

  /**
   * Application environment
   */
  NODE_ENV: import.meta.env.NODE_ENV || 'development',

  /**
   * Is production environment
   */
  isProd: import.meta.env.PROD === true,

  /**
   * Is development environment
   */
  isDev: import.meta.env.DEV === true,
}; 