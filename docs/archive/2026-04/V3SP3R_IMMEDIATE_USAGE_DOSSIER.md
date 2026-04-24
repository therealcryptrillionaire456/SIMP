# V3SP3R - AI Brain for Flipper Zero
## Complete Immediate Usage Dossier

**Repository Location**: `../V3SP3R/` (parent directory of current SIMP repo)  
**Status**: Production-ready Android application  
**License**: GPL-3.0  
**Author**: Elder Plinius  
**GitHub**: https://github.com/elder-plinius/V3SP3R

---

## 🚀 EXECUTIVE SUMMARY

V3SP3R (codename "Vesper") is an **Android application** that transforms your **Flipper Zero** into an **AI-powered command center** controlled entirely through **natural language**. It connects via **Bluetooth Low Energy (BLE)** to your Flipper Zero and uses **OpenRouter AI models** to execute commands, analyze signals, and manage hardware operations.

### Core Value Proposition
- **No menus, no manuals** - Just talk to your Flipper Zero like it's your partner-in-hacking
- **Instant expertise** - Don't memorize SubGHz protocols or IR formats
- **Real-time control** - AI reads Flipper's state, executes commands, reports back in seconds
- **Multimodal input** - Voice commands, photo analysis, text chat
- **Safety-first architecture** - Every action risk-classified, destructive ops require confirmation

---

## ⚡ IMMEDIATE STARTUP (5-MINUTE SETUP)

### 1. PREREQUISITES CHECKLIST
- [ ] **Flipper Zero device** (charged, firmware updated via qFlipper)
- [ ] **Android phone/tablet** (Android 8.0+, API 26+)
- [ ] **OpenRouter account** (free at [openrouter.ai](https://openrouter.ai))
- [ ] **$5-10 credit** added to OpenRouter account (most conversations cost pennies)
- [ ] **Bluetooth enabled** on both devices

### 2. BUILD & INSTALL (3 OPTIONS)

#### **Option A: Android Studio (Recommended)**
```bash
git clone https://github.com/elder-plinius/V3SP3R.git
cd V3SP3R
# Open in Android Studio
# Build > Build APK(s)
# Install app-debug.apk to device via USB debugging or file transfer
```

#### **Option B: Command Line (No Android Studio)**
```bash
git clone https://github.com/elder-plinius/V3SP3R.git
cd V3SP3R
./gradlew assembleDebug
# APK output: app/build/outputs/apk/debug/app-debug.apk
# Transfer to Android device and install
```

#### **Option C: Pre-built APK**
Check GitHub Releases for pre-built APK if available.

### 3. FIRST-TIME SETUP (2 MINUTES)
1. **Grant Permissions**:
   - Bluetooth (required)
   - Location (required for BLE scanning on Android)
   - Notifications (optional, for status updates)

2. **Add API Key**:
   - Settings → paste your OpenRouter API key (`sk-or-...`)
   - Get key from [openrouter.ai/keys](https://openrouter.ai/keys)

3. **Connect Device**:
   - Device tab → Scan → tap your Flipper Zero
   - Ensure Flipper Bluetooth is ON (Settings > Bluetooth)

4. **Start Chatting**:
   - Chat tab → begin natural language commands
   - First command: **"Show me my SD card contents"**

---

## 🎯 CORE FUNCTIONALITY

### COMMAND CATALOG - What You Can Do

```
Voice/Text Commands → AI Interpretation → Flipper Execution → Results
```

#### **File Operations**
- "Show me my SubGHz captures"
- "Read my garage remote file"
- "Create backup of all IR remotes"
- "Delete test folder"
- "Move file from /ext/subghz to /ext/backup"

#### **Hardware Control**
- "Transmit garage signal" (SubGHz)
- "Send TV power command" (IR)
- "Emulate my office badge" (NFC/RFID)
- "Run BadUSB script"
- "Turn on green LED"
- "Start vibration motor"

#### **Device Management**
- "What's my battery level?"
- "Show storage usage"
- "Launch SubGHz app"
- "Get firmware version"
- "List installed applications"

#### **Payload Generation**
- "Generate BadUSB script for reverse shell"
- "Create 315MHz garage remote"
- "Make NEC IR power button"
- "Generate NFC tag for door access"

### RISK & SAFETY SYSTEM

| Risk Level | Actions | User Interaction |
|------------|---------|------------------|
| **LOW** | `list_directory`, `read_file`, `get_device_info`, `get_storage_info` | Auto-execute |
| **MEDIUM** | `write_file` (existing files), `create_directory`, `copy` | Show diff preview |
| **HIGH** | `delete`, `move`, `rename`, `write_file` (new scope), `push_artifact` | Hold-to-confirm (1.5s) |
| **BLOCKED** | Operations on `/int/`, firmware paths, sensitive extensions | Requires Settings unlock |

---

## 🔥 ADVANCED FEATURES

### SMART GLASSES INTEGRATION (Mentra Bridge)
```bash
cd mentra-bridge
npm install && npm run build && npm start
# Default: http://localhost:8089
```
**In Vesper Settings**:
- Enable "Smart Glasses"
- Enter bridge URL (local or deployed)
- Set `MENTRA_API_KEY` env var for native SDK integration

**Features**:
- **Hands-free voice commands** via glasses
- **Camera photo analysis** - "What am I looking at?"
- **Wake word**: "Hey Vesper" or "Hey Vesper, [command]"
- **TTS responses** through glasses speakers
- **Vision triggers**: "Take a photo of this remote"

### SIGNAL ALCHEMY LAB
- **Visual waveform editor** with real-time preview
- **Layer and fuse** multiple signal patterns
- **Export directly** to Flipper's SD card
- **Custom RF signal synthesis** from scratch

### PAYLOAD LAB
- **AI-generated BadUSB scripts** with syntax validation
- **SubGHz signal creation** from specifications
- **IR remote generation** for any protocol
- **NFC tag emulation** data crafting
- **Validation before deployment** - AI checks format and safety

### FAPHUB BROWSER
- **Search Flipper app catalog** by name or category
- **One-tap install** to your device
- **Browse community resources** from GitHub
- **Direct download** of `.fap` files to `/ext/apps/`

### RESOURCE BROWSER
- **Search GitHub** for Flipper-compatible files
- **Browse repositories** and download directly
- **Community resource discovery** - signals, scripts, apps

---

## 🤖 AI INTEGRATION

### OPENROTER MODEL RECOMMENDATIONS

| Model | Best For | Speed | Cost | Recommendation |
|-------|----------|-------|------|----------------|
| **`nousresearch/hermes-4`** | Tool use, agent workflows | Fast | $$ | **Top pick** - purpose-built for agentic workflows |
| **`anthropic/claude-sonnet-4`** | Balance of speed/intelligence | Fast | $$ | **Great default** - reliable, capable |
| **`anthropic/claude-opus-4.6`** | Complex reasoning, multi-step ops | Medium | $$$$ | **Deep analysis** - when you need maximum capability |
| **`anthropic/claude-haiku-4`** | Simple commands, quick reads | Fastest | $ | **Speed demon** - for basic operations |
| **`openai/gpt-4o`** | General-purpose alternative | Fast | $$ | **Strong alternative** - good all-rounder |

**Our recommendation**: Start with **Hermes 4** or **Claude Sonnet 4** for daily use.

### COMMAND SCHEMA (execute_command)

```json
{
  "action": "write_file",
  "args": {
    "path": "/ext/subghz/garage.sub",
    "content": "Filetype: Flipper SubGhz Key File\nVersion: 1\nFrequency: 315000000\n..."
  },
  "justification": "User wants to change frequency from 390MHz to 315MHz",
  "expected_effect": "Update garage.sub file with new frequency"
}
```

#### **Available Actions (Full List)**:
- **File Operations**: `list_directory`, `read_file`, `write_file`, `create_directory`, `delete`, `move`, `rename`, `copy`
- **Device Info**: `get_device_info`, `get_storage_info`, `execute_cli`
- **Hardware Control**: `subghz_transmit`, `ir_transmit`, `nfc_emulate`, `rfid_emulate`, `ibutton_emulate`, `badusb_execute`, `led_control`, `vibro_control`
- **App Management**: `launch_app`, `search_faphub`, `install_faphub_app`
- **Payload & Artifacts**: `push_artifact`, `forge_payload`
- **Resources**: `browse_repo`, `download_resource`, `github_search`
- **Vision**: `request_photo`

---

## 🛠️ TROUBLESHOOTING QUICK REFERENCE

### **Flipper Not Found When Scanning**
1. **On Flipper**: Settings > Bluetooth > make sure it's ON
2. **Phone**: Toggle Bluetooth off/on
3. Ensure Flipper isn't connected to another device (e.g., qFlipper)
4. Move within 3 feet / 1 meter
5. Check Location permission is granted (required for BLE scanning on Android)

### **AI Not Responding**
1. Verify OpenRouter API key in Settings
2. Check credit balance at [openrouter.ai](https://openrouter.ai)
3. Test internet connection
4. Try a different model (Hermes 4 recommended)
5. Check OpenRouter status page for API issues

### **Build Failed in Android Studio**
1. Ensure JDK 17+ is installed
2. File > Sync Project with Gradle Files
3. Build > Clean Project > Rebuild Project
4. If still failing: close Android Studio, delete `.gradle` folder, reopen

### **"Could not parse tool arguments" Errors**
The AI model returned malformed JSON. Try:
1. Tap **Retry** on the error message
2. Switch to a recommended model (Hermes 4, Claude Sonnet 4)
3. Simplify your request
4. Vesper includes automatic JSON repair, but some models are more reliable

### **Permission Denied Errors**
- Some Flipper paths are protected by default (system files, firmware areas)
- Go to **Settings > Permissions** to unlock specific paths
- Enable **auto-approve** per risk tier to move faster
- Blocked paths always require manual unlock

---

## 🔒 SECURITY & COMPLIANCE

### **Safety Features**
- **All AI actions logged** and auditable in Audit screen
- **Destructive operations require confirmation** (hold-to-confirm 1.5s)
- **Protected system paths locked** by default (`/int/`, firmware areas)
- **Risk classification** before execution
- **No raw BLE access** from AI model - only structured commands
- **API keys stored** in encrypted DataStore

### **Legal Use**
- **Education and legitimate security research only**
- **Only use on devices you own** or have explicit authorization to test
- AI refuses clearly malicious requests
- **You are responsible** for complying with all applicable laws in your jurisdiction
- **All operations are logged** for accountability and review

### **Security Boundaries**
- Never expose API keys or credentials
- Refuse requests to access `/int/` unless unlocked
- Warn before destructive operations
- Explain risks honestly
- AI cannot transmit RF signals directly - only prepare files

---

## 🏗️ ARCHITECTURE OVERVIEW

### **High-Level Architecture**
```
┌─────────────────────────────────────────┐
│          V3SP3R Android App             │
├─────────────────────────────────────────┤
│  UI Layer (Jetpack Compose + Hilt)      │
│  ├── Chat Screen (voice, images, text)  │
│  ├── Ops Center                         │
│  ├── Alchemy Lab & Payload Lab          │
│  ├── File Browser & FapHub              │
│  ├── Device & Settings Screens          │
│  └── Audit Screen                       │
├─────────────────────────────────────────┤
│  Domain Layer                           │
│  ├── VesperAgent (AI orchestration)     │
│  ├── CommandExecutor (risk enforcement) │
│  ├── RiskAssessor + PermissionService   │
│  ├── ForgeEngine (payload generation)   │
│  ├── DiffService + AuditService         │
│  └── Signal Processing                  │
├─────────────────────────────────────────┤
│  Data Layer                             │
│  ├── OpenRouterClient (LLM API)         │
│  ├── FlipperBleService (BLE transport)  │
│  ├── GlassesIntegration (Mentra bridge) │
│  ├── Room Database (chat + audit)       │
│  └── Encrypted DataStore (settings)     │
└─────────────────────────────────────────┘
```

### **Key Components**
- **`VesperAgent`**: Orchestrates conversation flow, manages state
- **`OpenRouterClient`**: Handles API calls with tool calling and JSON repair
- **`CommandExecutor`**: Processes commands with risk assessment and approval
- **`RiskAssessor`**: Classifies operations by risk level (Low/Medium/High/Blocked)
- **`PermissionService`**: Manages path-based, time-limited permissions
- **`FlipperBleService`**: BLE connection and GATT operations
- **`AuditService`**: Logs all actions for accountability

### **Risk Classification Flow**
```
Command Received
       │
       ▼
┌──────────────────┐
│  Risk Assessment │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌──────┐  ┌───────┐
│ LOW  │  │BLOCKED│──────────► Reject with reason
└──┬───┘  └───────┘
   │
   ▼
Execute immediately
   │
   └────────────────┐
                    │
    ┌───────────────┴───────────────┐
    │                               │
    ▼                               ▼
┌───────┐                       ┌──────┐
│MEDIUM │                       │ HIGH │
└───┬───┘                       └──┬───┘
    │                              │
    ▼                              ▼
Show diff                   Hold-to-confirm
    │                              │
    ▼                              ▼
User clicks               User holds button
"Apply"                      1.5 seconds
    │                              │
    └──────────────┬───────────────┘
                   │
                   ▼
              Execute command
                   │
                   ▼
              Log to audit
```

---

## 💻 DEVELOPMENT & CONTRIBUTION

### **Project Structure**
```
V3SP3R/
├── app/src/main/java/com/vesper/flipper/
│   ├── ai/                     # AI integration
│   │   ├── OpenRouterClient.kt # LLM API, tool calling, JSON repair
│   │   ├── VesperAgent.kt      # Conversation orchestrator
│   │   ├── VesperPrompts.kt    # System prompts
│   │   ├── PayloadEngine.kt    # Payload generation
│   │   └── FlipperToolExecutor.kt
│   ├── ble/                    # Bluetooth
│   │   ├── FlipperBleService.kt
│   │   ├── FlipperProtocol.kt
│   │   ├── FlipperFileSystem.kt
│   │   └── MarauderBridge.kt
│   ├── glasses/                # Smart glasses
│   │   ├── GlassesIntegration.kt
│   │   └── GlassesBridgeClient.kt
│   ├── voice/                  # Voice I/O
│   │   ├── SpeechRecognitionHelper.kt
│   │   └── ElevenLabsTtsService.kt
│   ├── domain/
│   │   ├── executor/           # Command execution & risk
│   │   ├── model/              # Data models
│   │   ├── service/            # Audit, diff, permissions
│   │   └── protocol/           # SubGHz, Pwnagotchi
│   ├── data/                   # Persistence & settings
│   ├── security/               # Input validation, sanitization
│   ├── ui/                     # Jetpack Compose screens
│   │   ├── screen/
│   │   ├── viewmodel/
│   │   ├── components/
│   │   └── theme/
│   └── widget/                 # Home screen widget
├── mentra-bridge/              # Smart glasses bridge server (Node.js)
├── docs/                       # Architecture docs, schemas
└── gradle/                     # Build configuration
```

### **Building for Release**
1. Create `local.properties` in project root:
```properties
RELEASE_STORE_FILE=../keystore/vesper-release.jks
RELEASE_STORE_PASSWORD=your_store_password
RELEASE_KEY_ALIAS=vesper
RELEASE_KEY_PASSWORD=your_key_password
```

2. Build signed APK:
```bash
./gradlew assembleRelease
# APK: app/build/outputs/apk/release/app-release.apk
```

### **Dependencies**
- **Jetpack Compose**: Modern declarative UI
- **Hilt**: Dependency injection
- **Room**: Local database for audit logs
- **DataStore**: Encrypted preferences storage
- **OkHttp**: Network requests to OpenRouter
- **Kotlinx Serialization**: JSON parsing
- **java-diff-utils**: Diff computation for file changes

### **Areas Needing Contribution**
- iOS version (SwiftUI)
- Signal format parsers (new protocols)
- Additional payload templates
- UI/UX improvements
- Translations / i18n
- Test coverage

---

## 🎮 IMMEDIATE USE CASES

### **1. Remote Control Audit & Management**
```
"Show me all SubGHz files"
→ "Read each file and tell me frequencies"
→ "Identify duplicates"
→ "Create organized backup in /ext/backup/"
→ "Delete old test files"
```

### **2. Complete Device Inventory**
```
"Get battery level and health"
→ "Check storage usage by folder"
→ "List all installed .fap applications"
→ "Export report to /ext/reports/inventory.txt"
→ "Suggest cleanup based on usage"
```

### **3. Signal Analysis & Recreation**
```
"Take photo of this remote control"
→ AI identifies remote type and protocol
→ "Generate matching IR file"
→ "Test transmission"
→ "Save to /ext/infrared/living_room_tv.ir"
```

### **4. Payload Deployment Workflow**
```
"Generate BadUSB script for WiFi audit"
→ AI validates syntax and safety
→ "Push to /ext/badusb/wifi_audit.txt"
→ "Execute script"
→ "Monitor results and log output"
```

### **5. Hands-Free Field Operation**
```
"Hey Vesper, what's my battery level?"
→ "Hey Vesper, transmit garage signal"
→ "Hey Vesper, take photo of this device label"
→ "Hey Vesper, generate IR code for this AC unit"
→ "Hey Vesper, save everything to project folder"
```

### **6. Educational Security Research**
```
"Show me NFC dump structure"
→ "Explain MIFARE Classic vulnerabilities"
→ "Generate proof-of-concept attack"
→ "Test on lab device (owned/authorized)"
→ "Document findings in /ext/research/"
```

---

## 📋 QUICK COMMAND CHEAT SHEET

### **Basic Navigation**
```
"Show files in /ext/subghz"
"Read /ext/subghz/garage.sub"
"List all IR remotes"
"What's in /ext/nfc?"
```

### **File Operations**
```
"Create folder /ext/backup"
"Copy garage.sub to /ext/backup/"
"Rame old_capture.sub to garage_v2.sub"
"Delete /ext/test/ folder"
```

### **Hardware Control**
```
"Transmit garage signal"
"Send TV power command"
"Emulate office badge"
"Run BadUSB script login_backdoor.txt"
"Turn on blue LED"
```

### **Device Management**
```
"What's my battery level?"
"Show storage usage"
"Launch SubGHz app"
"Get firmware version"
"Reboot device"
```

### **Payload Generation**
```
"Generate BadUSB script to open cmd"
"Create 315MHz garage remote"
"Make NEC IR power button for Samsung TV"
"Generate NFC tag with URL https://example.com"
```

### **Smart Features**
```
"Take photo and identify remote type"
"Hey Vesper, scan for Bluetooth devices"
"Install WiFi scanner from FapHub"
"Search GitHub for Flipper game"
"Analyze this signal capture"
```

---

## 🚨 TROUBLESHOOTING DETAILED

### **BLE Communication Issues**
1. **Flipper not advertising**:
   - Ensure Bluetooth is ON in Settings
   - Restart Flipper Zero
   - Check Flipper isn't in "sleep" mode

2. **Connection drops**:
   - Move closer (BLE range ~10m optimal)
   - Avoid interference (microwaves, other 2.4GHz devices)
   - Check Flipper battery (low battery reduces BLE power)

3. **Pairing failures**:
   - Clear paired devices on both Flipper and phone
   - Re-pair from scratch
   - Check Android Bluetooth stack updates

### **OpenRouter API Issues**
1. **Rate limiting**:
   - Free tier: 100 requests/day
   - Paid: 60 requests/minute
   - Check usage at openrouter.ai/account

2. **Model availability**:
   - Some models may be temporarily unavailable
   - Check status.openrouter.ai
   - Switch to alternative model

3. **Cost management**:
   - Hermes 4: ~$0.001 per request
   - Claude Sonnet: ~$0.003 per request
   - Set budget alerts at openrouter.ai/account

### **File System Permissions**
**Protected Paths (require unlock)**:
- `/int/` - Internal storage (firmware, system)
- `/ext/update/` - Firmware updates
- Files with extensions: `.key`, `.priv`, `.secret`, `.cert`

**To unlock**:
1. Settings > Permissions
2. Tap path to unlock
3. Set duration (1 hour, 24 hours, permanent)
4. Confirm with device PIN/pattern if set

---

## 📊 PERFORMANCE OPTIMIZATION

### **For Faster Responses**
1. **Use Haiku model** for simple file operations
2. **Batch related commands** in single request
3. **Enable auto-approve** for Low/Medium risk in Settings
4. **Use text input** instead of voice for complex commands
5. **Pre-unlock frequently used paths**

### **Memory & Battery**
1. **Close other BLE apps** while using Vesper
2. **Disable "always scan"** in Settings when not needed
3. **Use dark theme** to save OLED battery
4. **Clear audit logs** periodically if storage constrained
5. **Export logs** to SD card and clear

### **Network Optimization**
1. **Use WiFi** instead of cellular for OpenRouter calls
2. **Enable compression** in OpenRouter API settings
3. **Cache frequent responses** (planned feature)
4. **Use local LLM** option if available (future)

---

## 🔮 FUTURE ROADMAP (Based on Code Analysis)

### **Planned Features (Code References)**
- **Local LLM integration** - On-device model support
- **Signal library** - Community-shared signal database
- **Automated workflows** - Scriptable command sequences
- **Cross-platform** - iOS/SwiftUI version
- **Plugin system** - Third-party tool integrations
- **Offline mode** - Basic functionality without internet

### **Integration Opportunities with SIMP**
1. **Vesper as SIMP Agent** - Expose Flipper control via SIMP broker
2. **SIMP Task Automation** - Schedule Flipper operations via SIMP orchestration
3. **Shared Audit Logs** - Integrate Vesper audit with SIMP security audit
4. **Cross-Agent Workflows** - Vesper + QuantumArb + KashClaw coordinated operations

---

## 📞 SUPPORT & COMMUNITY

### **Official Channels**
- **GitHub Repository**: https://github.com/elder-plinius/V3SP3R
- **Issues**: GitHub Issues for bugs and feature requests
- **Discussions**: GitHub Discussions for community support
- **Security Reports**: See SECURITY.md for responsible disclosure

### **Documentation**
- **README.md** - Quick start and overview
- **docs/architecture.md** - Technical architecture
- **docs/execute_command_schema.json** - Full API specification
- **docs/vesper_system.txt** - AI system prompt

### **Contributing**
1. Read CONTRIBUTING.md
2. Fork repository
3. Create feature branch
4. Submit pull request
5. Join discussions

### **License**
- **GPL-3.0** - Open source, copyleft
- **Commercial use** requires compliance with license terms
- **Attribution** required for derivatives

---

## 🎯 NEXT STEPS - IMMEDIATE ACTION PLAN

### **Phase 1: Setup (10-15 minutes)**
1. [ ] **Clone repository**: `git clone https://github.com/elder-plinius/V3SP3R.git`
2. [ ] **Build APK**: Use Android Studio or `./gradlew assembleDebug`
3. [ ] **Install on Android**: Transfer and install APK
4. [ ] **Get OpenRouter key**: Sign up at openrouter.ai, add $5 credit
5. [ ] **Connect Flipper**: Enable Bluetooth, pair devices

### **Phase 2: First Commands (5 minutes)**
1. [ ] **Test basic file ops**: "Show me SD card contents"
2. [ ] **Check device info**: "What's my battery level?"
3. [ ] **Explore signals**: "List SubGHz captures"
4. [ ] **Test transmission**: "Transmit first signal" (if available)

### **Phase 3: Advanced Usage (15-30 minutes)**
1. [ ] **Generate payload**: "Create BadUSB script for notepad"
2. [ ] **File management**: "Organize my IR remotes"
3. [ ] **Install apps**: "Find and install WiFi scanner"
4. [ ] **Smart glasses**: Set up Mentra bridge (optional)

### **Phase 4: Integration (Future)**
1. [ ] **SIMP integration**: Expose as SIMP agent
2. [ ] **Automated workflows**: Schedule operations
3. [ ] **Cross-agent coordination**: Combine with QuantumArb, KashClaw
4. [ ] **Enterprise features**: Team management, compliance reporting

---

## ✅ FINAL CHECKLIST BEFORE FIRST USE

### **Pre-Flight Checklist**
- [ ] Flipper Zero charged and firmware updated
- [ ] Android device with Android 8.0+
- [ ] OpenRouter account with API key and credits
- [ ] APK built and installed
- [ ] Bluetooth enabled on both devices
- [ ] Location permission granted on Android

### **First Session Goals**
- [ ] Connect to Flipper successfully
- [ ] Execute first command: "list_directory /ext"
- [ ] Read a file: "read_file /ext/subghz/example.sub"
- [ ] Get device info: "get_device_info"
- [ ] Transmit a signal (if available)

### **Success Metrics**
- ✅ AI responds within 2-3 seconds
- ✅ Commands execute successfully
- ✅ Results are accurate and useful
- ✅ Risk system works (diffs for writes, confirm for deletes)
- ✅ Audit log captures all actions

---

**V3SP3R** - Your Flipper Zero just got an AI brain upgrade. Talk to your hardware like it's your partner-in-hacking.

*Last Updated: 2026-04-20*
*Based on repository analysis of ../V3SP3R/*