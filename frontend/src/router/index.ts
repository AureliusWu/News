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
  }
];

export default routes;
