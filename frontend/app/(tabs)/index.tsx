import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, SafeAreaView,
  Animated, Platform, ActivityIndicator,
  KeyboardAvoidingView, Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  useAudioRecorder,
  RecordingPresets,
  AudioModule,
} from 'expo-audio';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type FoodItem = {
  id: string;
  normalized_name: string;
  quantity: number;
  unit: string;
  days_remaining: number;
  urgency_level: string;
};

type UpdatedItem = {
  id: string;
  normalized_name: string;
  status: string;
};

type ProcessResult = {
  transcript: string;
  items: FoodItem[];
  updated_items?: UpdatedItem[];
  not_found?: { name: string; intent: string }[];
  warnings?: { name: string; existing_batches: number; new_batch: number; oldest_added: string }[];
  count: number;
  error?: string;
};

// Web-only: browser MediaRecorder
let webMediaRecorder: any = null;
let webChunks: any[] = [];

function isInIframe(): boolean {
  if (Platform.OS !== 'web') return false;
  try {
    return window.self !== window.top;
  } catch {
    return true;
  }
}

export default function HomeScreen() {
  // expo-audio recorder hook (works on native, no-op setup on web)
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);

  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [permissionGranted, setPermissionGranted] = useState(false);
  // const [showTextInput, setShowTextInput] = useState(false); // dev-only text mode
  // const [textInput, setTextInput] = useState('');
  const [inIframe, setInIframe] = useState(false);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    initPermissions();
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
      const t = setTimeout(() => {
        Animated.timing(fadeAnim, { toValue: 0, duration: 400, useNativeDriver: true }).start(() => setResult(null));
      }, 8000);
      return () => clearTimeout(t);
    }
  }, [result]);

  async function initPermissions() {
    if (Platform.OS === 'web') {
      const iframe = isInIframe();
      setInIframe(iframe);
      if (!iframe) {
        try {
          const s = await navigator.mediaDevices.getUserMedia({ audio: true });
          s.getTracks().forEach(t => t.stop());
          setPermissionGranted(true);
        } catch {
          // Will request on first mic tap
        }
      }
    } else {
      // Native: request via expo-audio
      try {
        const perm = await AudioModule.requestRecordingPermissionsAsync();
        setPermissionGranted(perm.granted);
      } catch (e) {
        console.log('Permission check failed:', e);
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
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        setPermissionGranted(true);
        webChunks = [];
        const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus' : 'audio/webm';
        webMediaRecorder = new MediaRecorder(stream, { mimeType: mime });
        webMediaRecorder.ondataavailable = (e: any) => {
          if (e.data.size > 0) webChunks.push(e.data);
        };
        webMediaRecorder.start(100);
        setIsRecording(true);
      } catch (e: any) {
        if (e.name === 'NotAllowedError') {
          setError('Microphone access denied. Click the lock icon in your address bar to allow.');
        } else if (e.name === 'NotFoundError') {
          setError('No microphone found. Please connect a microphone.');
        } else {
          setError('Mic error: ' + e.message);
        }
      }
    } else {
      // Native: use expo-audio recorder
      try {
        if (!permissionGranted) {
          const perm = await AudioModule.requestRecordingPermissionsAsync();
          if (!perm.granted) {
            setError('Microphone permission denied. Please allow in Settings.');
            return;
          }
          setPermissionGranted(true);
        }
        await AudioModule.setAudioModeAsync({
          allowsRecording: true,
          playsInSilentMode: true,
        });
        await recorder.prepareToRecordAsync();
        recorder.record();
        setIsRecording(true);
      } catch (e: any) {
        console.error('Native record error:', e);
        setError('Recording failed: ' + e.message);
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
        await sendBlob(blob);
      } catch (e: any) {
        setError('Recording error: ' + e.message);
        setIsProcessing(false);
      }
    } else {
      // Native: stop expo-audio recorder
      try {
        await recorder.stop();
        const uri = recorder.uri;
        if (!uri) throw new Error('No recording URI');
        await sendNativeAudio(uri);
      } catch (e: any) {
        setError('Processing error: ' + e.message);
        setIsProcessing(false);
      }
    }
  }

  async function sendBlob(blob: Blob) {
    try {
      const fd = new FormData();
      fd.append('audio', blob, 'recording.webm');
      const res = await fetch(`${API_URL}/api/process-voice`, { method: 'POST', body: fd });
      const data: ProcessResult = await res.json();
      data.error ? setError(data.error) : setResult(data);
    } catch (e: any) {
      setError('Network error: ' + e.message);
    } finally {
      setIsProcessing(false);
    }
  }

  async function sendNativeAudio(uri: string) {
    try {
      const fd = new FormData();
      fd.append('audio', { uri, name: 'recording.m4a', type: 'audio/m4a' } as any);
      const res = await fetch(`${API_URL}/api/process-voice`, { method: 'POST', body: fd });
      const data: ProcessResult = await res.json();
      data.error ? setError(data.error) : setResult(data);
    } catch (e: any) {
      setError('Network error: ' + e.message);
    } finally {
      setIsProcessing(false);
    }
  }

  // DEV ONLY: sendText function for text input mode — commented out
  /* async function sendText() {
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
      data.error ? setError(data.error) : (setResult(data), setTextInput(''));
    } catch (e: any) {
      setError('Network error: ' + e.message);
    } finally {
      setIsProcessing(false);
    }
  } */

  function handleMicPress() {
    if (isProcessing) return;
    isRecording ? stopRecording() : startRecording();
  }

  function openInNewTab() {
    if (Platform.OS === 'web') {
      window.open(window.location.href, '_blank');
    }
  }

  function urgencyColor(u: string) {
    if (u === 'expired' || u === 'critical') return '#EF4444';
    if (u === 'urgent') return '#F59E0B';
    if (u === 'upcoming') return '#3B82F6';
    return '#10B981';
  }

  const hasResult = result && result.count > 0;
  const addedItems = result?.items || [];
  const updatedItems = result?.updated_items || [];
  const notFoundItems = result?.not_found || [];
  const warningItems = result?.warnings || [];

  return (
    <SafeAreaView style={s.container}>
      <KeyboardAvoidingView style={s.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <View style={s.header}>
          <Text style={s.title}>savex</Text>
          <Text style={s.subtitle}>speak to log expiry and items</Text>
        </View>

        <View style={s.center}>
          {hasResult && (
            <Animated.View style={[s.resultBox, { opacity: fadeAnim }]}>
              {result!.transcript ? <Text style={s.transcript}>"{result!.transcript}"</Text> : null}

              {warningItems.length > 0 && (
                <View style={s.warningBox}>
                  <Text style={s.warningTitle}>⚠️ Already in inventory</Text>
                  {warningItems.map((w, i) => (
                    <Text key={i} style={s.warningText}>
                      · {w.name} — added as batch #{w.new_batch} (you had {w.existing_batches} batch{w.existing_batches !== 1 ? 'es' : ''} already)
                    </Text>
                  ))}
                  <Text style={s.warningSubtext}>WhatsApp nudge sent to check before buying more</Text>
                </View>
              )}

              {addedItems.length > 0 && (
                <>
                  <Text style={s.resultTitle}>+ Added {addedItems.length} item{addedItems.length !== 1 ? 's' : ''}</Text>
                  {addedItems.map((item, i) => (
                    <View key={item.id || String(i)} style={s.resultItem}>
                      <View style={[s.urgencyDot, { backgroundColor: urgencyColor(item.urgency_level) }]} />
                      <Text style={s.resultItemName}>{item.normalized_name}</Text>
                      <Text style={s.resultItemMeta}>{item.quantity} {item.unit} · {item.days_remaining}d left</Text>
                    </View>
                  ))}
                </>
              )}

              {updatedItems.length > 0 && (
                <>
                  <Text style={[s.resultTitle, s.updatedTitle]}>
                    {addedItems.length > 0 ? '\n' : ''}✓ Updated {updatedItems.length} item{updatedItems.length !== 1 ? 's' : ''}
                  </Text>
                  {updatedItems.map((item, i) => (
                    <View key={item.id || String(i)} style={s.resultItem}>
                      <View style={[s.urgencyDot, { backgroundColor: item.status === 'used' ? '#10B981' : '#EF4444' }]} />
                      <Text style={s.resultItemName}>{item.normalized_name}</Text>
                      <Text style={[s.resultItemMeta, { color: item.status === 'used' ? '#10B981' : '#EF4444' }]}>
                        marked {item.status}
                      </Text>
                    </View>
                  ))}
                </>
              )}

              {notFoundItems.length > 0 && (
                <>
                  <Text style={[s.resultTitle, { color: '#F59E0B', marginTop: 8, fontSize: 13 }]}>
                    Not found in inventory:
                  </Text>
                  {notFoundItems.map((nf, i) => (
                    <Text key={i} style={[s.resultItemMeta, { color: '#F59E0B', paddingLeft: 14 }]}>
                      · {nf.name}
                    </Text>
                  ))}
                </>
              )}
            </Animated.View>
          )}

          {error === 'iframe_mic_blocked' && (
            <View style={s.iframeBox}>
              <Ionicons name="information-circle" size={24} color="#3B82F6" />
              <Text style={s.iframeTitle}>Mic blocked in preview</Text>
              <Text style={s.iframeText}>Browser security blocks microphone in embedded previews. Open in a new tab to use voice input:</Text>
              <TouchableOpacity testID="open-new-tab-btn" style={s.openTabBtn} onPress={openInNewTab}>
                <Ionicons name="open-outline" size={16} color="#0A0A0A" />
                <Text style={s.openTabText}>Open in New Tab</Text>
              </TouchableOpacity>
          {/* DEV ONLY: text input mode — commented out for production
          <TouchableOpacity testID="use-text-instead-btn" onPress={() => { setError(null); }} style={s.switchBtn}>
            <Text style={s.switchText}>or type instead</Text>
          </TouchableOpacity>
          */}

            </View>
          )}

          {error && error !== 'iframe_mic_blocked' && (
            <View style={s.errorBox}>
              <Text style={s.errorText}>{error}</Text>
              <TouchableOpacity testID="dismiss-error-btn" onPress={() => setError(null)} style={s.dismissBtn}>
                <Text style={s.dismissText}>Dismiss</Text>
              </TouchableOpacity>
            </View>
          )}

          {isRecording && (
            <View style={s.listeningBadge}>
              <View style={s.redDot} />
              <Text style={s.listeningText}>Listening... tap mic to stop</Text>
            </View>
          )}
          {isProcessing && (
            <View style={s.listeningBadge}>
              <ActivityIndicator size="small" color="#F5F5DC" />
              <Text style={s.listeningText}>Processing your groceries...</Text>
            </View>
          )}

          {/* Always show mic — text input mode commented out (dev only) */}
          <>
            <Animated.View style={[s.micOuter, { transform: [{ scale: pulseAnim }] }]}>
              <TouchableOpacity
                testID="mic-button"
                style={[s.micButton, isRecording && s.micRecording, isProcessing && s.micProcessing]}
                onPress={handleMicPress}
                activeOpacity={0.7}
                disabled={isProcessing}
              >
                <Ionicons name={isRecording ? 'stop' : 'mic'} size={40} color={isRecording ? '#EF4444' : '#0A0A0A'} />
              </TouchableOpacity>
            </Animated.View>
            {!isRecording && !isProcessing && !hasResult && !error && (
              <Text style={s.hint}>Tap to start recording</Text>
            )}
          </>

          {/* DEV ONLY: text input toggle — commented out
          <TouchableOpacity testID="switch-to-text-btn" onPress={() => setShowTextInput(true)} style={s.switchBtn}>
            <Ionicons name="create-outline" size={16} color="#52525B" />
            <Text style={s.switchText}>or type instead</Text>
          </TouchableOpacity>

          <View style={s.textInputWrap}>
            <TextInput
              testID="text-input"
              style={s.textInput}
              placeholder='e.g. "2 tomatoes and milk in fridge"'
              placeholderTextColor="#52525B"
              value={textInput}
              onChangeText={setTextInput}
              multiline
            />
            <View style={s.textActions}>
              <TouchableOpacity
                testID="send-text-btn"
                style={[s.sendBtn, !textInput.trim() && s.sendBtnDisabled]}
                onPress={sendText}
                disabled={!textInput.trim() || isProcessing}
              >
                <Ionicons name="arrow-up" size={20} color={textInput.trim() ? '#0A0A0A' : '#52525B'} />
              </TouchableOpacity>
            </View>
            <TouchableOpacity testID="switch-to-voice-btn" onPress={() => setShowTextInput(false)} style={s.switchBtn}>
              <Ionicons name="mic-outline" size={16} color="#52525B" />
              <Text style={s.switchText}>use voice instead</Text>
            </TouchableOpacity>
          </View>
          */}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
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
  updatedTitle: { color: '#A1A1AA' },
  transcript: { color: '#52525B', fontSize: 13, fontStyle: 'italic', marginBottom: 12 },
  resultItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, gap: 8 },
  urgencyDot: { width: 6, height: 6, borderRadius: 3 },
  resultItemName: { color: '#F5F5DC', fontSize: 15, fontWeight: '500', flex: 1 },
  resultItemMeta: { color: '#A1A1AA', fontSize: 13 },
});
