import AsyncStorage from '@react-native-async-storage/async-storage';

function sessionStorageKey(userId) {
  return userId ? `session_id_${userId}` : null;
}

async function getCurrentUserId(user) {
  if (user?.id) return user.id;

  const raw = await AsyncStorage.getItem('user_data');
  if (!raw) return null;

  try {
    return JSON.parse(raw)?.id || null;
  } catch {
    return null;
  }
}

export function getSessionStorageKey(user) {
  return sessionStorageKey(user?.id);
}

export async function getCurrentUserSessionId(user) {
  const key = sessionStorageKey(await getCurrentUserId(user));
  if (!key) return null;
  return AsyncStorage.getItem(key);
}

export async function setCurrentUserSessionId(user, sessionId) {
  const key = sessionStorageKey(await getCurrentUserId(user));
  if (!key || !sessionId) return;
  await AsyncStorage.setItem(key, sessionId);
}

export async function removeCurrentUserSessionId(user) {
  const key = sessionStorageKey(await getCurrentUserId(user));
  if (!key) return;
  await AsyncStorage.removeItem(key);
}
