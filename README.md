# 食材服务点线上预订系统

教职工（企微 H5，CAS 登录）线上预订食材；后勤处（PC 后台，账号密码）管理商品、
备货、核销、对账。取货现场支付，系统不动资金。

## 本地开发

```bash
docker compose -f docker-compose.dev.yml up -d   # MySQL
cd backend && python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                             # 按需修改
python seed.py                                   # 建表+66 SKU（初始管理员在应用首次启动时自动创建）
uvicorn app.main:app --host 0.0.0.0 --port 13000
cd ../frontend && npm install && npm run dev     # 5173，代理到 13000
```

本地联调登录：`/api/auth/dev-login?empid=T001&name=张老师`（`DEV_AUTH_ENABLED=1` 时）。

## E2E

```bash
cd e2e && npm install && npx playwright install chromium
bash ../scripts/e2e-up.sh && npx playwright test; bash ../scripts/e2e-down.sh
```

## CAS 联调

1. `CAS_BASE_URL` 填学校 CAS 地址（含 `/cas` 路径）
2. `APP_BASE_URL` 填已报备回调地址（开发期 `http://10.204.0.146:13000`）
3. 验证 `serviceValidate` 是否带姓名属性；不带则用后台「工号-姓名名单导入」或首登补填

## 生产部署

1. 校内服务器装 Docker；正式域名解析到服务器，证书放 `nginx/certs/`
2. **正式域名先到 CAS 管理员处报备 service 回调地址**
3. 根目录 `.env` 配好 `APP_BASE_URL/SESSION_SECRET/CAS_BASE_URL/INITIAL_ADMIN_PASSWORD/ MYSQL_ROOT_PASSWORD`
4. `docker compose up -d --build`
5. 首次进入后台改初始密码；建操作员账号
6. crontab: `0 2 * * * bash /path/to/scripts/backup.sh`

## 备份恢复

`backups/db-*.sql.gz`（数据库）、`backups/uploads-*.tgz`（图片），保留 7 天。
