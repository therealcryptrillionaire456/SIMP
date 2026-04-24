# V3SP3R - QUICK START GUIDE
## Get Running in 10 Minutes

## 🚀 ULTRA-QUICK START

### 1. PREREQUISITES (2 min)
```bash
# You need:
# - Flipper Zero (charged, Bluetooth ON)
# - Android phone (Android 8.0+)
# - OpenRouter API key (free: openrouter.ai)
# - $5 credit on OpenRouter
```

### 2. BUILD APK (3 min)
```bash
# Option A: Command line
git clone https://github.com/elder-plinius/V3SP3R.git
cd V3SP3R
./gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk

# Option B: Android Studio
# Open project in Android Studio
# Build > Build APK(s)
```

### 3. INSTALL & SETUP (3 min)
1. **Install APK** on Android device
2. **Open Vesper**, grant permissions (Bluetooth, Location)
3. **Settings** → paste OpenRouter API key (`sk-or-...`)
4. **Device tab** → Scan → tap your Flipper Zero

### 4. FIRST COMMANDS (2 min)
```
"Show me my SD card"
"What's my battery level?"
"List SubGHz files"
"Read garage.sub file"
```

## 📱 CORE SCREENS

### **Chat** - Talk to your Flipper
- Voice or text input
- AI interprets, executes commands
- See results in conversation

### **Device** - Connection management
- Scan for Flipper
- Connection status
- Battery, storage info

### **Files** - Direct file browser
- Navigate SD card
- View/edit files
- Upload/download

### **Audit** - Action history
- All AI commands logged
- Filter by type/date
- Export for review

### **Settings** - Configuration
- API keys
- Permissions
- Risk preferences
- Smart glasses

## 🎯 TOP 10 COMMANDS TO START

1. **`"Show SD card"`** - List root directory
2. **`"Battery level"`** - Check device power
3. **`"List SubGHz"`** - View RF captures
4. **`"Read garage.sub"`** - Inspect remote file
5. **`"Create backup folder"`** - Make /ext/backup/
6. **`"Generate BadUSB script"`** - Create HID payload
7. **`"Transmit signal"`** - Send SubGHz/IR
8. **`"Install WiFi scanner"`** - Get from FapHub
9. **`"Take photo of remote"`** - Smart glasses only
10. **`"Export audit log"`** - Save action history

## ⚠️ RISK SYSTEM (QUICK GUIDE)

| Color | Risk | Action Required |
|-------|------|-----------------|
| 🟢 **Green** | Low | Auto-execute |
| 🟡 **Yellow** | Medium | Review diff, click Apply |
| 🔴 **Red** | High | Hold button 1.5s |
| ⚫ **Black** | Blocked | Unlock in Settings first |

**Protected paths** (need unlock):
- `/int/` - Internal storage
- Firmware areas
- `.key`, `.priv` files

## 🔧 TROUBLESHOOTING

### **Flipper Not Found**
1. Flipper: Settings → Bluetooth → ON
2. Phone: Toggle Bluetooth
3. Grant Location permission
4. Move closer (3 feet)

### **AI Not Responding**
1. Check OpenRouter API key
2. Verify credit balance
3. Try different model (Hermes 4)
4. Check internet connection

### **Permission Denied**
1. Go to Settings → Permissions
2. Unlock needed paths
3. Enable auto-approve for risk levels

## 🎮 SMART GLASSES (OPTIONAL)

```bash
cd mentra-bridge
npm install && npm run build && npm start
# In Vesper Settings: Enable glasses, enter URL
```

**Wake word**: "Hey Vesper"
**Photo analysis**: "What am I looking at?"
**Hands-free**: Voice commands through glasses

## 📞 SUPPORT

- **GitHub**: https://github.com/elder-plinius/V3SP3R
- **Issues**: Bug reports, feature requests
- **OpenRouter**: API key, credits, model status

## ✅ READY-TO-USE COMMAND SEQUENCES

### **Device Audit**
```
"Battery level"
"Storage usage"
"Firmware version"
"List installed apps"
"Export report to /ext/audit.txt"
```

### **Signal Management**
```
"List all SubGHz files"
"Read each file, show frequencies"
"Identify duplicates"
"Organize into /ext/subghz/by_frequency/"
"Delete test files"
```

### **Payload Creation**
```
"Generate BadUSB script: open cmd as admin"
"Validate syntax"
"Save to /ext/badusb/admin_cmd.txt"
"Test execution"
```

## 🎯 NEXT STEPS AFTER SETUP

1. **Explore your files** - See what's on your Flipper
2. **Test transmissions** - Try existing signals
3. **Generate payloads** - Create custom scripts
4. **Install apps** - Browse FapHub
5. **Set up glasses** - For hands-free use

---

**Time to first command**: ~10 minutes  
**Cost per conversation**: Pennies (OpenRouter)  
**Learning curve**: Minimal (natural language)

**Start with**: `"Show me what's on my Flipper"`