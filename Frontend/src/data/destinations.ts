import type { Destination } from '../types';

export const destinations: Destination[] = [
  {
    id: 'rajasthan',
    name: 'Rajasthan',
    image: 'https://images.unsplash.com/photo-1539650116574-75c0c6d73f6e?auto=format&fit=crop&w=900&q=80',
    description: 'Unlock desert adventures, royal forts and vibrant culture.',
    accent: 'from-orange-200 via-amber-100 to-rose-100',
    cities: ['Jaipur', 'Udaipur', 'Jodhpur', 'Jaisalmer'],
  },
  {
    id: 'himachal-pradesh',
    name: 'Himachal Pradesh',
    image: 'https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=900&q=80',
    description: 'Snow-capped mountains, cafés and hidden valleys.',
    accent: 'from-sky-200 via-cyan-100 to-emerald-100',
    cities: ['Shimla', 'Manali', 'Dharamshala', 'Kasol'],
  },
  {
    id: 'kerala',
    name: 'Kerala',
    image: 'https://images.unsplash.com/photo-1511497584788-876760111969?auto=format&fit=crop&w=900&q=80',
    description: 'Backwaters, beaches and serene escapes.',
    accent: 'from-emerald-200 via-lime-100 to-cyan-100',
    cities: ['Kochi', 'Alleppey', 'Munnar', 'Thekkady'],
  },
  {
    id: 'goa',
    name: 'Goa',
    image: 'https://images.unsplash.com/photo-1519046904884-53103b34b206?auto=format&fit=crop&w=900&q=80',
    description: 'Sunsets, nightlife and coastal charm.',
    accent: 'from-fuchsia-200 via-rose-100 to-amber-100',
    cities: ['North Goa', 'South Goa', 'Panaji', 'Margao'],
  },
  {
    id: 'kashmir',
    name: 'Kashmir',
    image: 'https://images.unsplash.com/photo-1587474260584-136574528ed5?auto=format&fit=crop&w=900&q=80',
    description: 'Paradise of lakes, mountains and gardens.',
    accent: 'from-blue-200 via-slate-100 to-violet-100',
    cities: ['Srinagar', 'Gulmarg', 'Pahalgam', 'Sonamarg'],
  },
  {
    id: 'meghalaya',
    name: 'Meghalaya',
    image: 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80',
    description: 'Waterfalls, caves and living root bridges.',
    accent: 'from-green-200 via-emerald-100 to-teal-100',
    cities: ['Shillong', 'Cherrapunji', 'Mawlynnong', 'Dawki'],
  },
];
