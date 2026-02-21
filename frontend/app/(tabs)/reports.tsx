import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, SafeAreaView, ScrollView,
  RefreshControl, ActivityIndicator,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type ReportData = {
  overall: {
    saved_weight_kg: number;
    wasted_weight_kg: number;
    money_saved_inr: number;
    co2_saved_kg: number;
    waste_ratio: number;
    most_wasted_category: string;
    total_items_tracked: number;
  };
  streaks: {
    current_streak_days: number;
    longest_streak_days: number;
  };
  weekly: {
    items_saved: number;
    items_wasted: number;
    saved_weight_kg: number;
    money_saved_inr: number;
    co2_saved_kg: number;
  };
  monthly: {
    items_saved: number;
    items_wasted: number;
    saved_weight_kg: number;
    money_saved_inr: number;
    co2_saved_kg: number;
  };
};

export default function ReportsScreen() {
  const [data, setData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);

  useFocusEffect(
    useCallback(() => {
      fetchReports();
    }, [])
  );

  async function fetchReports() {
    try {
      const res = await fetch(`${API_URL}/api/reports`);
      const report = await res.json();
      setData(report);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color="#F5F5DC" />
        </View>
      </SafeAreaView>
    );
  }

  const report = data;

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={false} onRefresh={fetchReports} tintColor="#F5F5DC" />
        }
      >
        <View style={styles.header}>
          <Text style={styles.title}>Impact</Text>
          <Text style={styles.subtitle}>Your food waste reduction journey</Text>
        </View>

        {!report || report.overall.total_items_tracked === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="analytics-outline" size={48} color="#27272A" />
            <Text style={styles.emptyTitle}>No data yet</Text>
            <Text style={styles.emptyText}>
              Start logging food and marking items as used or wasted to see your impact
            </Text>
          </View>
        ) : (
          <>
            {/* Streak Banner */}
            <View style={styles.streakBanner}>
              <View style={styles.streakIconWrap}>
                <Ionicons name="flame" size={28} color="#F59E0B" />
              </View>
              <View style={styles.streakContent}>
                <Text style={styles.streakDays}>{report.streaks.current_streak_days}</Text>
                <Text style={styles.streakLabel}>day streak without waste</Text>
              </View>
              <View style={styles.streakBest}>
                <Text style={styles.bestLabel}>Best</Text>
                <Text style={styles.bestValue}>{report.streaks.longest_streak_days}d</Text>
              </View>
            </View>

            {/* Overall Impact Cards */}
            <Text style={styles.sectionTitle}>Overall Impact</Text>
            <View style={styles.cardGrid}>
              <MetricCard
                icon="leaf" iconColor="#10B981"
                value={`${report.overall.saved_weight_kg} kg`}
                label="Food Saved"
              />
              <MetricCard
                icon="cash-outline" iconColor="#F5F5DC"
                value={`₹${report.overall.money_saved_inr}`}
                label="Money Saved"
              />
              <MetricCard
                icon="earth" iconColor="#3B82F6"
                value={`${report.overall.co2_saved_kg} kg`}
                label="CO₂ Avoided"
              />
              <MetricCard
                icon="trending-down" iconColor="#EF4444"
                value={`${report.overall.wasted_weight_kg} kg`}
                label="Food Wasted"
              />
            </View>

            {report.overall.waste_ratio > 0 && (
              <View style={styles.wasteRatioCard}>
                <View style={styles.ratioHeader}>
                  <Text style={styles.ratioLabel}>Waste Ratio</Text>
                  <Text style={styles.ratioValue}>{(report.overall.waste_ratio * 100).toFixed(0)}%</Text>
                </View>
                <View style={styles.ratioBar}>
                  <View style={[styles.ratioFill, { width: `${Math.min(report.overall.waste_ratio * 100, 100)}%` }]} />
                </View>
                {report.overall.most_wasted_category ? (
                  <Text style={styles.ratioHint}>
                    Most wasted: {report.overall.most_wasted_category}
                  </Text>
                ) : null}
              </View>
            )}

            {/* Weekly Summary */}
            <Text style={styles.sectionTitle}>This Week</Text>
            <View style={styles.summaryCard}>
              <SummaryRow icon="checkmark-circle" color="#10B981" label="Items Saved" value={String(report.weekly.items_saved)} />
              <SummaryRow icon="close-circle" color="#EF4444" label="Items Wasted" value={String(report.weekly.items_wasted)} />
              <SummaryRow icon="scale-outline" color="#F5F5DC" label="Weight Saved" value={`${report.weekly.saved_weight_kg} kg`} />
              <SummaryRow icon="cash-outline" color="#F5F5DC" label="Money Saved" value={`₹${report.weekly.money_saved_inr}`} />
              <SummaryRow icon="earth" color="#3B82F6" label="CO₂ Avoided" value={`${report.weekly.co2_saved_kg} kg`} />
            </View>

            {/* Monthly Summary */}
            <Text style={styles.sectionTitle}>This Month</Text>
            <View style={styles.summaryCard}>
              <SummaryRow icon="checkmark-circle" color="#10B981" label="Items Saved" value={String(report.monthly.items_saved)} />
              <SummaryRow icon="close-circle" color="#EF4444" label="Items Wasted" value={String(report.monthly.items_wasted)} />
              <SummaryRow icon="scale-outline" color="#F5F5DC" label="Weight Saved" value={`${report.monthly.saved_weight_kg} kg`} />
              <SummaryRow icon="cash-outline" color="#F5F5DC" label="Money Saved" value={`₹${report.monthly.money_saved_inr}`} />
              <SummaryRow icon="earth" color="#3B82F6" label="CO₂ Avoided" value={`${report.monthly.co2_saved_kg} kg`} />
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function MetricCard({ icon, iconColor, value, label }: { icon: string; iconColor: string; value: string; label: string }) {
  return (
    <View style={styles.metricCard} testID={`metric-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <Ionicons name={icon as any} size={20} color={iconColor} />
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

function SummaryRow({ icon, color, label, value }: { icon: string; color: string; label: string; value: string }) {
  return (
    <View style={styles.summaryRow}>
      <View style={styles.summaryLeft}>
        <Ionicons name={icon as any} size={16} color={color} />
        <Text style={styles.summaryLabel}>{label}</Text>
      </View>
      <Text style={styles.summaryValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  loadingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 24, paddingBottom: 100 },
  header: { paddingTop: 16, paddingBottom: 8 },
  title: { fontSize: 28, fontWeight: '700', color: '#F5F5DC', letterSpacing: -0.5 },
  subtitle: { fontSize: 13, color: '#52525B', marginTop: 2, fontWeight: '500' },
  emptyState: { alignItems: 'center', justifyContent: 'center', paddingTop: 80, gap: 8 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: '#27272A' },
  emptyText: { fontSize: 14, color: '#52525B', textAlign: 'center', lineHeight: 20 },
  streakBanner: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#18181B',
    borderRadius: 16, padding: 16, marginTop: 20, gap: 12,
  },
  streakIconWrap: {
    width: 48, height: 48, borderRadius: 24, backgroundColor: 'rgba(245,158,11,0.1)',
    alignItems: 'center', justifyContent: 'center',
  },
  streakContent: { flex: 1 },
  streakDays: { fontSize: 28, fontWeight: '700', color: '#F5F5DC' },
  streakLabel: { fontSize: 13, color: '#52525B', fontWeight: '500' },
  streakBest: { alignItems: 'center' },
  bestLabel: { fontSize: 11, color: '#52525B', fontWeight: '500' },
  bestValue: { fontSize: 16, fontWeight: '700', color: '#A1A1AA' },
  sectionTitle: {
    fontSize: 16, fontWeight: '600', color: '#A1A1AA', marginTop: 24, marginBottom: 12,
  },
  cardGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  metricCard: {
    width: '48%', backgroundColor: '#18181B', borderRadius: 14, padding: 16, gap: 6,
  },
  metricValue: { fontSize: 22, fontWeight: '700', color: '#F5F5DC' },
  metricLabel: { fontSize: 12, color: '#52525B', fontWeight: '500' },
  wasteRatioCard: {
    backgroundColor: '#18181B', borderRadius: 14, padding: 16, marginTop: 12,
  },
  ratioHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10,
  },
  ratioLabel: { fontSize: 14, color: '#A1A1AA', fontWeight: '500' },
  ratioValue: { fontSize: 18, fontWeight: '700', color: '#EF4444' },
  ratioBar: {
    height: 6, backgroundColor: '#27272A', borderRadius: 3, overflow: 'hidden',
  },
  ratioFill: { height: 6, backgroundColor: '#EF4444', borderRadius: 3 },
  ratioHint: { fontSize: 12, color: '#52525B', marginTop: 8, textTransform: 'capitalize' },
  summaryCard: { backgroundColor: '#18181B', borderRadius: 14, padding: 4 },
  summaryRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 12, paddingHorizontal: 12,
    borderBottomWidth: 1, borderBottomColor: '#27272A',
  },
  summaryLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  summaryLabel: { fontSize: 14, color: '#A1A1AA', fontWeight: '500' },
  summaryValue: { fontSize: 14, fontWeight: '600', color: '#F5F5DC' },
});
