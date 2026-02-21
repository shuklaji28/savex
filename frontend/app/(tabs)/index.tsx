import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, SafeAreaView,
  Animated, Platform, ActivityIndicator, TextInput,
  KeyboardAvoidingView, Keyboard,
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

// Web-only: use browser MediaRecorder API
let webMediaRecorder: any = null;
let webAudioChunks: Blob[] = [];

export default function HomeScreen() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [showTextInput, setShowTextInput] = useState(false);
  const [textInput, setTextInput] = useState('');
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
      fadeAnim.setValue(0);
      Animated.timing(fadeAnim, { toValue: 1, duration: 400, useNativeDriver: true }).start();
      const timer = setTimeout(() => {
        Animated.timing(fadeAnim, { toValue: 0, duration: 400, useNativeDriver: true }).start(() => setResult(null));
      }, 8000);
      return () => clearTimeout(timer);
    }
  }, [result]);

  async function checkPermission() {
    if (Platform.OS === 'web') {
      // On web, check browser mic permission
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(track => track.stop()); // release immediately
        setPermissionGranted(true);
      } catch {
        // Try requesting again on user gesture
        setPermissionGranted(false);
      }
    } else {
      // On native, use expo-av permissions
      try {
        const { status } = await Audio.requestPermissionsAsync();
        setPermissionGranted(status === 'granted');
      } catch {
        setPermissionGranted(false);
      }
    }
  }

  async function requestAndGrantPermission() {
    if (Platform.OS === 'web') {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(track => track.stop());
        setPermissionGranted(true);
        return true;
      } catch (e: any) {
        setError('Microphone access denied. Please allow mic access in your browser settings.');
        return false;
      }
    } else {
      try {
        const { status } = await Audio.requestPermissionsAsync();
        if (status === 'granted') {
          setPermissionGranted(true);
          return true;
        }
        setError('Microphone permission denied. Please grant access in Settings.');
        return false;
      } catch {
        return false;
      }
    }
  }

  async function startRecording() {
    setError(null);
    setResult(null);

    // Ensure permission
    if (!permissionGranted) {
      const granted = await requestAndGrantPermission();
      if (!granted) return;
    }

    if (Platform.OS === 'web') {
      // Use browser MediaRecorder API directly
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        webAudioChunks = [];
        webMediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        webMediaRecorder.ondataavailable = (event: any) => {
          if (event.data.size > 0) {
            webAudioChunks.push(event.data);
          }
        };
        webMediaRecorder.start();
        setIsRecording(true);
      } catch (e: any) {
        console.error('Web recording error:', e);
        setError('Microphone access failed: ' + e.message + '. Check browser permissions.');
      }
    } else {
      // Native: use expo-av
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
        console.error('Native recording error:', e);
        setError('Recording failed: ' + e.message);
      }
    }
  }

  async function stopRecording() {
    setIsRecording(false);
    setIsProcessing(true);

    if (Platform.OS === 'web') {
      // Web: stop MediaRecorder and send blob
      try {
        if (!webMediaRecorder) throw new Error('No active recording');
        await new Promise<void>((resolve) => {
          webMediaRecorder.onstop = () => resolve();
          webMediaRecorder.stop();
        });
        // Stop all tracks
        webMediaRecorder.stream.getTracks().forEach((track: any) => track.stop());
        const blob = new Blob(webAudioChunks, { type: 'audio/webm' });
        webAudioChunks = [];
        webMediaRecorder = null;
        if (blob.size === 0) throw new Error('Empty recording');
        await sendAudioBlob(blob);
      } catch (e: any) {
        setError('Failed to process recording: ' + e.message);
        setIsProcessing(false);
      }
    } else {
      // Native: use expo-av
      try {
        if (!recordingRef.current) throw new Error('No active recording');
        await recordingRef.current.stopAndUnloadAsync();
        const uri = recordingRef.current.getURI();
        recordingRef.current = null;
        if (!uri) throw new Error('No recording URI');
        await sendAudioNative(uri);
      } catch (e: any) {
        setError('Failed to process: ' + e.message);
        setIsProcessing(false);
      }
    }
  }

  async function sendAudioBlob(blob: Blob) {
    try {
      const formData = new FormData();
      formData.append('audio', blob, 'recording.webm');
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

  async function sendAudioNative(uri: string) {
    try {
      const formData = new FormData();
      formData.append('audio', {
        uri,
        name: 'recording.m4a',
        type: 'audio/m4a',
      } as any);
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

  async function sendText() {
    if (!textInput.trim()) return;
    Keyboard.dismiss();
    setError(null);
    setResult(null);
    setIsProcessing(true);
    try {
      const res = await fetch(`${API_URL}/api/process-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: textInput }),
      });
      const data: ProcessResult = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setResult(data);
        setTextInput('');
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

  const showResult = result && result.items && result.items.length > 0;

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <View style={styles.header}>
          <Text style={styles.title}>sustain</Text>
          <Text style={styles.subtitle}>
            {showTextInput ? 'type what you bought' : 'speak to log groceries'}
          </Text>
        </View>

        <View style={styles.center}>
          {/* Result display */}
          {showResult && (
            <Animated.View style={[styles.resultBox, { opacity: fadeAnim }]}>
              <Text style={styles.resultTitle}>
                Added {result!.count} item{result!.count !== 1 ? 's' : ''}
              </Text>
              {result!.transcript ? (
                <Text style={styles.transcript}>"{result!.transcript}"</Text>
              ) : null}
              {result!.items.map((item, i) => (
                <View key={item.id || i} style={styles.resultItem}>
                  <View style={[styles.urgencyDot, { backgroundColor: getUrgencyColor(item.urgency_level) }]} />
                  <Text style={styles.resultItemName}>{item.normalized_name}</Text>
                  <Text style={styles.resultItemMeta}>
                    {item.quantity} {item.unit} · {item.days_remaining}d left
                  </Text>
                </View>
              ))}
            </Animated.View>
          )}

          {error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{error}</Text>
              <TouchableOpacity testID="dismiss-error-btn" onPress={() => setError(null)} style={styles.dismissBtn}>
                <Text style={styles.dismissText}>Dismiss</Text>
              </TouchableOpacity>
            </View>
          )}

          {isRecording && (
            <View style={styles.listeningBadge}>
              <View style={styles.redDot} />
              <Text style={styles.listeningText}>Listening... tap to stop</Text>
            </View>
          )}
          {isProcessing && (
            <View style={styles.listeningBadge}>
              <ActivityIndicator size="small" color="#F5F5DC" />
              <Text style={styles.listeningText}>Processing...</Text>
            </View>
          )}

          {!showTextInput ? (
            <>
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
                  disabled={isProcessing}
                >
                  <Ionicons
                    name={isRecording ? 'stop' : 'mic'}
                    size={40}
                    color={isRecording ? '#EF4444' : '#0A0A0A'}
                  />
                </TouchableOpacity>
              </Animated.View>

              {!isRecording && !isProcessing && !showResult && !error && (
                <Text style={styles.hint}>Tap to start recording</Text>
              )}

              <TouchableOpacity
                testID="switch-to-text-btn"
                onPress={() => setShowTextInput(true)}
                style={styles.switchBtn}
              >
                <Ionicons name="create-outline" size={16} color="#52525B" />
                <Text style={styles.switchText}>or type instead</Text>
              </TouchableOpacity>
            </>
          ) : (
            <View style={styles.textInputWrap}>
              <TextInput
                testID="text-input"
                style={styles.textInput}
                placeholder="e.g. 2 tomatoes and milk in fridge"
                placeholderTextColor="#52525B"
                value={textInput}
                onChangeText={setTextInput}
                multiline
                returnKeyType="send"
                onSubmitEditing={sendText}
              />
              <View style={styles.textActions}>
                <TouchableOpacity
                  testID="send-text-btn"
                  style={[styles.sendBtn, !textInput.trim() && styles.sendBtnDisabled]}
                  onPress={sendText}
                  disabled={!textInput.trim() || isProcessing}
                >
                  <Ionicons name="arrow-up" size={20} color={textInput.trim() ? '#0A0A0A' : '#52525B'} />
                </TouchableOpacity>
              </View>
              <TouchableOpacity
                testID="switch-to-voice-btn"
                onPress={() => setShowTextInput(false)}
                style={styles.switchBtn}
              >
                <Ionicons name="mic-outline" size={16} color="#52525B" />
                <Text style={styles.switchText}>use voice instead</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  flex: { flex: 1 },
  header: { paddingHorizontal: 24, paddingTop: 16 },
  title: { fontSize: 32, fontWeight: '700', color: '#F5F5DC', letterSpacing: -0.5 },
  subtitle: { fontSize: 14, color: '#52525B', marginTop: 4, fontWeight: '500' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  listeningBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 24,
    paddingHorizontal: 16, paddingVertical: 8, backgroundColor: '#18181B', borderRadius: 20,
  },
  redDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: '#EF4444' },
  listeningText: { color: '#A1A1AA', fontSize: 14, fontWeight: '500' },
  micOuter: {
    width: 120, height: 120, borderRadius: 60,
    backgroundColor: 'rgba(245,245,220,0.06)', alignItems: 'center', justifyContent: 'center',
  },
  micButton: {
    width: 88, height: 88, borderRadius: 44, backgroundColor: '#F5F5DC',
    alignItems: 'center', justifyContent: 'center',
  },
  micRecording: { backgroundColor: '#27272A' },
  micProcessing: { backgroundColor: '#27272A', opacity: 0.6 },
  hint: { color: '#52525B', fontSize: 14, marginTop: 20, fontWeight: '500' },
  switchBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 20,
    paddingHorizontal: 16, paddingVertical: 10,
  },
  switchText: { color: '#52525B', fontSize: 13, fontWeight: '500' },
  textInputWrap: { width: '100%', paddingHorizontal: 24, alignItems: 'center' },
  textInput: {
    width: '100%', backgroundColor: '#18181B', borderRadius: 16, padding: 16,
    color: '#F5F5DC', fontSize: 16, minHeight: 80, textAlignVertical: 'top',
    borderWidth: 1, borderColor: '#27272A',
  },
  textActions: { flexDirection: 'row', justifyContent: 'flex-end', width: '100%', marginTop: 10 },
  sendBtn: {
    width: 44, height: 44, borderRadius: 22, backgroundColor: '#F5F5DC',
    alignItems: 'center', justifyContent: 'center',
  },
  sendBtnDisabled: { backgroundColor: '#27272A' },
  errorBox: {
    marginHorizontal: 24, marginBottom: 16, padding: 16, width: '85%',
    backgroundColor: 'rgba(239,68,68,0.1)', borderRadius: 12,
    borderWidth: 1, borderColor: 'rgba(239,68,68,0.2)',
  },
  errorText: { color: '#EF4444', fontSize: 14 },
  dismissBtn: { marginTop: 8, alignSelf: 'flex-end' },
  dismissText: { color: '#A1A1AA', fontSize: 13, fontWeight: '500' },
  resultBox: {
    marginHorizontal: 24, marginBottom: 16, padding: 16, width: '85%',
    backgroundColor: '#18181B', borderRadius: 16, borderWidth: 1, borderColor: '#27272A',
  },
  resultTitle: { color: '#10B981', fontSize: 16, fontWeight: '600', marginBottom: 4 },
  transcript: { color: '#52525B', fontSize: 13, fontStyle: 'italic', marginBottom: 12 },
  resultItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, gap: 8 },
  urgencyDot: { width: 6, height: 6, borderRadius: 3 },
  resultItemName: { color: '#F5F5DC', fontSize: 15, fontWeight: '500', flex: 1 },
  resultItemMeta: { color: '#A1A1AA', fontSize: 13 },
});
