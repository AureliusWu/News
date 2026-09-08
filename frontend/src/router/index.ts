import {createRouter, createWebHistory, type RouteRecordRaw} from "vue-router";
import HomeView from "../pages/HomeView.vue";
import AboutView from "../pages/AboutView.vue";

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    name: "home",
    component: HomeView
  },
  {
    path: "/about",
    name: "about",
    component: AboutView
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: "/"
  }
];

export default routes;

export const routerHistory = createWebHistory(import.meta.env.BASE_URL);
