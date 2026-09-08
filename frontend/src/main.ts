import {createApp} from "vue";
import {createPinia} from "pinia";
import {createRouter} from "vue-router";
import routes, {routerHistory} from "./router";
import App from "./App.vue";
import "./styles.css";

const router = createRouter({
  history: routerHistory,
  routes
});

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount("#app");
