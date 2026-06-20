import { createContext, useContext, useState } from 'react';
import apiClient from '../services/api';
import { Image as ExpoImage } from 'expo-image';
import { useAuth } from './AuthContext';
import { setCurrentUserSessionId } from '../services/session';

const QuizContext = createContext(null);
const IMAGE_PREFETCH_TIMEOUT_MS = 2500;

async function prefetchCardImage(card) {
  if (!card?.image_url) return;
  try {
    await Promise.race([
      ExpoImage.prefetch(card.image_url),
      new Promise((resolve) => setTimeout(resolve, IMAGE_PREFETCH_TIMEOUT_MS)),
    ]);
  } catch {
    // Continue with the card even if the image cache could not warm up.
  }
}

export function QuizProvider({ children }) {
  const { user } = useAuth();
  const [sessionId, setSessionId] = useState(null);
  const [currentCard, setCurrentCard] = useState(null);
  const [phase, setPhase] = useState('swipe');
  const [cardCount, setCardCount] = useState(0);
  const [entropy, setEntropy] = useState(999);
  const [questions, setQuestions] = useState([]);
  const [results, setResults] = useState(null);

  const startQuiz = async () => {
    const response = await apiClient.post('/quiz/v4/start');
    const data = response.data;
    setSessionId(data.session_id);
    await setCurrentUserSessionId(user, data.session_id);
    await prefetchCardImage(data.card);
    setCurrentCard(data.card);
    setPhase(data.phase ?? 'swipe');
    if (data.card_count != null) setCardCount(data.card_count);
    const cards = data.cards || (data.card ? [data.card] : []);
    cards.slice(0, 3).forEach(card => {
      if (card.image_url) ExpoImage.prefetch(card.image_url);
    });
  };

  const swipe = async (tagSlug, direction) => {
    const response = await apiClient.post('/quiz/v4/swipe', {
      session_id: sessionId,
      tag_slug: tagSlug,
      direction,
    });
    const data = response.data;
    setPhase(data.phase);
    if (data.card_count != null) setCardCount(data.card_count);
    if (data.entropy != null) setEntropy(data.entropy);
    if (data.questions) setQuestions(data.questions);
    if (data.card) {
      await prefetchCardImage(data.card);
      setCurrentCard(data.card);
    }
    return data;
  };

  const answer = async (questionId, answerValue) => {
    const response = await apiClient.post('/quiz/v4/answer', {
      session_id: sessionId,
      question_id: questionId,
      answer: answerValue,
    });
    const data = response.data;
    if (data.phase) setPhase(data.phase);
    if (data.questions) setQuestions(data.questions);
    return data;
  };

  const getResults = async () => {
    const response = await apiClient.get(`/quiz/v4/results/${sessionId}`);
    setResults(response.data);
    return response.data;
  };

  return (
    <QuizContext.Provider
      value={{ sessionId, currentCard, phase, cardCount, entropy, questions, results, startQuiz, swipe, answer, getResults }}
    >
      {children}
    </QuizContext.Provider>
  );
}

export function useQuiz() {
  const ctx = useContext(QuizContext);
  if (!ctx) throw new Error('useQuiz must be used within QuizProvider');
  return ctx;
}
