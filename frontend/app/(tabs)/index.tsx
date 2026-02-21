import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, SafeAreaView,
  Animated, Platform, ActivityIndicator, TextInput,
  KeyboardAvoidingView, Keyboard, Linking,
} from 'react-native';
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

// ── Platform-specific recording helpers ──
// Web: browser MediaRecorder
let webMediaRecorder: any = null;
let webChunks: any[] = [];

// Native: expo-audio (lazy loaded to avoid web issues)
let AudioModule: any = null;
let useAudioRecorderRef: any = null;
let RecordingPresetsRef: any = null;

function isInIframe(): boolean {
  if (Platform.OS !== 'web') return false;
  try {
    return window.self !== window.top;
  } catch {
    return true; // cross-origin iframe
  }
}

export default function HomeScreen() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [showTextInput, setShowTextInput] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [inIframe, setInIframe] = useState(false);
  const [nativeRecorder, setNativeRecorder] = useState<any>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    initAudio();
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

  async function initAudio() {
    if (Platform.OS === 'web') {
      // Check if we're in an iframe
      const iframe = isInIframe();
      setInIframe(iframe);
      if (!iframe) {
        // Only request mic if not in iframe
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          stream.getTracks().forEach(t => t.stop());
          setPermissionGranted(true);
        } catch {
          setPermissionGranted(false);
        }
      }
    } else {
      // Native: use expo-audio
      try {
        const expoAudio = require('expo-audio');
        AudioModule = expoAudio.default || expoAudio;
        RecordingPresetsRef = expoAudio.RecordingPresets;
        // Request permission
        const perm = await AudioModule.requestRecordingPermissionsAsync();
        setPermissionGranted(perm.granted);
      } catch (e: any) {
        console.error('Native audio init error:', e);
        setPermissionGranted(false);
      }
    }
  }

  async function startRecording() {
    setError(null);
    setResult(null);

    if (Platform.OS === 'web') {
      if (inIframe) {
        setError('iframe_mic_blocked');
        return;
      }
      // Web: use browser MediaRecorder
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        setPermissionGranted(true);
        webChunks = [];
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm';
        webMediaRecorder = new MediaRecorder(stream, { mimeType });
        webMediaRecorder.ondataavailable = (e: any) => {
          if (e.data.size > 0) webChunks.push(e.data);
        };
        webMediaRecorder.start(100); // collect chunks every 100ms
        setIsRecording(true);
      } catch (e: any) {
        console.error('Web mic error:', e);
        if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
          setError('Microphone access denied. Click the lock icon in your browser address bar to allow mic.');
        } else if (e.name === 'NotFoundError') {
          setError('No microphone found. Please connect a microphone.');
        } else {
          setError('Microphone error: ' + e.message);
        }
      }
    } else {
      // Native: use expo-audio
      try {
        if (!AudioModule) {
          const expoAudio = require('expo-audio');
          AudioModule = expoAudio.default || expoAudio;
          RecordingPresetsRef = expoAudio.RecordingPresets;
        }
        // Ensure permission
        if (!permissionGranted) {
          const perm = await AudioModule.requestRecordingPermissionsAsync();
          if (!perm.granted) {
            setError('Microphone permission denied. Please allow in Settings.');
            return;
          }
          setPermissionGranted(true);
        }
        // Set audio mode for recording
        await AudioModule.setAudioModeAsync({
          allowsRecording: true,
          playsInSilentMode: true,
        });
        // Create and start recorder
        const recorder = new AudioModule.AudioRecorder(
          RecordingPresetsRef?.HIGH_QUALITY || {
            extension: '.m4a',
            sampleRate: 44100,
            numberOfChannels: 1,
            bitRate: 128000,
          }
        );
        recorder.prepareToRecordAsync();
        await recorder.recordAsync();
        setNativeRecorder(recorder);
        setIsRecording(true);
      } catch (e: any) {
        console.error('Native recording error:', e);
        // Fallback: try expo-av as backup
        try {
          const { Audio } = require('expo-av');
          await Audio.setAudioModeAsync({
            allowsRecordingIOS: true,
            playsInSilentModeIOS: true,
          });
          const { recording } = await Audio.Recording.createAsync(
            Audio.RecordingOptionsPresets.HIGH_QUALITY
          );
          setNativeRecorder({ type: 'expo-av', recording });
          setIsRecording(true);
        } catch (e2: any) {
          console.error('Fallback recording error:', e2);
          setError('Recording failed: ' + e2.message);
        }
      }
    }
  }

  async function stopRecording() {
    setIsRecording(false);
    setIsProcessing(true);

    if (Platform.OS === 'web') {
      try {
        if (!webMediaRecorder) throw new Error('No active recording');
        await new Promise<void>((resolve) => {
          webMediaRecorder.onstop = () => resolve();
          webMediaRecorder.stop();
        });
        webMediaRecorder.stream.getTracks().forEach((t: any) => t.stop());
        const blob = new Blob(webChunks, { type: 'audio/webm' });
        webChunks = [];
        webMediaRecorder = null;
        if (blob.size < 100) throw new Error('Recording too short');
        await sendAudioBlob(blob);
      } catch (e: any) {
        setError('Recording failed: ' + e.message);
        setIsProcessing(false);
      }
    } else {
      try {
        if (!nativeRecorder) throw new Error('No active recording');
        if (nativeRecorder.type === 'expo-av') {
          // expo-av fallback path
          const rec = nativeRecorder.recording;
          await rec.stopAndUnloadAsync();
          const uri = rec.getURI();
          setNativeRecorder(null);
          if (!uri) throw new Error('No recording URI');
          await sendAudioNative(uri);
        } else {
          // expo-audio path
          await nativeRecorder.stop();
          const uri = nativeRecorder.uri || nativeRecorder.getURI?.();
          setNativeRecorder(null);
          if (!uri) throw new Error('No recording URI');
          await sendAudioNative(uri);
        }
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
      if (data.error) setError(data.error);
      else setResult(data);
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
      if (data.error) setError(data.error);
      else setResult(data);
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
      if (data.error) setError(data.error);
      else { setResult(data); setTextInput(''); }
    } catch (e: any) {
      setError('Network error: ' + e.message);
    } finally {
      setIsProcessing(false);
    }
  }

  function handleMicPress() {
    if (isProcessing) return;
    if (isRecording) stopRecording();
    else startRecording();
  }

  function openInNewTab() {
    if (Platform.OS === 'web') {
      window.open(window.location.href, '_blank');
    } else {
      Linking.openURL(API_URL || '');
    }
  }

  function getUrgencyColor(urgency: string) {
    switch (urgency) {
      case 'expired': case 'critical': return '#EF4444';
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

          {/* Iframe mic blocked - special message */}
          {error === 'iframe_mic_blocked' && (
            <View style={styles.iframeBox}>
              <Ionicons name="information-circle" size={24} color="#3B82F6" />
              <Text style={styles.iframeTitle}>Mic blocked in preview</Text>
              <Text style={styles.iframeText}>
                Browser security blocks microphone in embedded previews. Open this app in a new browser tab to use voice:
              </Text>
              <TouchableOpacity testID="open-new-tab-btn" style={styles.openTabBtn} onPress={openInNewTab}>
                <Ionicons name="open-outline" size={16} color="#0A0A0A" />
                <Text style={styles.openTabText}>Open in New Tab</Text>
              </TouchableOpacity>
              <TouchableOpacity testID="use-text-instead-btn" onPress={() => { setError(null); setShowTextInput(true); }} style={styles.switchBtn}>
                <Text style={styles.switchText}>or type instead</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Regular errors */}
          {error && error !== 'iframe_mic_blocked' && (
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
              <Text style={styles.listeningText}>Listening... tap mic to stop</Text>
            </View>
          )}
          {isProcessing && (
            <View style={styles.listeningBadge}>
              <ActivityIndicator size="small" color="#F5F5DC" />
              <Text style={styles.listeningText}>Processing your groceries...</Text>
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
                placeholder='e.g. "2 tomatoes and milk in fridge"'
                placeholderTextColor="#52525B"
                value={textInput}
                onChangeText={setTextInput}
                multiline
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
  // Iframe specific
  iframeBox: {
    marginHorizontal: 24, marginBottom: 16, padding: 20, width: '85%',
    backgroundColor: '#18181B', borderRadius: 16, borderWidth: 1, borderColor: '#27272A',
    alignItems: 'center', gap: 8,
  },
  iframeTitle: { color: '#F5F5DC', fontSize: 16, fontWeight: '600' },
  iframeText: { color: '#A1A1AA', fontSize: 13, textAlign: 'center', lineHeight: 18 },
  openTabBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 20, paddingVertical: 12, backgroundColor: '#F5F5DC',
    borderRadius: 12, marginTop: 8,
  },
  openTabText: { color: '#0A0A0A', fontSize: 14, fontWeight: '600' },
  // Error
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
