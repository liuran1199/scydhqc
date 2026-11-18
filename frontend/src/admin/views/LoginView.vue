<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="brand">
        <div class="brand-mark">食</div>
        <div>
          <h1 class="text-[18px] font-bold tracking-wide">食材服务点</h1>
          <p class="text-xs text-[--sc-sub] mt-0.5">后勤管理处 · 预订管理后台</p>
        </div>
      </div>
      <el-form label-position="top" @submit.prevent="login">
        <el-form-item>
          <el-input
            v-model="username"
            placeholder="用户名"
            size="large"
            :prefix-icon="User"
            autofocus
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            :prefix-icon="Lock"
            @keyup.enter="login"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="w-full"
          native-type="submit"
          :loading="loading"
        >
          {{ loading ? "登录中…" : "登 录" }}
        </el-button>
      </el-form>
      <p class="mt-5 text-center text-xs text-[--sc-sub]">
        仅限后勤管理人员使用，账号由系统管理员分配
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Lock, User } from "@element-plus/icons-vue";
import { useAdminStore } from "../../stores/admin";

const username = ref("");
const password = ref("");
const loading = ref(false);
const router = useRouter();
const store = useAdminStore();

async function login() {
  if (!username.value || !password.value) {
    ElMessage.warning("请输入用户名和密码");
    return;
  }
  loading.value = true;
  try {
    await store.login(username.value, password.value);
    router.push("/admin/dashboard");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "登录失败"); // 含锁定提示文案
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(1200px 500px at 20% -10%, #e7f0ea 0%, transparent 60%),
    var(--sc-bg);
  padding: 24px;
}
.login-card {
  width: 400px;
  max-width: 100%;
  background: var(--sc-card);
  border-radius: 16px;
  padding: 36px 36px 28px;
  box-shadow: 0 8px 30px rgb(31 41 51 / 10%);
}
.brand {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 28px;
}
.brand-mark {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  background: var(--sc-primary);
  color: #fff;
  font-size: 22px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
