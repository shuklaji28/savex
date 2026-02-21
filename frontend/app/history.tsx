import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, SafeAreaView, ScrollView,
  RefreshControl, ActivityIndicator, TouchableOpacity,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type HistoryItem = {
  id: string;
  normalized_name: string;
  quantity: number;
  unit: string;
  status: string;
  action_date: string;
  added_date: string;
  expiry_date: string;
  category: string;
  estimated_cost_inr: number;
};

export default function HistoryScreen() {
  const router = useRouter();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory();
  }, []);

  async function fetchHistory() {
    try {
      const res = await fetch(`${API_URL}/api/inventory/history`);
      const data = await res.json();
      setItems(data.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Custom header with back button */}
      <View style={styles.header}>
        <TouchableOpacity
          testID="history-back-btn"
          style={styles.backBtn}
          onPress={() => router.back()}
        >
          <Ionicons name="arrow-back" size={24} color="#F5F5DC" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Past Items</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={false} onRefresh={() => { setLoading(true); fetchHistory(); }} tintColor="#F5F5DC" />
        }
      >
        {loading ? (
          <View style={styles.centerState}>
            <ActivityIndicator size="large" color="#F5F5DC" />
          </View>
        ) : items.length === 0 ? (
          <View style={styles.centerState}>
            <Ionicons name="archive-outline" size={48} color="#27272A" />
            <Text style={styles.emptyTitle}>No history yet</Text>
            <Text style={styles.emptyText}>Items marked as used or wasted will appear here</Text>
          </View>
        ) : (
          items.map((item) => (
            <View key={item.id} style={styles.itemCard} testID={`history-item-${item.id}`}>
              <View style={styles.statusBadge}>
                <Ionicons
                  name={item.status === 'used' ? 'checkmark-circle' : 'close-circle'}
                  size={16}
                  color={item.status === 'used' ? '#10B981' : '#EF4444'}
                />
                <Text style={[styles.statusText, { color: item.status === 'used' ? '#10B981' : '#EF4444' }]}>
                  {item.status}
                </Text>
              </View>
              <Text style={styles.itemName}>{item.normalized_name}</Text>
              <View style={styles.itemMeta}>
                <Text style={styles.metaText}>{item.quantity} {item.unit}</Text>
                <Text style={styles.metaDot}>·</Text>
                <Text style={styles.metaText}>₹{item.estimated_cost_inr}</Text>
                <Text style={styles.metaDot}>·</Text>
                <Text style={styles.metaText}>{item.action_date}</Text>
              </View>
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#18181B',
    borderBottomWidth: 1, borderBottomColor: '#27272A',
  },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '600', color: '#F5F5DC' },
  scroll: { flex: 1 },
  scrollContent: { padding: 24, paddingBottom: 100 },
  centerState: { alignItems: 'center', justifyContent: 'center', paddingTop: 80, gap: 8 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: '#27272A' },
  emptyText: { fontSize: 14, color: '#52525B', textAlign: 'center' },
  itemCard: {
    backgroundColor: '#18181B', borderRadius: 14, padding: 16, marginBottom: 8,
  },
  statusBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 4 },
  statusText: { fontSize: 12, fontWeight: '600', textTransform: 'uppercase' },
  itemName: { fontSize: 16, fontWeight: '600', color: '#F5F5DC', textTransform: 'capitalize' },
  itemMeta: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  metaText: { fontSize: 12, color: '#52525B' },
  metaDot: { color: '#52525B', fontSize: 12 },
});
