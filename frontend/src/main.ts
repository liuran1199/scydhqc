import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import zhCn from "element-plus/dist/locale/zh-cn.mjs";
import Vant from "vant";
import "element-plus/dist/index.css";
import "vant/lib/index.css";
import "./main.css";
import App from "./App.vue";
import router from "./router";

createApp(App)
  .use(createPinia())
  .use(router)
  .use(ElementPlus, { locale: zhCn })
  .use(Vant)
  .mount("#app");
