# 完整实施计划：Logo更新 + 登录页/落地页一体化改造

我已基于你的需求整理出**可直接执行**的前端改造方案（React/Next.js 技术栈），覆盖Logo替换、油气田化学研发系统专属落地页设计、登录页融合，所有步骤适配项目结构。

---

## 一、Logo 100%替换方案

### 1. 资源处理（必须步骤）

1. 将本地图片 `D:\iCloudDrive\__NEW\00_MINE\PRJ\石油化工\41-设计\Logo\Lumiton·Omax图标.png`
   复制到前端项目：`frontend/public/logo.png`
2. 文本Logo统一为：`Lumiton·Omax | 知涌`

### 2. 全局替换代码（核心文件）

#### ① 侧边栏 Logo（AppSidebar.tsx）

找到项目中的 `AppSidebar.tsx`，替换品牌区域代码：
```tsx
// 原Logo代码 → 替换为以下内容
<div className="flex items-center gap-2 px-3 py-4">
  <img 
    src="/logo.png" 
    alt="Lumiton·Omax Logo" 
    className="h-8 w-auto"  // 尺寸可自适应调整
  />
  <span className="text-lg font-bold text-white">
    Lumiton·Omax | 知涌
  </span>
</div>
```

#### ② 登录页/全局 Header Logo

搜索所有包含 `logo`、`brand`、SVG图标的文件，统一替换为上述图片+文本组合。

#### ③ 页面标题/浏览器标签

修改 `frontend/src/app/layout.tsx`：
```tsx
export const metadata = {
  title: "Lumiton·Omax | 知涌 - 油气田化学研发操作系统",
  icons: {
    icon: "/logo.png",
  },
};
```

---

## 二、登录页 → 专业落地页 一体化改造

核心目标：**登录表单 + 产品宣传Hero区融合**，对标参考站风格，聚焦**油井水泥外加剂/油气田化学研发系统**定位。

### 1. 核心定位文案（直接使用）

- 主标题：**Lumiton·Omax | 知涌**
- 副标题：**油气田化学 / 油井水泥外加剂 研发操作系统**
- 核心价值：
  从经验试错 → 机理驱动与智能预测
  构建可追踪、可复盘、可预测的研发决策系统
- 功能亮点：
  ✅ 历史经验/实验数据结构化管理
  ✅ 现场反馈闭环追踪
  ✅ 产品机理假设数字化验证
  ✅ 智能研发决策支持

### 2. 代码实现：登录+落地页（login/page.tsx）

新建/替换 `frontend/src/app/login/page.tsx`，这是Next.js标准路由文件：

```tsx
// login/page.tsx - 油气田研发系统 登录&落地页
"use client";
import React from "react";
import LoginForm from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex flex-col">
      {/* 顶部导航栏 */}
      <header className="w-full px-6 py-4 border-b border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Logo" className="h-9 w-auto" />
            <h1 className="text-xl font-bold text-slate-800">
              Lumiton·Omax | 知涌
            </h1>
          </div>
        </div>
      </header>

      {/* 主内容区：左侧宣传 + 右侧登录表单 */}
      <main className="flex-1 flex max-w-7xl mx-auto w-full px-4 py-12 md:py-24">
        {/* 左侧：产品落地页宣传区 */}
        <div className="hidden md:flex flex-col w-1/2 justify-center pr-12">
          <h2 className="text-4xl font-bold text-slate-800 mb-4 leading-tight">
            油气田化学 / 油井水泥外加剂
            <span className="text-blue-600 block mt-2">研发操作系统</span>
          </h2>
          
          <p className="text-lg text-slate-600 mb-8">
            帮助研发团队把历史经验、实验数据、现场反馈和产品机理假设
            组织成可追踪、可复盘、可预测的研发决策系统
          </p>

          {/* 核心价值点 */}
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <span className="text-green-500 text-xl">✅</span>
              <span className="text-slate-700">从经验试错转向机理与预测</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-green-500 text-xl">✅</span>
              <span className="text-slate-700">实验数据全生命周期管理</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-green-500 text-xl">✅</span>
              <span className="text-slate-700">研发过程数字化、可追溯</span>
            </div>
          </div>
        </div>

        {/* 右侧：登录表单 */}
        <div className="w-full md:w-1/2 flex items-center justify-center">
          <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8">
            <div className="text-center mb-6">
              <h3 className="text-2xl font-bold text-slate-800">欢迎登录</h3>
              <p className="text-slate-500 mt-1">进入研发操作系统</p>
            </div>
            {/* 登录表单组件 */}
            <LoginForm />
          </div>
        </div>
      </main>

      {/* 页脚 */}
      <footer className="w-full px-6 py-4 border-t border-slate-200 bg-white text-center text-slate-500 text-sm">
        © {new Date().getFullYear()} Lumiton·Omax | 知涌 油气田化学研发系统
      </footer>
    </div>
  );
}
```

### 3. 登录表单组件（LoginForm.tsx）

保持原有登录逻辑不变，仅做样式适配，确保和落地页融合：

```tsx
// src/components/auth/LoginForm.tsx
"use client";
import { useState } from "react";

export default function LoginForm() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    // 原有登录逻辑
    console.log("登录:", username, password);
  };

  return (
    <form onSubmit={handleLogin} className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          账号
        </label>
        <input
          type="text"
          className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          密码
        </label>
        <input
          type="password"
          className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </div>

      <button
        type="submit"
        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-lg transition-colors"
      >
        登录系统
      </button>
    </form>
  );
}
```

---

## 三、快速检索命令（定位所有Logo相关文件）


在项目根目录执行，快速找到所有需要修改的文件：

```bash
# 搜索所有logo相关代码
grep -r "logo" frontend/src/ --include="*.tsx" --include="*.ts"

# 搜索侧边栏品牌文件
grep -r "AppSidebar" frontend/src/ --include="*.tsx"

# 搜索登录页面
find frontend/src/app -name "login*"
```

---

## 四、改造完成效果

1. **全平台Logo统一**：侧边栏、登录页、浏览器标签均显示 `Lumiton·Omax | 知涌`
2. **专业落地页**：登录页自带油气田化学研发系统宣传，对标参考站高端质感
3. **功能融合**：左侧产品介绍 + 右侧登录表单，无需单独开发落地页
4. **业务匹配**：核心文案完全贴合**油井水泥外加剂研发**业务场景

---

### 总结

1. **Logo替换**：复制图片到`public/`，全局替换文本和图片引用；
2. **页面改造**：用`login/page.tsx`实现**登录+落地页二合一**，适配油气田研发业务；
3. **样式适配**：采用化工/研发系统专业配色（蓝白渐变），保持简洁专业。

---
