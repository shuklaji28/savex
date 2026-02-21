import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, SafeAreaView, ScrollView,
  TouchableOpacity, RefreshControl, Modal, Alert, Platform,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type FoodItem = {
  id: string;
  item_name: string;
  normalized_name: string;
  quantity: number;
  unit: string;
  storage_location: string;
  category: string;
  added_date: string;
  expiry_date: string;
  status: string;
  estimated_weight_grams: number;
  estimated_cost_inr: number;
  days_remaining: number;
  urgency_level: string;
};

type GroupedItems = {
  title: string;
  items: FoodItem[];
  color: string;
};

export default function InventoryScreen() {
  const router = useRouter();
  const [items, setItems] = useState<FoodItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<FoodItem | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useFocusEffect(
    useCallback(() => {
      fetchInventory();
    }, [])
  );

  async function fetchInventory() {
    try {
      const res = await fetch(`${API_URL}/api/inventory`);
      const data = await res.json();
      setItems(data.items || []);
    } catch (e) {
      console.error('Fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function markItem(itemId: string, status: 'used' | 'wasted') {
    try {
      await fetch(`${API_URL}/api/inventory/${itemId}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      setSelectedItem(null);
      fetchInventory();
    } catch (e) {
      console.error('Mark error:', e);
    }
  }

  function getGroupedItems(): GroupedItems[] {
    const groups: GroupedItems[] = [
      { title: 'Expired', items: [], color: '#EF4444' },
      { title: 'Expiring Today', items: [], color: '#EF4444' },
      { title: 'Expiring in 1-2 Days', items: [], color: '#F59E0B' },
      { title: 'Expiring This Week', items: [], color: '#3B82F6' },
      { title: 'Fresh Items', items: [], color: '#10B981' },
    ];
    items.forEach(item => {
      if (item.days_remaining <= 0) groups[0].items.push(item);
      else if (item.days_remaining === 1) groups[1].items.push(item);
      else if (item.days_remaining <= 3) groups[2].items.push(item);
      else if (item.days_remaining <= 7) groups[3].items.push(item);
      else groups[4].items.push(item);
    });
    return groups.filter(g => g.items.length > 0);
  }

  function getStorageIcon(loc: string) {
    switch (loc) {
      case 'fridge': return 'snow-outline';
      case 'freezer': return 'cube-outline';
      case 'kitchen_counter': return 'cafe-outline';
      case 'pantry_shelf': return 'file-tray-stacked-outline';
      default: return 'location-outline';
    }
  }

  function formatTimeRemaining(days: number) {
    if (days <= 0) return 'Expired';
    if (days === 1) return 'Expires today';
    if (days === 2) return 'Expires tomorrow';
    return `${days - 1} days left`;
  }

  const grouped = getGroupedItems();

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Inventory</Text>
          <Text style={styles.count}>{items.length} active items</Text>
        </View>
        <TouchableOpacity
          testID="view-history-btn"
          style={styles.historyBtn}
          onPress={() => router.push('/history')}
        >
          <Ionicons name="time-outline" size={18} color="#A1A1AA" />
          <Text style={styles.historyText}>History</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); fetchInventory(); }}
            tintColor="#F5F5DC"
          />
        }
      >
        {loading ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>Loading...</Text>
          </View>
        ) : items.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="leaf-outline" size={48} color="#27272A" />
            <Text style={styles.emptyTitle}>No items yet</Text>
            <Text style={styles.emptyText}>Use voice to add groceries</Text>
          </View>
        ) : (
          grouped.map((group) => (
            <View key={group.title} style={styles.section}>
              <View style={styles.sectionHeader}>
                <View style={[styles.sectionDot, { backgroundColor: group.color }]} />
                <Text style={[styles.sectionTitle, { color: group.color }]}>{group.title}</Text>
                <Text style={styles.sectionCount}>{group.items.length}</Text>
              </View>
              {group.items.map((item) => (
                <TouchableOpacity
                  key={item.id}
                  testID={`item-card-${item.id}`}
                  style={styles.itemCard}
                  onPress={() => setSelectedItem(item)}
                  activeOpacity={0.7}
                >
                  <View style={styles.itemLeft}>
                    <Text style={styles.itemName}>{item.normalized_name}</Text>
                    <View style={styles.itemMeta}>
                      <Ionicons name={getStorageIcon(item.storage_location) as any} size={12} color="#52525B" />
                      <Text style={styles.metaText}>{item.storage_location.replace('_', ' ')}</Text>
                      <Text style={styles.metaDot}>·</Text>
                      <Text style={styles.metaText}>{item.quantity} {item.unit}</Text>
                    </View>
                  </View>
                  <View style={styles.itemRight}>
                    <Text style={[styles.timeLeft, { color: group.color }]}>
                      {formatTimeRemaining(item.days_remaining)}
                    </Text>
                    <Ionicons name="chevron-forward" size={16} color="#27272A" />
                  </View>
                </TouchableOpacity>
              ))}
            </View>
          ))
        )}
      </ScrollView>

      <Modal
        visible={selectedItem !== null}
        transparent
        animationType="slide"
        onRequestClose={() => setSelectedItem(null)}
      >
        {selectedItem && (
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHandle} />
              <Text style={styles.modalTitle}>{selectedItem.normalized_name}</Text>
              <View style={styles.modalDetails}>
                <DetailRow label="Quantity" value={`${selectedItem.quantity} ${selectedItem.unit}`} />
                <DetailRow label="Storage" value={selectedItem.storage_location.replace('_', ' ')} />
                <DetailRow label="Added" value={selectedItem.added_date} />
                <DetailRow label="Expires" value={selectedItem.expiry_date} />
                <DetailRow label="Category" value={selectedItem.category} />
                <DetailRow label="Est. Weight" value={`${selectedItem.estimated_weight_grams}g`} />
                <DetailRow label="Est. Cost" value={`₹${selectedItem.estimated_cost_inr}`} />
              </View>
              <View style={styles.modalActions}>
                <TouchableOpacity
                  testID="mark-used-btn"
                  style={[styles.actionBtn, styles.usedBtn]}
                  onPress={() => markItem(selectedItem.id, 'used')}
                >
                  <Ionicons name="checkmark-circle" size={20} color="#10B981" />
                  <Text style={[styles.actionText, { color: '#10B981' }]}>Used</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  testID="mark-wasted-btn"
                  style={[styles.actionBtn, styles.wastedBtn]}
                  onPress={() => markItem(selectedItem.id, 'wasted')}
                >
                  <Ionicons name="trash" size={20} color="#EF4444" />
                  <Text style={[styles.actionText, { color: '#EF4444' }]}>Wasted</Text>
                </TouchableOpacity>
              </View>
              <TouchableOpacity
                testID="modal-close-btn"
                style={styles.closeBtn}
                onPress={() => setSelectedItem(null)}
              >
                <Text style={styles.closeBtnText}>Close</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
      </Modal>
    </SafeAreaView>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 24, paddingTop: 16, paddingBottom: 12,
  },
  title: { fontSize: 28, fontWeight: '700', color: '#F5F5DC', letterSpacing: -0.5 },
  count: { fontSize: 13, color: '#52525B', marginTop: 2, fontWeight: '500' },
  historyBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 14, paddingVertical: 8, backgroundColor: '#18181B', borderRadius: 20,
  },
  historyText: { color: '#A1A1AA', fontSize: 13, fontWeight: '500' },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 24, paddingBottom: 100 },
  section: { marginTop: 20 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  sectionDot: { width: 8, height: 8, borderRadius: 4 },
  sectionTitle: { fontSize: 16, fontWeight: '600', flex: 1 },
  sectionCount: { fontSize: 13, color: '#52525B', fontWeight: '500' },
  itemCard: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#18181B', borderRadius: 14, padding: 16, marginBottom: 8,
  },
  itemLeft: { flex: 1 },
  itemName: { fontSize: 16, fontWeight: '600', color: '#F5F5DC', textTransform: 'capitalize' },
  itemMeta: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  metaText: { fontSize: 12, color: '#52525B', textTransform: 'capitalize' },
  metaDot: { color: '#52525B', fontSize: 12 },
  itemRight: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  timeLeft: { fontSize: 13, fontWeight: '600' },
  emptyState: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 100, gap: 8 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: '#27272A' },
  emptyText: { fontSize: 14, color: '#52525B' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' },
  modalContent: {
    backgroundColor: '#18181B', borderTopLeftRadius: 24, borderTopRightRadius: 24,
    padding: 24, paddingBottom: 40,
  },
  modalHandle: {
    width: 40, height: 4, borderRadius: 2, backgroundColor: '#27272A',
    alignSelf: 'center', marginBottom: 20,
  },
  modalTitle: {
    fontSize: 24, fontWeight: '700', color: '#F5F5DC', textTransform: 'capitalize', marginBottom: 16,
  },
  modalDetails: { gap: 2 },
  detailRow: {
    flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: '#27272A',
  },
  detailLabel: { fontSize: 14, color: '#52525B', fontWeight: '500' },
  detailValue: { fontSize: 14, color: '#F5F5DC', fontWeight: '500', textTransform: 'capitalize' },
  modalActions: {
    flexDirection: 'row', gap: 12, marginTop: 24,
  },
  actionBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, paddingVertical: 14, borderRadius: 14, borderWidth: 1,
  },
  usedBtn: { borderColor: 'rgba(16,185,129,0.3)', backgroundColor: 'rgba(16,185,129,0.08)' },
  wastedBtn: { borderColor: 'rgba(239,68,68,0.3)', backgroundColor: 'rgba(239,68,68,0.08)' },
  actionText: { fontSize: 15, fontWeight: '600' },
  closeBtn: { alignItems: 'center', paddingVertical: 14, marginTop: 12 },
  closeBtnText: { fontSize: 15, color: '#52525B', fontWeight: '500' },
});
