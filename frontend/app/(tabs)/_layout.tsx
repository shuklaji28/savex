import { Tabs } from 'expo-router';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

type TabIconProps = {
  name: keyof typeof Ionicons.glyphMap;
  color: string;
  size: number;
  focused: boolean;
  label: string;
};

function TabIcon({ name, color, size, focused, label }: TabIconProps) {
  return (
    <View style={tabStyles.iconWrap}>
      <Ionicons name={name} size={size} color={color} />
      <Text style={[tabStyles.label, { color }]}>{label}</Text>
    </View>
  );
}

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: tabStyles.bar,
        tabBarActiveTintColor: '#F5F5DC',
        tabBarInactiveTintColor: '#52525B',
        tabBarShowLabel: false,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size, focused }) => (
            <View style={[tabStyles.micWrap, focused && tabStyles.micActive]}>
              <Ionicons name="mic" size={28} color={focused ? '#0A0A0A' : '#F5F5DC'} />
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="inventory"
        options={{
          title: 'Inventory',
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="list-outline" color={color} size={22} focused={focused} label="Items" />
          ),
        }}
      />
      <Tabs.Screen
        name="cook"
        options={{
          title: 'Cook',
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="restaurant-outline" color={color} size={22} focused={focused} label="Cook" />
          ),
        }}
      />
      <Tabs.Screen
        name="reports"
        options={{
          title: 'Reports',
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="stats-chart-outline" color={color} size={22} focused={focused} label="Impact" />
          ),
        }}
      />
    </Tabs>
  );
}

const tabStyles = StyleSheet.create({
  bar: {
    backgroundColor: '#18181B',
    borderTopWidth: 0,
    height: 70,
    paddingBottom: 8,
    paddingTop: 8,
    elevation: 0,
    shadowOpacity: 0,
  },
  iconWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 2,
  },
  label: {
    fontSize: 10,
    fontWeight: '500',
    marginTop: 2,
  },
  micWrap: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#27272A',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  micActive: {
    backgroundColor: '#F5F5DC',
  },
});
