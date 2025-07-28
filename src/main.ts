import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import { routes } from 'vue-router/auto-routes';
import { createPinia } from 'pinia';
import piniaPluginPersistedState from 'pinia-plugin-persistedstate';
import { Icon } from '@iconify/vue';
import App from './App.vue';

import './styles/main.css'


const pinia = createPinia()
pinia.use(piniaPluginPersistedState)
const router = createRouter({
  routes,
  history: createWebHistory(import.meta.env.BASE_URL),
})
createApp(App).use(router).use(pinia).component("Icon", Icon).mount('#app')
