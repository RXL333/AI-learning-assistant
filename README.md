# AI 学习助手

!\[Python]\(https\://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge\&logo=python\&logoColor=white)
!\[FastAPI]\(https\://img.shields.io/badge/FastAPI-0.116-009688?style=for-the-badge\&logo=fastapi\&logoColor=white)
!\[Vue]\(https\://img.shields.io/badge/Vue-3-42B883?style=for-the-badge\&logo=vuedotjs\&logoColor=white)
!\[Vite]\(https\://img.shields.io/badge/Vite-7-646CFF?style=for-the-badge\&logo=vite\&logoColor=white)
!\[SQLAlchemy]\(https\://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=for-the-badge\&logo=sqlalchemy\&logoColor=white)
!\[SQLite]\(https\://img.shields.io/badge/SQLite-Default-003B57?style=for-the-badge\&logo=sqlite\&logoColor=white)
!\[MySQL]\(https\://img.shields.io/badge/MySQL-Optional-4479A1?style=for-the-badge\&logo=mysql\&logoColor=white)
!\[OpenAI Compatible]\(https\://img.shields.io/badge/OpenAI-Compatible-111111?style=for-the-badge\&logo=openai\&logoColor=white)
!\[Status]\(https\://img.shields.io/badge/Status-Ready%20for%20Portfolio-8A5CF6?style=for-the-badge)
!\[License]\(https\://img.shields.io/badge/License-Add%20Your%20Own-lightgrey?style=for-the-badge)

<br />

一个面向个人学习场景的全栈学习平台。它把 `AI 问答`、`错题整理`、`AI 出题`、`复习安排`、`学习轨迹回看`、`思维导图生成` 组合到同一个工作流里，适合用来做日常学习记录、知识梳理和复盘。

项目采用前后端分离架构：

- 前端：`Vue 3 + Vue Router + Vite`
- 后端：`FastAPI + SQLAlchemy`
- 数据库：默认 `SQLite`，可切换 `MySQL`
- AI 接口：兼容 OpenAI 风格 API
- 迁移工具：`Alembic`

## 项目理解

这个项目不是单纯的聊天壳子，而是一套围绕学习闭环设计的工具：

1. 先在 `AI 问答` 中提问、解释、拆解知识点
2. 再把问题沉淀到 `错题本` 或 `思维导图`
3. 通过 `AI 出题` 做练习并记录薄弱点
4. 在 `复习中心` 里集中完成当天该做的复习
5. 最后到 `学习历史` 回看最近几天到底学了什么

如果你想做的是一个“能持续记录学习行为并不断回看”的学习助手，这个项目比单页面聊天工具更合适。

## 核心功能

### 1. AI 问答

- 支持多种学习模式切换
- 支持普通问答和更偏鼓励式的陪伴对话
- 问答结果可进一步转为学习资产

### 2. 错题本

- 支持手动录入错题
- 支持 AI 出题后自动把答错内容加入错题本
- AI 生成的选择题会保留题干、选项和答案信息，便于后续复习

### 3. AI 出题

- 可以基于学科或主题生成练习题
- 支持提交答案、自动判题、生成解析
- 试卷历史可查看、可删除

### 4. 复习中心

- 把原来的“今日复习”和“复习计划”合并成一个入口
- 以“今天先做什么”为主，减少重复信息
- 支持直接进入 AI 带学式复习流程

### 5. 学习历史

- 用更轻量的时间线回看最近学习记录
- 聚合问答、错题和复习任务
- 适合做学习复盘，而不是只看分散页面

### 6. 思维导图

- 支持将学习内容转换成导图结构
- 方便从零散对话过渡到结构化知识梳理

### 7. 用户系统

- 支持注册、登录、鉴权
- 前端路由按登录态保护

## 适用场景

- 个人自学
- 课程复习
- 错题整理
- 面试知识回顾
- AI 辅助学习记录

不适合的场景：

- 高并发在线教育平台
- 大规模班级管理
- 多租户 SaaS
- 强依赖复杂推荐系统或海量题库的正式商业平台

## 技术架构

### 前端

- `Vue 3`
- `Vue Router 4`
- `Vite`

前端主要页面包括：

- `Dashboard`
- `AI 问答`
- `错题本`
- `AI 出题`
- `复习中心`
- `学习历史`
- `思维导图`
- `个人中心`

### 后端

- `FastAPI`
- `SQLAlchemy 2`
- `python-jose`
- `passlib`
- `httpx`
- `Alembic`

后端职责包括：

- 用户认证
- 聊天与 AI 接口编排
- 错题、复习、试卷、导图等业务数据管理
- 前端静态资源托管

### 数据库

- 默认本地数据库：`SQLite`
- 可切换到：`MySQL`

默认运行数据库位于：

- `backend/ai_study_helper.db`

## 项目结构

```text
AI学习助手/
├─ backend/
│  ├─ app/
│  │  ├─ routers/        # 路由层
│  │  ├─ services/       # AI 模式、业务辅助逻辑
│  │  ├─ config.py       # 配置读取
│  │  ├─ database.py     # 数据库连接与兼容初始化
│  │  ├─ models.py       # SQLAlchemy 模型
│  │  └─ main.py         # FastAPI 入口
│  ├─ alembic/           # 迁移目录
│  ├─ tests/             # 基础后端测试
│  ├─ run.py             # 启动脚本
│  ├─ requirements.txt   # Python 依赖
│  └─ .env.example       # 环境变量模板
├─ frontend/
│  ├─ src/
│  │  ├─ pages/          # 页面
│  │  ├─ api.js          # API 请求封装
│  │  ├─ router.js       # 路由
│  │  └─ App.js          # 根组件
│  ├─ styles.css         # 全局样式
│  ├─ package.json       # 前端依赖
│  └─ vite.config.js     # Vite 配置
└─ README.md
```

## 环境要求

建议环境：

- Python `3.10+`
- Node.js `18+`
- npm `9+`

如果你只想本地体验，SQLite 就够用。
如果你准备长期运行或多用户使用，建议尽早切换 MySQL。

## 安装与启动

## 一、克隆项目

```bash
git clone <your-repo-url>
cd AI学习助手
```

## 二、配置后端环境

进入后端目录并安装依赖：

```bash
cd backend
pip install -r requirements.txt
```

根据模板创建环境变量文件：

```bash
copy .env.example .env
```

或者手动创建 `backend/.env`。

### `backend/.env` 示例

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-5.2
JWT_SECRET_KEY=replace_with_a_long_random_secret
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:///./ai_study_helper.db
```

### 环境变量说明

- `OPENAI_API_KEY`
  AI 接口密钥
- `OPENAI_BASE_URL`
  OpenAI 风格接口地址，默认官方地址
- `OPENAI_MODEL`
  默认模型名
- `JWT_SECRET_KEY`
  登录鉴权密钥，生产环境必须替换
- `ACCESS_TOKEN_EXPIRE_MINUTES`
  Token 过期时间，单位分钟
- `DATABASE_URL`
  数据库连接地址

## 三、启动后端

```bash
cd backend
python run.py
```

默认运行地址：

```text
http://127.0.0.1:8001
```

可用健康检查：

```text
http://127.0.0.1:8001/api/health
```

## 四、启动前端开发环境

```bash
cd frontend
npm install
npm run dev
```

默认地址：

```text
http://127.0.0.1:5173
```

前端开发时已配置代理：

- `/api` 会自动转发到 `http://127.0.0.1:8001`

## 五、前端生产构建

```bash
cd frontend
npm run build
```

构建产物输出到：

- `frontend/dist`

后端在检测到 `frontend/dist` 存在时，会直接托管前端静态资源。

这意味着你可以有两种运行方式：

1. 开发模式

- 前端 `Vite dev server`
- 后端 `FastAPI`

1. 一体化运行

- 先构建前端
- 再启动后端
- 由后端直接提供前端页面

## 数据库说明

## 默认使用 SQLite

默认数据库配置：

```env
DATABASE_URL=sqlite:///./ai_study_helper.db
```

在当前项目中，它会指向：

- `backend/ai_study_helper.db`

适合：

- 本地开发
- 个人使用
- 功能验证

## 切换到 MySQL

如果你希望：

- 多用户长期使用
- 更稳的并发写入
- 更完整的关系型数据库能力

建议切到 MySQL。

### 1. 创建数据库

```sql
CREATE DATABASE ai_study_helper CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 修改 `backend/.env`

```env
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/ai_study_helper?charset=utf8mb4
```

### 3. 执行迁移

```bash
cd backend
alembic upgrade head
```

### 4. 启动后端

```bash
python run.py
```

## Alembic 迁移

项目已集成 Alembic。

### 执行已有迁移

```bash
cd backend
alembic upgrade head
```

### 生成新迁移

当你修改了模型后：

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

相关目录：

- `backend/alembic.ini`
- `backend/alembic/`

## 默认账号与隐私说明

本仓库默认不包含真实用户数据。

上传 GitHub 前，建议确保以下内容不进入仓库：

- `backend/.env`
- `*.db`
- `frontend/node_modules`
- `frontend/dist`
- `*.log`
- `__pycache__`

项目当前 `.gitignore` 已覆盖上述大部分内容。

如果你是首次拉取仓库：

- 请自行创建 `backend/.env`
- 首次启动后注册账号即可使用

## 常用开发命令

### 后端

安装依赖：

```bash
cd backend
pip install -r requirements.txt
```

启动服务：

```bash
python run.py
```

运行基础检查：

```bash
python -m compileall backend
```

运行测试：

```bash
python -m unittest discover backend/tests
```

### 前端

安装依赖：

```bash
cd frontend
npm install
```

本地开发：

```bash
npm run dev
```

生产构建：

```bash
npm run build
```

本地预览构建：

```bash
npm run preview
```

## 页面说明

### 首页

- 查看学习总览
- 快速进入核心功能模块

### AI 问答

- 与 AI 直接对话
- 支持不同学习模式
- 适合提问、解释、梳理和陪伴学习

### 错题本

- 管理错题
- 查看题目、答案、解析和复习信息

### AI 出题

- 生成题目
- 提交答案
- 生成解析
- 错题自动沉淀

### 复习中心

- 查看今天优先处理的任务
- 继续复习弱项
- 通过 AI 带学继续推进

### 学习历史

- 按时间线回看最近的学习轨迹
- 适合做阶段复盘

### 思维导图

- 把学习内容转成结构化导图

### 个人中心

- 查看账号信息
- 管理登录状态

<br />

## 已知边界

当前项目更适合作为：

- 个人学习助手
- 小规模内部工具

如果你要把它做成正式线上产品，建议继续完善：

- 更完整的测试体系
- 更严格的权限与限流
- 更稳定的数据库迁移流程
- 更细的日志与监控
- 更强的前后端契约约束

## License

如果你准备公开仓库，建议补充正式许可证，例如：

- `MIT`
- `Apache-2.0`

当前仓库如未单独声明许可证，请按你的实际发布策略补充。
