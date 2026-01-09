![70a86a2398fff3c609f2fa6d81fc4db3](https://github.com/user-attachments/assets/33da3ed9-2433-4525-b502-0ec0f6fcc0be)# 微信公众号文章生成器 - 启动指南

> 🚀 一站式 AI 写作 + 智能配图 + 精美渲染解决方案

---

## 📦 项目简介

本 Skill 是一套端到端的微信公众号文章生成流水线，采用 **"科技速食"** 写作人设，可自动完成：

1. **AI 写作**：基于主题生成符合公众号风格的科普文章
2. **智能配图**：识别 `![Image](描述)` 占位符，调用 Gemini API 生成精美插画
3. **敏感词审查**：自动替换平台敏感词，避免限流
4. **HTML 渲染**：转换为微信编辑器兼容的富文本格式
5. **一键复制**：直接粘贴到公众号后台

---

## ⚙️ 环境要求

| 依赖项 | 版本要求 | 说明 |
|--------|----------|------|
| Python | ≥ 3.9 | 推荐 3.11+ |
| uv | 最新版 | Python 包管理器 |
| Gemini API Key | — | 用于图片生成 |

---

## 🔧 安装步骤

### 1. 克隆项目

```bash
cd ~/Downloads
# 如果项目已存在，跳过此步
git clone <your-repo-url> wechat-article-generator
cd wechat-article-generator
```

### 2. 安装依赖

使用 `uv` 自动创建虚拟环境并安装依赖：

```bash
uv sync
```

> 💡 首次运行会自动创建 `.venv` 目录

### 3. 配置 API 密钥

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 Gemini API Key：

```env
# Gemini API Key (必填，用于图片生成)
GOOGLE_API_KEY=your_api_key_here
```

> 🔐 获取 API Key：访问 [Google AI Studio](https://aistudio.google.com/apikey)

---

## 🚀 快速开始

### 方式一：通过 Antigravity Skill 触发（推荐）

直接对 AI 助手说：

```
写一篇关于 [主题] 的公众号文章
```

**示例**：
- "写一篇关于 [主题] 的公众号文章"
- "帮我写一篇介绍 Prompt Engineering 的微信文章"
- "生成我的世界的公众号文章"

AI 将自动执行完整流水线：创作 → 配图 → 审查 → 渲染 → 预览

---

### 方式二：手动执行脚本

#### 步骤 1：创作文章

按照 `persona/tech_fast_food.md` 中的写作规范创作 Markdown 文章，在需要插图的位置使用占位符：

```markdown
# 你的文章标题

这是第一段内容...

![Image](一个机器人在学习编程)

继续写作...
```

#### 步骤 2：生成 HTML

运行渲染脚本：

```bash
uv run python scripts/md_to_html.py your_article.md --preview
```

**命令行参数**：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入的 Markdown 文件 | (必填) |
| `-o, --output` | 输出 HTML 文件路径 | 与输入同名 |
| `--preview` | 完成后自动打开浏览器预览 | 否 |

**环境变量配置** (`.env` 文件)：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `GOOGLE_API_KEY` | Gemini API 密钥 | (必填) |
| `IMG_MODEL_NAME` | 图片生成模型 | `gemini-3-pro-image-preview` |
| `TEXT_MODEL_NAME` | 文本生成模型 | `gemini-3-pro-preview` |
| `IMAGE_RESOLUTION` | 图片分辨率 (1k/2k/4k) | `2k` |
| `ENABLE_SEARCH` | 启用 Google Search Grounding | `false` |

**示例**：

```bash
# 基本用法
uv run python scripts/md_to_html.py my_article.md --preview

# 指定输出路径
uv run python scripts/md_to_html.py my_article.md -o output/final.html
```

> 💡 如需修改图片分辨率或启用搜索，请编辑 `.env` 文件而非使用命令行参数

#### 步骤 3：复制到公众号

1. 打开生成的 HTML 文件
2. 点击右上角「一键复制」按钮
3. 前往微信公众号后台，`Ctrl+V` 粘贴

---

## 📁 项目结构

```
wechat-article-generator/
├── .env                    # 环境变量配置 (API Key)
├── .env.example            # 环境变量模板
├── SKILL.md                # Skill 触发说明
├── README.md               # 本文档
├── pyproject.toml          # Python 项目配置
│
├── persona/
│   └── tech_fast_food.md   # "科技速食" 写作人设 Prompt
│
├── scripts/
│   └── md_to_html.py       # 核心渲染脚本
│
├── templates/
│   └── wechat_style.css    # 微信公众号样式表
│
├── assets/                 # AI 生成的图片缓存
└── images/                 # 手动添加的图片素材
```

---

## 🎨 自定义写作人设

编辑 `persona/tech_fast_food.md` 可自定义写作风格：

- **开篇风格**：新闻锚点 or 金句开场
- **段落节奏**：极短段落，1-3 句
- **重点突出**：加粗、符号包裹
- **结尾三件套**：金句 + 预告 + 互动

---

## 🔍 敏感词审查

以下词汇会被自动替换以避免平台限流：

| 敏感词 | 替换为 |
|--------|--------|
| 自动化 | 智能联动 |
| 股票/炒股 | 权益资产 |
| 赚钱/暴富 | 获取收益 |
| 翻墙/VPN | 跨境访问 |
| 微信/公众号 | 平台/内容生态 |
| 抖音 | 短视频平台 |
| 小红书 | 种草平台 |

> 完整清单见 `SKILL.md`

---

## ❓ 常见问题

### Q1: 图片生成失败怎么办？

**检查项**：
1. `.env` 中是否配置了 `GOOGLE_API_KEY`
2. API Key 是否有 Gemini 3 Pro Image 模型的访问权限
3. 网络是否能正常访问 `generativelanguage.googleapis.com`

**回退方案**：脚本会自动使用 placeholder 图片，不影响文章生成

### Q2: 如何更换图片风格？

编辑 `scripts/md_to_html.py` 中的 `expand_prompt()` 函数：

```python
sys_prompt = """
你是一个专业的 AI 绘画提示词专家...
风格: 现代极简主义插画，平面风格，柔和暖色调(Morandi colors)
"""
```

修改风格描述即可切换为：
- 赛博朋克风格
- 水彩插画风格
- 3D 等距视角
- 等等...

### Q3: 粘贴到公众号后样式丢失？

确保使用「一键复制」按钮，而非手动 `Ctrl+A` 全选。

脚本已将所有 CSS 样式内联（inline），确保微信编辑器能正确识别。

---

## 📞 技术支持

如遇问题，请提供以下信息：

1. 运行命令
2. 完整报错日志
3. Python 版本 (`python --version`)
4. uv 版本 (`uv --version`)

---

**Happy Writing! ✍️**
生成效果可看微信公众号
![70a86a2398fff3c609f2fa6d81fc4db3](https://github.com/user-attachments/assets/740eec46-ec95-43c7-9aee-5329de3a463b)
