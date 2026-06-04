# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ground-effect Wing 2D-CFD — a 2D computational fluid dynamics GUI application for rapid aerodynamic analysis of FSAE front/side wings. The long-term goal is a full RANS k-ε CFD solver, but this will be built progressively over ~4 years.

Reference implementation: https://github.com/LingWilson616/Ground-Effect_2D-Wings-CFD

## Two Tracks

This repo serves two purposes:

1. **AI Assignment (`ai_cfd_assistant/`)** — PySide6 desktop app combining AI chat (DeepSeek) with real-time CFD visualization (panel method). This is the current deliverable, built in Python for speed.
2. **Full CFD Project (future)** — Complete C++/Qt CFD suite with geometry sketcher, mesh generation, RANS k-ε solver, and post-processing. This is the 4-year goal described in `prompt.txt`.

## Current Project: AI CFD Assistant

### Tech Stack
| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.8+ | Miniconda env at `C:/Users/14150/miniconda3/` |
| GUI | PySide6 6.6.3 | Qt for Python (LGPL) |
| AI API | DeepSeek | OpenAI-compatible, base URL `https://api.deepseek.com/v1` |
| Visualization | matplotlib 3.7 | Embedded in Qt via `FigureCanvasQTAgg` |
| CFD Core | Panel method | NACA 4/5-digit generator + 2D source/vortex panel method |
| Math | numpy, scipy | Linear algebra, interpolation |

### How to Run
```bash
# Set API key (create .env file in ai_cfd_assistant/)
echo "DEEPSEEK_API_KEY=sk-your-key" > ai_cfd_assistant/.env
# Or set environment variable: set DEEPSEEK_API_KEY=sk-your-key

# Install dependencies (proxy must be working or disabled)
pip install -r ai_cfd_assistant/requirements.txt

# Run
cd ai_cfd_assistant
python main.py
```

Note: System has a proxy configured at `127.0.0.1:7890`. If proxy software (Clash/V2Ray) is not running, pip/coda will fail. Temporarily disable via:
```powershell
powershell -Command "Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyEnable -Value 0"
# ... install ... then re-enable:
powershell -Command "Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyEnable -Value 1"
```

### Project Structure
```
ai_cfd_assistant/
├── main.py                  # Entry point, env loading
├── requirements.txt
├── .env.example
└── src/
    ├── main_window.py       # Main window: menus, toolbar, tree, workspace stack
    ├── chat_widget.py       # AI chat with streaming, markdown, code highlighting
    ├── viz_widgets.py       # matplotlib panels: airfoil shape, Cp, streamlines
    ├── ai_client.py         # DeepSeek API wrapper (streaming + chat)
    ├── cfd_core.py          # NACA generator + 2D panel method
    └── theme.py             # Dark QSS theme (~7000 chars)
```

### Architecture Notes
- **MainWindow** follows `prompt.txt` GUI spec: menu bar (文件/求解/帮助), toolbar (geometry tools), tree view (项目→几何/区域/网格/后处理/AI助手), stacked workspace, status bar, property dock
- **ChatWidget** uses `QThread` for streaming API calls, signals to update UI. Uses `markdown` + `pygments` for rendering.
- **VizPanel** has 3 tabs: airfoil profile (NACA interactive), pressure coefficient (panel method), streamlines
- **Panel method** uses source + vortex panels with Kutta condition. Currently produces reasonable Cl for cambered airfoils but Cp values need calibration. Thin airfoil theory (`2π·sin(α)`) serves as sanity check.
- **Python 3.8 compatibility**: All files use `from __future__ import annotations` for `str | None` syntax

## Full CFD Project (Future)

### Planned Tech Stack
| Layer | Choice |
|---|---|
| Language | C++17/20 |
| Build | CMake |
| GUI | Qt 6 + QGraphicsView |
| Geometry | Custom + Gmsh C++ API |
| Solver | FVM + SIMPLE/PISO + k-ε RANS |
| Mesh | Gmsh (structured + unstructured) |
| Linear Algebra | Eigen |
| Data Format | VTK/VTU |

### Requirements (from prompt.txt)
See `prompt.txt` for full Chinese-language spec. Key modules:
1. **Geometry** — 2D CAD sketcher, 3000×2000mm canvas, 10mm grid, Profili .dat import
2. **Regions** — BC assignment (velocity inlet, pressure outlet, walls), fluid properties
3. **Mesh** — Base size 100mm, min 0.1mm
4. **Post-processing** — Cp contour, total pressure contour, velocity streamlines, downforce
5. **AI Assistant** — Integrated CFD expert chatbot
