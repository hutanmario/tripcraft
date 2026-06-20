import { createContext, useContext, useEffect, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import apiClient from '../services/api';
import { removeCurrentUserSessionId } from '../services/session';

const AuthContext = createContext(null);

const tokenStorage = Platform.OS === 'web'
  ? {
      getItemAsync: (key) => AsyncStorage.getItem(key),
      setItemAsync: (key, value) => AsyncStorage.setItem(key, value),
      deleteItemAsync: (key) => AsyncStorage.removeItem(key),
    }
  : SecureStore;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const storedToken = await tokenStorage.getItemAsync('access_token');
        const storedUser = await tokenStorage.getItemAsync('user');
        const asyncUser = await AsyncStorage.getItem('user_data');

        if (!storedToken) {
          await tokenStorage.deleteItemAsync('user');
          await AsyncStorage.removeItem('user_data');
          return;
        }

        const { data: serverUser } = await apiClient.get('/auth/me');
        const rawUser = storedUser || asyncUser;
        const restoredUser = serverUser || (rawUser ? JSON.parse(rawUser) : null);
        if (!restoredUser) throw new Error('No authenticated user found');

        setToken(storedToken);
        setUser(restoredUser);
        await tokenStorage.setItemAsync('user', JSON.stringify(restoredUser));
        await AsyncStorage.setItem('user_data', JSON.stringify(restoredUser));
      } catch {
        await tokenStorage.deleteItemAsync('access_token');
        await tokenStorage.deleteItemAsync('user');
        await AsyncStorage.removeItem('user_data');
        setToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  async function login(newToken, newUser) {
    await tokenStorage.deleteItemAsync('user');
    await tokenStorage.deleteItemAsync('access_token');
    await tokenStorage.setItemAsync('access_token', newToken);
    await tokenStorage.setItemAsync('user', JSON.stringify(newUser));
    await AsyncStorage.setItem('user_data', JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
    setIsLoading(false);
  }

  async function logout() {
    await removeCurrentUserSessionId(user);
    await tokenStorage.deleteItemAsync('access_token');
    await tokenStorage.deleteItemAsync('user');
    await AsyncStorage.removeItem('user_data');
    setToken(null);
    setUser(null);
    setIsLoading(false);
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isLoading, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
