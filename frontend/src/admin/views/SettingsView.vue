<template>
  <div class="card">
    <el-tabs v-model="tab">
      <!-- 管理员账号 -->
      <el-tab-pane label="管理员账号" name="admins">
        <div class="mb-3">
          <el-button type="primary" :icon="Plus" @click="openEdit()">新增账号</el-button>
        </div>
        <el-table :data="admins" v-loading="loadingAdmins">
          <el-table-column prop="username" label="用户名" width="140" />
          <el-table-column label="姓名" width="120">
            <template #default="{ row }">{{ row.name || "-" }}</template>
          </el-table-column>
          <el-table-column label="角色" width="120">
            <template #default="{ row }">
              <el-tag :type="row.role === 'super' ? 'danger' : 'info'" size="small">
                {{ row.role === "super" ? "超级管理员" : "操作员" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="86">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
                {{ row.is_active ? "启用" : "停用" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="最近登录" width="160">
            <template #default="{ row }">
              {{ (row.last_login_at || "-").slice(0, 16).replace("T", " ") }}
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="200">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="warning" @click="resetPwd(row)">重置密码</el-button>
              <el-button
                link
                :type="row.is_active ? 'danger' : 'success'"
                @click="toggle(row)"
              >
                {{ row.is_active ? "停用" : "启用" }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 取货须知 -->
      <el-tab-pane label="取货须知" name="notice">
        <div class="notice-panel">
          <el-input
            v-model="notice"
            type="textarea"
            :rows="9"
            maxlength="500"
            show-word-limit
            placeholder="服务点位置、营业时间、支付方式说明…（教职工端「取货须知」页展示）"
          />
          <div class="mt-3">
            <el-button type="primary" :loading="savingNotice" @click="saveNotice">
              保存
            </el-button>
            <span class="form-hint">保存后教职工端即时生效</span>
          </div>
        </div>
      </el-tab-pane>

      <!-- 操作日志 -->
      <el-tab-pane label="操作日志" name="logs">
        <el-table :data="logs" v-loading="loadingLogs">
          <el-table-column label="时间" width="160">
            <template #default="{ row }">
              {{ (row.created_at || "").slice(0, 19).replace("T", " ") }}
            </template>
          </el-table-column>
          <el-table-column prop="username" label="账号" width="120" />
          <el-table-column label="动作" width="110">
            <template #default="{ row }">{{ ACTION_LABEL[row.action] || row.action }}</template>
          </el-table-column>
          <el-table-column prop="target" label="对象" width="170" show-overflow-tooltip />
          <el-table-column prop="detail" label="详情" min-width="180" show-overflow-tooltip />
          <template #empty>
            <el-empty description="暂无日志" :image-size="80" />
          </template>
        </el-table>
        <el-pagination
          class="mt-4"
          layout="total, prev, pager, next"
          :total="logTotal"
          :page-size="20"
          @current-change="loadLogs"
        />
      </el-tab-pane>
    </el-tabs>
  </div>

  <!-- 新增 / 编辑账号 -->
  <el-dialog v-model="editVisible" :title="form.id ? '编辑账号' : '新增账号'" width="420">
    <el-form label-width="80px">
      <el-form-item label="用户名" required>
        <el-input v-model="form.username" :disabled="!!form.id" maxlength="32" />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input v-model="form.name" maxlength="30" />
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="form.role">
          <el-option label="操作员（无系统设置权限）" value="operator" />
          <el-option label="超级管理员" value="super" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="!form.id" label="初始密码" required>
        <el-input v-model="form.password" type="password" show-password placeholder="至少 6 位" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editVisible = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus } from "@element-plus/icons-vue";
import { api } from "../../api/http";
import { useAdminStore } from "../../stores/admin";

interface AdminRow {
  id: number;
  username: string;
  name: string;
  role: string;
  is_active: boolean;
  last_login_at: string | null;
}
interface LogRow {
  id: number;
  username: string;
  action: string;
  target: string;
  detail: string;
  created_at: string;
}
interface AdminForm {
  id: number;
  username: string;
  name: string;
  role: string;
  password: string;
}

const ACTION_LABEL: Record<string, string> = {
  verify: "核销",
  cancel: "代取消",
  admin_create: "新增账号",
  admin_update: "修改账号",
  login: "登录",
};

const emptyForm = (): AdminForm => ({
  id: 0,
  username: "",
  name: "",
  role: "operator",
  password: "",
});

const store = useAdminStore();
const tab = ref("admins");
const admins = ref<AdminRow[]>([]);
const notice = ref("");
const logs = ref<LogRow[]>([]);
const logTotal = ref(0);
const editVisible = ref(false);
const form = ref<AdminForm>(emptyForm());
const loadingAdmins = ref(false);
const loadingLogs = ref(false);
const savingNotice = ref(false);

async function loadAdmins() {
  loadingAdmins.value = true;
  try {
    admins.value = await api<AdminRow[]>("/api/admin/admins");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "加载失败");
  } finally {
    loadingAdmins.value = false;
  }
}

async function loadLogs(p = 1) {
  loadingLogs.value = true;
  try {
    const d = await api<{ items: LogRow[]; total: number }>(`/api/admin/logs?page=${p}`);
    logs.value = d.items;
    logTotal.value = d.total;
  } finally {
    loadingLogs.value = false;
  }
}

function openEdit(row?: AdminRow) {
  form.value = row
    ? { ...emptyForm(), id: row.id, username: row.username, name: row.name, role: row.role }
    : emptyForm();
  editVisible.value = true;
}

async function save() {
  const f = form.value;
  if (!f.id) {
    if (!f.username.trim()) {
      ElMessage.warning("请输入用户名");
      return;
    }
    if (f.password.length < 6) {
      ElMessage.warning("初始密码至少 6 位");
      return;
    }
  }
  try {
    if (f.id) {
      await api(`/api/admin/admins/${f.id}`, {
        method: "PUT",
        body: JSON.stringify({ role: f.role, name: f.name.trim() }),
      });
    } else {
      await api("/api/admin/admins", {
        method: "POST",
        body: JSON.stringify({
          username: f.username.trim(),
          password: f.password,
          role: f.role,
          name: f.name.trim(),
        }),
      });
    }
    ElMessage.success("已保存");
    editVisible.value = false;
    loadAdmins();
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "保存失败");
  }
}

async function resetPwd(row: AdminRow) {
  let pwd: string;
  try {
    const { value } = await ElMessageBox.prompt(
      `为账号「${row.username}」设置新密码，保存后立即生效（原会话不失效）。`,
      "重置密码",
      {
        inputType: "password",
        inputPlaceholder: "新密码（至少 6 位）",
        inputValidator: (v: string) => (v || "").length >= 6 || "密码至少 6 位",
      },
    );
    pwd = value;
  } catch {
    return; // 用户放弃
  }
  try {
    await api(`/api/admin/admins/${row.id}`, {
      method: "PUT",
      body: JSON.stringify({ password: pwd }),
    });
    ElMessage.success("已重置");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "重置失败");
  }
}

async function toggle(row: AdminRow) {
  if (row.is_active && row.username === store.admin?.username) {
    ElMessage.warning("不能停用当前登录的账号");
    return;
  }
  try {
    await api(`/api/admin/admins/${row.id}`, {
      method: "PUT",
      body: JSON.stringify({ is_active: !row.is_active }),
    });
    loadAdmins();
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "操作失败");
  }
}

async function loadNotice() {
  try {
    const d = await api<{ content: string }>("/api/admin/settings/notice");
    notice.value = d.content;
  } catch {
    /* 留空即可 */
  }
}

async function saveNotice() {
  savingNotice.value = true;
  try {
    await api("/api/admin/settings/notice", {
      method: "PUT",
      body: JSON.stringify({ content: notice.value }),
    });
    ElMessage.success("已保存，教职工端即时生效");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "保存失败");
  } finally {
    savingNotice.value = false;
  }
}

onMounted(() => {
  loadAdmins();
  loadNotice();
  loadLogs(1);
});
</script>

<style scoped>
.card {
  background: var(--sc-card);
  border-radius: 12px;
  padding: 8px 20px 16px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.notice-panel {
  max-width: 560px;
  padding-top: 8px;
}
.form-hint {
  margin-left: 12px;
  font-size: 12px;
  color: var(--sc-sub);
}
</style>
