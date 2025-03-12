// frontend/src/services/api.ts
import axios from 'axios';

const API_URL = 'http://localhost:5000/api';

export const api = axios.create({
  baseURL: API_URL
});

export const getProducts = async () => {
  const response = await api.get('/products');
  return response.data;
};