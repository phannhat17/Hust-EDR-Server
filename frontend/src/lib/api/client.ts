import axios from 'axios';
import { env } from '@/config/env';

// Create an axios instance with default config
export const apiClient = axios.create({
  baseURL: env.API_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': env.API_KEY,
  },
  timeout: 10000, // 10 seconds
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Any status codes outside the range of 2xx
    console.error('API Error:', error);
    
    // You can add global error handling here
    // For example, redirect to login page if 401 Unauthorized
    
    return Promise.reject(error);
  }
);

// Request interceptor to add auth tokens if needed
apiClient.interceptors.request.use(
  (config) => {
    // You can add authentication tokens here if needed
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
); 