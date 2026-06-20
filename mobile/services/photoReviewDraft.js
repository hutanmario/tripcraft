import AsyncStorage from '@react-native-async-storage/async-storage';

const PREFIX = 'photo_review_draft_';

function draftKey(id) {
  return `${PREFIX}${id}`;
}

export async function savePhotoReviewDraft(payload) {
  const id = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  await AsyncStorage.setItem(draftKey(id), JSON.stringify(payload));
  return id;
}

export async function loadPhotoReviewDraft(id) {
  if (!id) return null;
  const raw = await AsyncStorage.getItem(draftKey(id));
  if (!raw) return null;
  return JSON.parse(raw);
}

export async function clearPhotoReviewDraft(id) {
  if (!id) return;
  await AsyncStorage.removeItem(draftKey(id));
}
