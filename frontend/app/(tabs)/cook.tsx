import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, SafeAreaView, ScrollView,
  TouchableOpacity, ActivityIndicator, RefreshControl,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type Recipe = {
  title: string;
  type: string;
  prep_time_minutes: number;
  expiring_items_used: string[];
  other_ingredients: string[];
  steps: string[];
  tip?: string;
};

type ExpiringItem = {
  name: string;
  quantity: number;
  unit: string;
  days_remaining: number;
  urgency: string;
};

export default function CookScreen() {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [expiringItems, setExpiringItems] = useState<ExpiringItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      fetchRecipes();
    }, [])
  );

  async function fetchRecipes() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/recipes`);
      const data = await res.json();
      setRecipes(data.recipes || []);
      setExpiringItems(data.expiring_items || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function getTypeIcon(type: string) {
    switch (type) {
      case 'quick_meal': return 'flame-outline';
      case 'snack': return 'fast-food-outline';
      case 'simple_prep': return 'leaf-outline';
      default: return 'restaurant-outline';
    }
  }

  function getUrgencyColor(urgency: string) {
    switch (urgency) {
      case 'critical': return '#EF4444';
      case 'urgent': return '#F59E0B';
      case 'upcoming': return '#3B82F6';
      default: return '#10B981';
    }
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>What to Cook</Text>
        <Text style={styles.subtitle}>Use it before you lose it</Text>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={false} onRefresh={fetchRecipes} tintColor="#F5F5DC" />
        }
      >
        {loading ? (
          <View style={styles.centerState}>
            <ActivityIndicator size="large" color="#F5F5DC" />
            <Text style={styles.loadingText}>Generating recipes...</Text>
          </View>
        ) : error ? (
          <View style={styles.centerState}>
            <Ionicons name="alert-circle-outline" size={48} color="#EF4444" />
            <Text style={styles.errorText}>{error}</Text>
            <TouchableOpacity testID="retry-recipes-btn" onPress={fetchRecipes} style={styles.retryBtn}>
              <Text style={styles.retryText}>Retry</Text>
            </TouchableOpacity>
          </View>
        ) : expiringItems.length === 0 ? (
          <View style={styles.centerState}>
            <Ionicons name="happy-outline" size={48} color="#27272A" />
            <Text style={styles.emptyTitle}>All fresh!</Text>
            <Text style={styles.emptyText}>No items expiring soon</Text>
          </View>
        ) : (
          <>
            {expiringItems.length > 0 && (
              <View style={styles.expiringSection}>
                <Text style={styles.expiringTitle}>Items to use up</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  {expiringItems.map((item, i) => (
                    <View key={i} style={[styles.expiringChip, { borderColor: getUrgencyColor(item.urgency) }]}>
                      <Text style={styles.chipName}>{item.name}</Text>
                      <Text style={[styles.chipDays, { color: getUrgencyColor(item.urgency) }]}>
                        {item.days_remaining <= 0 ? 'expired' : `${item.days_remaining}d`}
                      </Text>
                    </View>
                  ))}
                </ScrollView>
              </View>
            )}

            {recipes.length === 0 ? (
              <View style={styles.centerState}>
                <Text style={styles.emptyText}>No recipes generated. Try again!</Text>
              </View>
            ) : (
              recipes.map((recipe, idx) => (
                <View key={idx} style={styles.recipeCard}>
                  <TouchableOpacity
                    testID={`recipe-card-${idx}`}
                    style={styles.recipeHeader}
                    onPress={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                    activeOpacity={0.7}
                  >
                    <View style={styles.recipeLeft}>
                      <Ionicons name={getTypeIcon(recipe.type) as any} size={20} color="#F5F5DC" />
                      <View style={styles.recipeTitleWrap}>
                        <Text style={styles.recipeTitle}>{recipe.title}</Text>
                        <View style={styles.recipeMeta}>
                          <Text style={styles.recipeType}>{recipe.type.replace('_', ' ')}</Text>
                          <Text style={styles.recipeDot}>·</Text>
                          <Text style={styles.recipeTime}>{recipe.prep_time_minutes} min</Text>
                        </View>
                      </View>
                    </View>
                    <Ionicons
                      name={expandedIdx === idx ? 'chevron-up' : 'chevron-down'}
                      size={20}
                      color="#52525B"
                    />
                  </TouchableOpacity>

                  <View style={styles.savedItems}>
                    {recipe.expiring_items_used.map((item, i) => (
                      <View key={i} style={styles.savedChip}>
                        <Ionicons name="leaf" size={10} color="#10B981" />
                        <Text style={styles.savedText}>{item}</Text>
                      </View>
                    ))}
                  </View>

                  {expandedIdx === idx && (
                    <View style={styles.recipeBody}>
                      {recipe.other_ingredients.length > 0 && (
                        <View style={styles.ingredientSection}>
                          <Text style={styles.sectionLabel}>Also needed</Text>
                          <Text style={styles.ingredientList}>
                            {recipe.other_ingredients.join(', ')}
                          </Text>
                        </View>
                      )}
                      <View style={styles.stepsSection}>
                        <Text style={styles.sectionLabel}>Steps</Text>
                        {recipe.steps.map((step, i) => (
                          <View key={i} style={styles.stepRow}>
                            <Text style={styles.stepNum}>{i + 1}</Text>
                            <Text style={styles.stepText}>{step}</Text>
                          </View>
                        ))}
                      </View>
                      {recipe.tip && (
                        <View style={styles.tipBox}>
                          <Ionicons name="bulb-outline" size={14} color="#F59E0B" />
                          <Text style={styles.tipText}>{recipe.tip}</Text>
                        </View>
                      )}
                    </View>
                  )}
                </View>
              ))
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  header: { paddingHorizontal: 24, paddingTop: 16, paddingBottom: 8 },
  title: { fontSize: 28, fontWeight: '700', color: '#F5F5DC', letterSpacing: -0.5 },
  subtitle: { fontSize: 13, color: '#52525B', marginTop: 2, fontWeight: '500' },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 24, paddingBottom: 100 },
  centerState: { alignItems: 'center', justifyContent: 'center', paddingTop: 80, gap: 12 },
  loadingText: { color: '#A1A1AA', fontSize: 14, marginTop: 8 },
  errorText: { color: '#EF4444', fontSize: 14, textAlign: 'center' },
  retryBtn: {
    paddingHorizontal: 20, paddingVertical: 10, backgroundColor: '#18181B', borderRadius: 12,
  },
  retryText: { color: '#F5F5DC', fontSize: 14, fontWeight: '500' },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: '#27272A' },
  emptyText: { fontSize: 14, color: '#52525B' },
  expiringSection: { marginTop: 16, marginBottom: 8 },
  expiringTitle: { fontSize: 14, fontWeight: '600', color: '#A1A1AA', marginBottom: 10 },
  expiringChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16,
    borderWidth: 1, marginRight: 8, backgroundColor: '#18181B',
  },
  chipName: { fontSize: 13, color: '#F5F5DC', fontWeight: '500', textTransform: 'capitalize' },
  chipDays: { fontSize: 12, fontWeight: '600' },
  recipeCard: { backgroundColor: '#18181B', borderRadius: 16, marginTop: 12, overflow: 'hidden' },
  recipeHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: 16,
  },
  recipeLeft: { flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 },
  recipeTitleWrap: { flex: 1 },
  recipeTitle: { fontSize: 16, fontWeight: '600', color: '#F5F5DC' },
  recipeMeta: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 },
  recipeType: { fontSize: 12, color: '#52525B', textTransform: 'capitalize' },
  recipeDot: { color: '#52525B', fontSize: 12 },
  recipeTime: { fontSize: 12, color: '#52525B' },
  savedItems: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 6,
    paddingHorizontal: 16, paddingBottom: 12,
  },
  savedChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8,
    backgroundColor: 'rgba(16,185,129,0.1)',
  },
  savedText: { fontSize: 12, color: '#10B981', fontWeight: '500', textTransform: 'capitalize' },
  recipeBody: { paddingHorizontal: 16, paddingBottom: 16, gap: 16 },
  ingredientSection: {},
  sectionLabel: { fontSize: 13, fontWeight: '600', color: '#A1A1AA', marginBottom: 6 },
  ingredientList: { fontSize: 14, color: '#F5F5DC', lineHeight: 20 },
  stepsSection: {},
  stepRow: { flexDirection: 'row', gap: 10, marginBottom: 8 },
  stepNum: {
    width: 20, height: 20, borderRadius: 10, backgroundColor: '#27272A',
    textAlign: 'center', lineHeight: 20, fontSize: 11, color: '#A1A1AA', fontWeight: '600',
  },
  stepText: { fontSize: 14, color: '#F5F5DC', flex: 1, lineHeight: 20 },
  tipBox: {
    flexDirection: 'row', gap: 8, padding: 12, backgroundColor: 'rgba(245,158,11,0.08)',
    borderRadius: 10, alignItems: 'flex-start',
  },
  tipText: { fontSize: 13, color: '#F59E0B', flex: 1, lineHeight: 18 },
});
