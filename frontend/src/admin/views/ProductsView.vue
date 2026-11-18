<template>
  <div>
    <!-- 筛选与操作 -->
    <div class="card bar">
      <el-input
        v-model="q"
        placeholder="商品名称"
        class="w-44"
        clearable
        @keyup.enter="load(1)"
        @clear="load(1)"
      />
      <el-select
        v-model="categoryId"
        placeholder="全部分类"
        clearable
        class="w-32"
        @change="load(1)"
      >
        <el-option v-for="c in cats" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-select v-model="status" placeholder="全部状态" clearable class="w-28" @change="load(1)">
        <el-option label="在售" value="on" />
        <el-option label="下架" value="off" />
      </el-select>
      <el-button @click="load(1)">查询</el-button>
      <div class="spacer" />
      <el-button :icon="Download" @click="download('/api/admin/products/template')">
        导入模板
      </el-button>
      <el-upload :show-file-list="false" accept=".xlsx" :http-request="doImport">
        <el-button :icon="DocumentAdd">Excel 导入</el-button>
      </el-upload>
      <el-button :icon="Promotion" @click="download('/api/admin/products/export')">
        导出
      </el-button>
      <el-button :icon="FolderOpened" @click="catsVisible = true">分类管理</el-button>
      <el-button type="primary" :icon="Plus" @click="openEdit()">新增商品</el-button>
    </div>

    <!-- 商品表 -->
    <div class="card" v-loading="loading">
      <el-table :data="items">
        <el-table-column label="图片" width="72">
          <template #default="{ row }">
            <el-image
              v-if="row.image"
              :src="row.image"
              fit="cover"
              lazy
              class="thumb"
            />
            <div v-else class="thumb no-img">{{ row.name.slice(0, 1) }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="brand" label="品牌" width="90" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" width="90" show-overflow-tooltip />
        <el-table-column prop="unit" label="单位" width="60" />
        <el-table-column label="售价" width="96" align="right">
          <template #default="{ row }">
            <span class="price">￥{{ fmtMoney(row.price_sale) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="原价" width="96" align="right">
          <template #default="{ row }">
            <span class="origin">￥{{ fmtMoney(row.price_original) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="库存" width="80" align="right">
          <template #default="{ row }">
            <span :class="{ stockout: row.stock === 0 }">
              {{ row.stock === null ? "无限" : row.stock }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="76">
          <template #default="{ row }">
            <el-tag :type="row.status === 'on' ? 'success' : 'info'" size="small" effect="light">
              {{ row.status === "on" ? "在售" : "下架" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="116" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button
              link
              :type="row.status === 'on' ? 'info' : 'success'"
              @click="toggle(row)"
            >
              {{ row.status === "on" ? "下架" : "上架" }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无商品，点右上角「新增商品」或 Excel 导入" :image-size="80" />
        </template>
      </el-table>
      <el-pagination
        class="mt-4"
        layout="total, prev, pager, next"
        :total="total"
        :page-size="20"
        :current-page="page"
        @current-change="load"
      />
    </div>

    <!-- 新增 / 编辑 -->
    <el-dialog v-model="editVisible" :title="form.id ? '编辑商品' : '新增商品'" width="580">
      <el-form label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" maxlength="60" />
        </el-form-item>
        <div class="grid-cols-2">
          <el-form-item label="规格">
            <el-input v-model="form.spec" placeholder="如 500g/盒" />
          </el-form-item>
          <el-form-item label="单位" required>
            <el-input v-model="form.unit" style="width: 96px" placeholder="件" />
          </el-form-item>
        </div>
        <div class="grid-cols-2">
          <el-form-item label="品牌">
            <el-input v-model="form.brand" />
          </el-form-item>
          <el-form-item label="产地">
            <el-input v-model="form.origin" />
          </el-form-item>
        </div>
        <el-form-item label="分类">
          <el-select v-model="form.category_id" clearable placeholder="未分类" class="w-full">
            <el-option v-for="c in cats" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <div class="grid-cols-2">
          <el-form-item label="原价(元)">
            <el-input-number v-model="form._po" :min="0" :precision="2" :step="0.5" />
          </el-form-item>
          <el-form-item label="售价(元)" required>
            <el-input-number v-model="form._ps" :min="0.01" :precision="2" :step="0.5" />
          </el-form-item>
        </div>
        <el-form-item label="库存">
          <el-input-number v-model="form._stock" :min="0" placeholder="留空 = 不限库存" />
          <span class="form-hint">清空数值表示不限库存</span>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" />
          <span class="form-hint">小的排前面</span>
        </el-form-item>
        <el-form-item label="图片">
          <div class="w-full">
            <div class="flex flex-wrap items-start gap-2">
              <div v-for="(img, i) in form.images" :key="img" class="img-cell">
                <el-image :src="img" fit="cover" class="img-preview" :preview-src-list="form.images" :initial-index="i" />
                <span v-if="i === 0" class="cover-tag">封面</span>
                <div class="img-ops">
                  <el-button v-if="i > 0" link size="small" @click="setCover(i)">
                    设为封面
                  </el-button>
                  <el-button link size="small" type="danger" @click="form.images.splice(i, 1)">
                    删除
                  </el-button>
                </div>
              </div>
              <el-upload
                v-if="form.images.length < 9"
                :show-file-list="false"
                accept=".jpg,.jpeg,.png,.webp"
                :http-request="doUpload"
              >
                <div class="img-preview upload-cell">＋上传</div>
              </el-upload>
            </div>
            <span class="form-hint">第一张为封面（详情页可左右滑动查看全部），最多 9 张，jpg/png/webp ≤5MB</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分类管理 -->
    <el-dialog v-model="catsVisible" title="分类管理" width="500">
      <el-table :data="cats" size="small">
        <el-table-column label="名称">
          <template #default="{ row }">
            <el-input v-model="row.name" size="small" @change="saveCat(row)" />
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="saveCat(row)" />
          </template>
        </el-table-column>
        <el-table-column label="排序" width="100">
          <template #default="{ row }">
            <el-input-number
              v-model="row.sort"
              size="small"
              controls-position="right"
              @change="saveCat(row)"
            />
          </template>
        </el-table-column>
      </el-table>
      <div class="mt-3 flex gap-2">
        <el-input v-model="newCat" placeholder="新分类名称" size="small" @keyup.enter="addCat" />
        <el-button size="small" type="primary" plain @click="addCat">添加</el-button>
      </div>
    </el-dialog>

    <!-- 导入结果 -->
    <el-dialog v-model="importVisible" title="导入结果" width="520">
      <p v-if="importResult" class="mb-3">
        新增 <b class="ok">{{ importResult.created }}</b> 条，更新
        <b class="ok">{{ importResult.updated }}</b> 条<span v-if="importResult.errors.length">
          ，失败 {{ importResult.errors.length }} 行</span
        >。
      </p>
      <el-alert
        v-for="e in importResult?.errors || []"
        :key="e.row"
        type="error"
        :closable="false"
        class="mb-1.5"
        :title="`第 ${e.row} 行：${e.msg}`"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  DocumentAdd,
  Download,
  FolderOpened,
  Plus,
  Promotion,
} from "@element-plus/icons-vue";
import { api, download } from "../../api/http";
import { fmtMoney } from "../../shared/format";

interface Product {
  id: number;
  name: string;
  brand: string;
  spec: string;
  unit: string;
  origin: string;
  price_original: number;
  price_sale: number;
  image: string | null;
  images: string[];
  category_id: number | null;
  status: string;
  stock: number | null;
  sort: number;
}
interface Category {
  id: number;
  name: string;
  sort: number;
  enabled: boolean;
}
interface ImportResult {
  created: number;
  updated: number;
  errors: { row: number; msg: string }[];
}
interface ProductForm {
  id: number;
  name: string;
  spec: string;
  unit: string;
  brand: string;
  origin: string;
  category_id: number | null;
  sort: number;
  images: string[];
  status: string;
  _po: number;
  _ps: number;
  _stock: number | null;
}

const emptyForm = (): ProductForm => ({
  id: 0,
  name: "",
  spec: "",
  unit: "件",
  brand: "",
  origin: "",
  category_id: null,
  sort: 0,
  images: [],
  status: "on",
  _po: 0,
  _ps: 0,
  _stock: null,
});

const q = ref("");
const categoryId = ref<number | undefined>(undefined);
const status = ref("");
const cats = ref<Category[]>([]);
const items = ref<Product[]>([]);
const total = ref(0);
const page = ref(1);
const loading = ref(false);
const editVisible = ref(false);
const saving = ref(false);
const form = ref<ProductForm>(emptyForm());
const catsVisible = ref(false);
const newCat = ref("");
const importResult = ref<ImportResult | null>(null);
const importVisible = ref(false);

async function load(p = 1) {
  page.value = p;
  const params = new URLSearchParams({ page: String(p) });
  if (q.value) params.set("q", q.value);
  if (categoryId.value) params.set("category_id", String(categoryId.value));
  if (status.value) params.set("status", status.value);
  loading.value = true;
  try {
    const d = await api<{ items: Product[]; total: number }>(`/api/admin/products?${params}`);
    items.value = d.items;
    total.value = d.total;
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "加载失败");
  } finally {
    loading.value = false;
  }
}

function openEdit(row?: Product) {
  form.value = row
    ? {
        ...emptyForm(),
        ...row,
        images: row.images?.length ? [...row.images] : row.image ? [row.image] : [],
        _po: row.price_original / 100,
        _ps: row.price_sale / 100,
        _stock: row.stock,
      }
    : emptyForm();
  editVisible.value = true;
}

/** 把第 i 张挪到第一位成为封面 */
function setCover(i: number) {
  const imgs = [...form.value.images];
  const [pick] = imgs.splice(i, 1);
  form.value.images = [pick, ...imgs];
}

async function save() {
  const f = form.value;
  if (!f.name.trim()) {
    ElMessage.warning("请输入商品名称");
    return;
  }
  if (!f._ps || f._ps <= 0) {
    ElMessage.warning("售价需大于 0");
    return;
  }
  const body = {
    name: f.name.trim(),
    spec: f.spec.trim(),
    unit: f.unit.trim() || "件",
    brand: f.brand.trim(),
    origin: f.origin.trim(),
    category_id: f.category_id ?? null,
    price_original: Math.round((f._po || 0) * 100),
    price_sale: Math.round(f._ps * 100),
    stock: f._stock ?? null,
    sort: f.sort || 0,
    status: f.status || "on",
    images: f.images, // 后端自动以第一张为封面
  };
  saving.value = true;
  try {
    if (f.id) {
      await api(`/api/admin/products/${f.id}`, { method: "PUT", body: JSON.stringify(body) });
    } else {
      await api("/api/admin/products", { method: "POST", body: JSON.stringify(body) });
    }
    ElMessage.success("已保存");
    editVisible.value = false;
    load(page.value);
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

async function toggle(row: Product) {
  try {
    await api(`/api/admin/products/${row.id}`, {
      method: "PUT",
      body: JSON.stringify({ status: row.status === "on" ? "off" : "on" }), // 部分更新，只送状态
    });
    load(page.value);
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "操作失败");
  }
}

async function doUpload(opt: { file: File }) {
  const fd = new FormData();
  fd.append("file", opt.file);
  try {
    const d = await api<{ url: string }>("/api/admin/upload", { method: "POST", body: fd });
    form.value.images.push(d.url);
    ElMessage.success("图片已上传");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "上传失败");
  }
}

async function doImport(opt: { file: File }) {
  const fd = new FormData();
  fd.append("file", opt.file);
  try {
    importResult.value = await api<ImportResult>("/api/admin/products/import", {
      method: "POST",
      body: fd,
    });
    importVisible.value = true;
    load(1);
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "导入失败");
  }
}

async function loadCats() {
  cats.value = await api<Category[]>("/api/admin/categories");
}

async function saveCat(row: Category) {
  if (!row.name.trim()) {
    ElMessage.warning("分类名称不能为空");
    loadCats();
    return;
  }
  try {
    await api(`/api/admin/categories/${row.id}`, {
      method: "PUT",
      body: JSON.stringify({
        name: row.name.trim(),
        sort: row.sort || 0,
        enabled: row.enabled !== false,
      }),
    });
    loadCats();
    load(page.value);
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "保存失败");
    loadCats();
  }
}

async function addCat() {
  if (!newCat.value.trim()) return;
  try {
    await api("/api/admin/categories", {
      method: "POST",
      body: JSON.stringify({ name: newCat.value.trim() }),
    });
    newCat.value = "";
    loadCats();
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "添加失败");
  }
}

onMounted(() => {
  loadCats();
  load(1);
});
</script>

<style scoped>
.card {
  background: var(--sc-card);
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.spacer {
  flex: 1;
}
.thumb {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  display: block;
}
.no-img {
  background: var(--sc-primary-soft);
  color: var(--sc-primary);
  font-size: 17px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.price {
  color: var(--sc-price);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.origin {
  color: var(--sc-sub);
  text-decoration: line-through;
  font-variant-numeric: tabular-nums;
}
.stockout {
  color: var(--sc-price);
  font-weight: 600;
}
.grid-cols-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 12px;
}
.form-hint {
  margin-left: 10px;
  font-size: 12px;
  color: var(--sc-sub);
}
.img-preview {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  flex-shrink: 0;
}
.img-cell {
  position: relative;
}
.cover-tag {
  position: absolute;
  left: 0;
  bottom: 18px;
  padding: 0 6px;
  border-radius: 0 8px 0 0;
  background: var(--sc-primary);
  color: #fff;
  font-size: 11px;
  line-height: 18px;
}
.img-ops {
  display: flex;
  justify-content: center;
  gap: 2px;
  margin-top: 1px;
}
.img-ops .el-button + .el-button {
  margin-left: 0;
}
.img-ops .el-button {
  padding: 2px 4px;
  height: auto;
  font-size: 12px;
}
.upload-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed var(--sc-line);
  color: var(--sc-sub);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.upload-cell:hover {
  border-color: var(--sc-primary);
  color: var(--sc-primary);
}
.ok {
  color: var(--sc-primary);
}
</style>
