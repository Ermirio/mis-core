import axios from 'axios';

// Create an Axios instance with the base URL from environment variables
// If VITE_API_URL is not defined, it falls back to a relative path which might be handled by proxy in dev
const baseURL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
    baseURL: baseURL,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 10000, // 10 seconds timeout
});

// Response interceptor for generic error handling (optional but recommended)
api.interceptors.response.use(
    (response) => {
        return response.data; // Return the data directly to simplify usage
    },
    (error) => {
        // Handle specific error status codes here if needed
        if (error.response) {
            // The request was made and the server responded with a status code
            // that falls out of the range of 2xx
            console.error('API Error Response:', error.response.data);
            console.error('API Error Status:', error.response.status);
        } else if (error.request) {
            // The request was made but no response was received
            console.error('API No Response:', error.request);
        } else {
            // Something happened in setting up the request that triggered an Error
            console.error('API Request Error:', error.message);
        }
        return Promise.reject(error);
    }
);

// API methods wrapper
const ApiService = {
    // Generic methods
    get: (url, config = {}) => api.get(url, config),
    post: (url, data, config = {}) => api.post(url, data, config),
    put: (url, data, config = {}) => api.put(url, data, config),
    delete: (url, config = {}) => api.delete(url, config),

    // Specific endpoints can be added here as helper methods if desired
};

export default ApiService;
