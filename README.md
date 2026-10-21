# Data Science Digital Library (DS-Lab)

A digital learning platform and library for Data Science students at Mohan Babu University (MBU).

## 🚀 Features

- **Live Interactive Python Compiler**: Edit and execute Python notebook cells directly in the browser with persistent variables, rich DataFrame tables, and inline Matplotlib/Seaborn plots.
- **Hybrid Execution Engine**:
  - **⚡ Native Persistent Python Server (Recommended)**: Instant sub-10ms execution backed by local Python virtual environment (`server.py`).
  - **🌐 In-Browser WebAssembly (Pyodide)**: Automatic zero-install fallback when deployed as a static site or running standalone.

## 📁 Project Structure

```text
├── index.html       # Main webpage structure and experiment runner UI
├── style.css        # Responsive modern design system and code/plot styling
├── script.js        # Hybrid execution engine (Native + Pyodide) and router
├── server.py        # High-performance persistent Python execution server
├── iris.csv         # Offline dataset for data science and visualization experiments
├── mbu-logo.png     # University logo
├── photo.png        # Profile display
└── pdfs/            # PDF lab manuals and experiment documents
```

## 💻 Getting Started

### Option 1: Native Persistent Python Server (Instant ⚡ Execution)

To enjoy blazing-fast 10ms execution with full access to NumPy, Pandas, Matplotlib, and Seaborn:

```bash
# 1. Create and activate virtual environment (first time only)
python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy matplotlib seaborn

# 2. Run the persistent execution server
python3 server.py 8000
```

Then visit **`http://localhost:8000`** in your browser. The status badge will show **`Native Python (Local Server · Instant ⚡)`**.

### Option 2: Static / In-Browser WebAssembly

You can also run a standard static server:

```bash
python3 -m http.server 8000
```

The application will automatically detect that no local execution backend is active and fall back to the in-browser WebAssembly engine!

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
