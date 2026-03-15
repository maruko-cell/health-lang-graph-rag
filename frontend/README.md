# 健康助手前端

React + Vite 前端，依赖与整体说明见项目根目录 [README.md](../README.md)。

**配置说明：**

- 环境变量：将 **`frontend/.env.example`** 复制为 **`frontend/.env`** 并填写必填项。
- 必填项：`VITE_BACKEND_ORIGIN` 指向后端地址（如 `http://localhost:4000`），否则无法正确请求后端接口。

**本地开发：**

```bash
npm install
cp .env.example .env   # 首次运行必做
npm run dev
```

默认访问地址：`http://localhost:5173`。
