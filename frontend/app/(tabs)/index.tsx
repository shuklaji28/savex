import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, SafeAreaView,
  Animated, Platform, ActivityIndicator,
} from 'react-native';
import { Audio } from 'expo-av';
import { Ionicons } from '@expo/vector-icons';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type FoodItem = {
  id: string;
  item_name: string;
  normalized_name: string;
  quantity: number;
  unit: string;
  storage_location: string;
  expiry_date: string;
  days_remaining: number;
  urgency_level: string;
};

type ProcessResult = {
  transcript: string;
  items: FoodItem[];
  count: number;
  error?: string;
};

export default function HomeScreen() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [permissionGranted, setPermissionGranted] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    checkPermission();
  }, []);

  useEffect(() => {
    if (isRecording) {
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, { toValue: 1.15, duration: 800, useNativeDriver: true }),
          Animated.timing(pulseAnim, { toValue: 1, duration: 800, useNativeDriver: true }),
        ])
      );
      pulse.start();
      return () => pulse.stop();
    } else {
      pulseAnim.setValue(1);
    }
  }, [isRecording]);

  useEffect(() => {
    if (result) {
      Animated.timing(fadeAnim, { toValue: 1, duration: 400, useNativeDriver: true }).start();
      const timer = setTimeout(() => {
        Animated.timing(fadeAnim, { toValue: 0, duration: 400, useNativeDriver: true }).start(() => setResult(null));
      }, 6000);
      return () => clearTimeout(timer);
    }
  }, [result]);

  async function checkPermission() {
    try {
      const { status } = await Audio.requestPermissionsAsync();
      setPermissionGranted(status === 'granted');
    } catch {
      setPermissionGranted(false);
    }
  }

  async function startRecording() {
    setError(null);
    setResult(null);
    try {
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      recordingRef.current = recording;
      setIsRecording(true);
    } catch (e: any) {
      setError('Failed to start recording: ' + e.message);
    }
  }

  async function stopRecording() {
    if (!recordingRef.current) return;
    setIsRecording(false);
    setIsProcessing(true);
    try {
      await recordingRef.current.stopAndUnloadAsync();
      const uri = recordingRef.current.getURI();
      recordingRef.current = null;
      if (!uri) throw new Error('No recording URI');
      await sendAudio(uri);
    } catch (e: any) {
      setError('Failed to process: ' + e.message);
      setIsProcessing(false);
    }
  }

  async function sendAudio(uri: string) {
    try {
      const formData = new FormData();
      if (Platform.OS === 'web') {
        const response = await fetch(uri);
        const blob = await response.blob();
        formData.append('audio', blob, 'recording.webm');
      } else {
        formData.append('audio', {
          uri,
          name: 'recording.m4a',
          type: 'audio/m4a',
        } as any);
      }
      const res = await fetch(`${API_URL}/api/process-voice`, {
        method: 'POST',
        body: formData,
      });
      const data: ProcessResult = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setResult(data);
      }
    } catch (e: any) {
      setError('Network error: ' + e.message);
    } finally {
      setIsProcessing(false);
    }
  }

  function handleMicPress() {
    if (isProcessing) return;
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  function getUrgencyColor(urgency: string) {
    switch (urgency) {
      case 'expired': return '#EF4444';
      case 'critical': return '#EF4444';
      case 'urgent': return '#F59E0B';
      case 'upcoming': return '#3B82F6';
      default: return '#10B981';
    }
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>sustain</Text>
        <Text style={styles.subtitle}>speak to log groceries</Text>
      </View>

      <View style={styles.center}>
        {isRecording && (
          <View style={styles.listeningBadge}>
            <View style={styles.redDot} />
            <Text style={styles.listeningText}>Listening...</Text>
          </View>
        )}
        {isProcessing && (
          <View style={styles.listeningBadge}>
            <ActivityIndicator size="small" color="#F5F5DC" />
            <Text style={styles.listeningText}>Processing...</Text>
          </View>
        )}

        <Animated.View style={[styles.micOuter, { transform: [{ scale: pulseAnim }] }]}>
          <TouchableOpacity
            testID="mic-button"
            style={[
              styles.micButton,
              isRecording && styles.micRecording,
              isProcessing && styles.micProcessing,
            ]}
            onPress={handleMicPress}
            activeOpacity={0.7}
            disabled={!permissionGranted || isProcessing}
          >
            <Ionicons
              name={isRecording ? 'stop' : 'mic'}
              size={40}
              color={isRecording ? '#EF4444' : '#0A0A0A'}
            />
          </TouchableOpacity>
        </Animated.View>

        {!permissionGranted && (
          <TouchableOpacity testID="grant-permission-btn" onPress={checkPermission} style={styles.permBtn}>
            <Text style={styles.permText}>Tap to grant microphone access</Text>
          </TouchableOpacity>
        )}

        {!isRecording && !isProcessing && !result && !error && permissionGranted && (
          <Text style={styles.hint}>Tap to start recording</Text>
        )}
      </View>

      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {result && result.items && result.items.length > 0 && (
        <Animated.View style={[styles.resultBox, { opacity: fadeAnim }]}>
          <Text style={styles.resultTitle}>
            Added {result.count} item{result.count !== 1 ? 's' : ''}
          </Text>
          {result.transcript ? (
            <Text style={styles.transcript}>"{result.transcript}"</Text>
          ) : null}
          {result.items.map((item, i) => (
            <View key={item.id || i} style={styles.resultItem}>
              <View style={[styles.urgencyDot, { backgroundColor: getUrgencyColor(item.urgency_level) }]} />
              <Text style={styles.resultItemName}>
                {item.normalized_name}
              </Text>
              <Text style={styles.resultItemMeta}>
                {item.quantity} {item.unit} · {item.days_remaining}d left
              </Text>
            </View>
          ))}
        </Animated.View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0A0A0A',
  },
  header: {
    paddingHorizontal: 24,
    paddingTop: 16,
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    color: '#F5F5DC',
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 14,
    color: '#52525B',
    marginTop: 4,
    fontWeight: '500',
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  listeningBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 24,
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: '#18181B',
    borderRadius: 20,
  },
  redDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#EF4444',
  },
  listeningText: {
    color: '#A1A1AA',
    fontSize: 14,
    fontWeight: '500',
  },
  micOuter: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: 'rgba(245,245,220,0.06)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  micButton: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: '#F5F5DC',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#F5F5DC',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.3,
    shadowRadius: 20,
    elevation: 10,
  },
  micRecording: {
    backgroundColor: '#27272A',
  },
  micProcessing: {
    backgroundColor: '#27272A',
    opacity: 0.6,
  },
  hint: {
    color: '#52525B',
    fontSize: 14,
    marginTop: 20,
    fontWeight: '500',
  },
  permBtn: {
    marginTop: 20,
    paddingHorizontal: 20,
    paddingVertical: 10,
    backgroundColor: '#18181B',
    borderRadius: 12,
  },
  permText: {
    color: '#F5F5DC',
    fontSize: 14,
  },
  errorBox: {
    marginHorizontal: 24,
    marginBottom: 24,
    padding: 16,
    backgroundColor: 'rgba(239,68,68,0.1)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.2)',
  },
  errorText: {
    color: '#EF4444',
    fontSize: 14,
  },
  resultBox: {
    marginHorizontal: 24,
    marginBottom: 24,
    padding: 16,
    backgroundColor: '#18181B',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#27272A',
  },
  resultTitle: {
    color: '#10B981',
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  transcript: {
    color: '#52525B',
    fontSize: 13,
    fontStyle: 'italic',
    marginBottom: 12,
  },
  resultItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    gap: 8,
  },
  urgencyDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  resultItemName: {
    color: '#F5F5DC',
    fontSize: 15,
    fontWeight: '500',
    flex: 1,
  },
  resultItemMeta: {
    color: '#A1A1AA',
    fontSize: 13,
  },
});
