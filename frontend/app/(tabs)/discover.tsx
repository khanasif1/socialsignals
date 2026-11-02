import React from 'react';
import { useLocalSearchParams } from 'expo-router';
import { Feed } from '../../components/Feed';
export default function Discover() {
  const { topic } = useLocalSearchParams<{ topic?: string }>();
  return <Feed key={topic || 'all'} initialTopic={topic || ''} />;
}
