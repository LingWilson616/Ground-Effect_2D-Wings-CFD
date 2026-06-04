# 近地翼片 2D-CFD 仿真

FSAE 地面效应翼型二维 CFD 快速分析工具。

三维 CFD（Ansys、StarCCM+）计算速度过慢导致迭代周期过长，二维 CFD 实现快速验证。

## 🚀 AI CFD 助手（当前版本）

面向 AI 应用课程的 PySide6 桌面应用，集成 DeepSeek AI 对话与实时 CFD 可视化。

### 技术栈

| 层 | 技术 |
|---|---|
| GUI | PySide6 |
| AI | DeepSeek API |
| 可视化 | matplotlib |
| CFD 核心 | 面元法（Panel Method） |
| 翼型 | NACA 4/5 位生成器 |

### 快速开始

```bash
cd ai_cfd_assistant

# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（在 ai_cfd_assistant/.env）
DEEPSEEK_API_KEY=your_key_here

# 3. 运行
python main.py
```

### 功能

- 🤖 **AI CFD 专家对话** — 流式输出，Markdown 渲染，代码高亮
- 🪽 **翼型可视化** — NACA 4/5 位交互式生成
- 📊 **压力系数** — 实时面元法计算
- 🌊 **流线图** — 势流可视化
- 📂 **DAT 文件导入** — 支持 Profili 格式

---

## 🎯 完整 CFD 项目（规划中，4年路线）

| 阶段 | 内容 |
|---|---|
| 大一 | Python 原型 + GUI 框架 |
| 大二 | C++ 几何引擎 + Gmsh 网格 |
| 大三 | 有限体积法 + SIMPLE 求解器 |
| 大四 | k-ε RANS + 后处理 |

### 目标技术栈

| 层 | 技术 |
|---|---|
| 语言 | C++17/20 |
| GUI | Qt 6 + QGraphicsView |
| 网格 | Gmsh |
| 求解器 | 自研 FVM + SIMPLE + k-ε |
| 线性代数 | Eigen |
| 数据格式 | VTK/VTU |

---

## 📄 License

MIT License
