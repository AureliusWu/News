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
    path: "/library",
    name: "library",
    component: () => import("../pages/LibraryView.vue")
  },
  {
    path: "/sources",
    name: "sources",
    component: () => import("../pages/SourcesView.vue")
  },
  {path: "/events", name: "events", component: () => import("../pages/EventsView.vue")},
  {path: "/events/:eventId", name: "event-detail", component: () => import("../pages/EventsView.vue")},
  {
    path: "/:pathMatch(.*)*",
    redirect: "/"
  }
];

export default routes;

export const routerHistory = createWebHistory(import.meta.env.BASE_URL);
