# Claude Desktop Multi-Account & Continuity Hub for Windows

A native Windows desktop companion for the official **Claude Desktop** app that provides seamless **1-click multi-account switching** and an **80% token limit handoff assistant** to transfer active chat contexts across accounts without losing work.

---

## ✨ Features

- **⚡ 1-Click Seamless Account Switching**: Switch between multiple Claude accounts in the official Claude Desktop Windows app without re-authenticating every time.
- **📋 80% Token Limit / Session Handoff Assistant**:
  1. One-click copy for an optimized context summary prompt when approaching chat or usage limits.
  2. One-click swap to the alternate account with the continuation prompt pre-formatted and ready on your clipboard (`Ctrl+V`).
- **🔍 Real-Time Account Detection**: Polls live session UUIDs every 1.5s to automatically detect manual logins or account changes without desync.
- **🔒 Isolated & Permanent Local Profiles**: Each account's session tokens, IndexedDB, and cookies are stored securely on your local disk (`native_profiles/`).
- **🛡️ Reboot & Lock Safe**: Graceful process termination with lock-check retries to prevent corrupted session databases (`WinError 32`).
- **🎨 Modern Dark Mode GUI**: Built with CustomTkinter.

---

## 📋 Prerequisites

- **Windows 10 / 11 (64-bit)**
- **Official Claude Desktop for Windows** (installed via Microsoft Store or Anthropic installer)
- **Python 3.10+** (ensure `Add python.exe to PATH` is checked during installation)

---

## 🚀 Quick Start Guide

### 1. Clone the Repository
```bash
git clone https://github.com/rezkiyasser31-ship-it/claude-desktop-multi-account.git
cd claude-desktop-multi-account
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch the Application
Run via Python or double-click `Claude-Multi-Hub.bat`:
```bash
python app.py
```
*(On first run, the app automatically creates a clean `config.json` with two placeholder accounts ready for setup).*

---

## ⚙️ Initial Account Setup (2 Minutes)

When launching the app for the first time, your account cards will show **`○ Not Saved Yet`**:

1. **Set Up Account 1**:
   - Click the blue **`Set Up / Log In`** button on Account 1.
   - Claude Desktop will open in a fresh login state.
   - Sign in with your first Google / Claude account.
   - Return to the Hub and click **`📸 Snapshot Current Login`**.
   - Account 1 is now permanently saved!

2. **Set Up Account 2**:
   - Click **`Set Up / Log In`** on Account 2.
   - Claude Desktop will open in a clean login state (your Account 1 session is safely preserved).
   - Sign in with your second Google / Claude account.
   - Return to the Hub and click **`📸 Snapshot Current Login`**.
   - Account 2 is now permanently saved!

3. **Add More Accounts**:
   - Click **`+ Add Account`** to add as many additional accounts as you need.

---

## 🔄 Recommended Workflow (Handoff Continuity)

When a conversation reaches its context limit or account session limit:

1. **Step 1**: Click **`📋 1. Copy Handoff Prompt`** in the Hub.
2. Paste it into your current Claude chat (`Ctrl+V`) and hit Enter. Claude will generate a structured, high-density summary of your conversation state and next steps.
3. Copy Claude's generated summary.
4. **Step 2**: Click **`⚡ 2. Switch & Resume in Account 2`** in the Hub.
   - The Hub will automatically swap profiles, relaunch Claude on the target account, and format the resume prompt onto your clipboard.
5. In the new Claude window, press **`Ctrl+V`** and hit Enter to continue right where you left off!

---

## 🔐 Privacy & Security

- **100% Local Storage**: All cookies, session databases, and authentication tokens are kept strictly on your local machine inside `native_profiles/`.
- **Zero Telemetry**: No credentials or personal data are ever sent over the network.
- **Git Protected**: `config.json` and all `native_profiles/` directories are explicitly ignored by `.gitignore` to prevent accidental credential leakage.

---

## 🛠️ Project Structure

```
├── app.py                  # Main CustomTkinter GUI application
├── native_switcher.py      # Core session swapper, lock management, and UUID detector
├── launcher.py             # Config management and browser fallback helpers
├── config.example.json     # Clean template configuration for new users
├── Claude-Multi-Hub.bat    # Portable Windows launcher batch file
├── launch.vbs              # Silent background launcher script
├── requirements.txt        # Python package dependencies
├── .gitignore              # Protects personal profiles and credentials
├── LICENSE                 # MIT License
└── README.md               # Documentation
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
