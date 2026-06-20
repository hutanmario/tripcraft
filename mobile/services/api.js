import axios from 'axios';
import * as SecureStore from 'expo-secure-store';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

const tokenStorage = Platform.OS === 'web'
  ? {
      getItemAsync: (key) => AsyncStorage.getItem(key),
    }
  : SecureStore;

const getBaseUrl = () => {
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL
  }

  if (__DEV__) {
    const hostUri = Constants.expoConfig?.hostUri || Constants.manifest?.debuggerHost
    if (hostUri) {
      const host = hostUri.split(':')[0]
      return `http://${host}:8000`
    }
    return 'http://localhost:8000'
  }

  throw new Error('EXPO_PUBLIC_API_URL must be configured for production builds')
}

export const BASE_URL = getBaseUrl();

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
});

api.interceptors.request.use(async (config) => {
  const token = await tokenStorage.getItemAsync('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
