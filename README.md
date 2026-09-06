# AssHole-Engine
A Wi-Fi remote control for your PC. The bigger the hole, the more control you get. More control = more leakage = more bugs.

Bilkul 😂 Neeche **full GitHub `README.md`** ready hai. Meme artwork ke liye `assets/artwork.png` aur UI screenshots ke liye `assets/pc-dashboard.png` / `assets/webui.png` assume kiye hain.

# 🕳️ ASSHOLE DECK

> **Your PC. Your phone. One unnecessarily powerful asshole.**

A local Wi-Fi remote control system that lets you control your PC from your phone using a browser-based WebUI.

No app installation on the phone.
No cloud server.
No account.
Just connect to the same network, scan the QR code, and start controlling your PC.

Because apparently... **a keyboard and mouse weren't enough.** 💀

---

## 😂 Why does this exist?

I wanted to control my PC from my phone.

So instead of making a simple remote...

I made **ASSHOLE DECK**.

Because why make one button when you can make an entire dashboard that controls almost everything?

---

## 🖼️ The Artwork

<p align="center">
  <img src="assets/artwork.png" alt="ASSHOLE DECK Artwork" width="600">
</p>

> **The bigger the hole, the bigger the control.** 🕳️

---

# 📸 Screenshots

## 🖥️ PC Dashboard

The desktop application runs a local Flask server and provides a control dashboard on your PC.

<p align="center">
  <img src="assets/pc-dashboard.png" alt="ASSHOLE DECK PC Dashboard" width="700">
</p>

---

## 📱 WebUI

Open the WebUI from any device connected to the same local network.

<p align="center">
  <img src="assets/webui.png" alt="ASSHOLE DECK WebUI" width="700">
</p>

---

# 🤨 What can this thing actually do?

Quite a lot.

Maybe too much.

---

## 🎛️ PC Remote Control

Control your PC directly from your phone.

### 🖱️ Mouse Control

* Move mouse
* Left click
* Right click
* Mouse actions
* Touch-based interaction
* Remote pointer control

Basically:

> **Phone = mouse with commitment issues.**

---

## ⌨️ Keyboard Control

Send keyboard actions from the WebUI to the PC.

Supports things like:

* Normal keyboard input
* Special keys
* Enter
* Escape
* Backspace
* Space
* Arrow keys
* Modifier keys
* Keyboard shortcuts

Your phone can now pretend to be a keyboard.

Your actual keyboard is probably offended.

---

# 🔊 Soundboard

Play sound effects **locally on the PC**.

The audio is played by the desktop application using `pygame`.

The phone is only the controller.

### Soundboard features

* Play sounds
* Stop sounds
* Pause sounds
* Resume sounds
* Loop playback
* Volume control
* Sound folders
* Custom sound files
* Soundboard management

So you can sit on your bed and remotely make your PC go:

> **BONK** 🔊

---

# 🎵 Media Controls

Control media playback from your phone.

Available controls can include:

* ▶️ Play
* ⏸️ Pause
* ⏹️ Stop
* ⏭️ Next
* ⏮️ Previous
* 🔊 Volume
* 🎚️ Media controls

Your phone becomes the remote.

Your PC becomes the victim.

---

# 📂 Media & File Browser

Browse configured media folders from the WebUI.

You can:

* Browse folders
* View files
* Open files
* Access media
* Download files
* Navigate directories

Because getting up from your chair is apparently unacceptable.

---

# 🚀 Application Launcher

Launch applications on your PC directly from your phone.

Create your own application shortcuts.

For example:

```text
🎮 Steam
🌐 Chrome
💬 Discord
🎨 Photoshop
📝 Notepad
```

Add whatever application you want.

One tap.

One launch.

Zero walking.

---

# 🔗 Custom Shortcuts

Create custom shortcuts for websites, applications, commands, or other useful actions.

Your dashboard can become your own personal control center.

Or an unnecessarily complicated Start Menu.

Your choice.

---

# 📸 Screenshot

Capture your PC screen remotely.

Useful when you want to quickly see what's happening on the PC without physically checking it.

Because sometimes:

> "What is my PC doing?"

is a legitimate question.

---

# ☀️ Brightness Control

Control screen brightness remotely.

Useful for:

* Night usage
* Dark rooms
* Media playback
* Saving your eyes
* Being lazy

Mostly being lazy.

---

# 🔊 PC Volume / System Controls

Control supported system functions directly from the WebUI.

The goal is simple:

> **Move less. Control more.**

---

# 📱 QR Code Connection

When the desktop application starts, it displays a QR code containing the local WebUI address.

Scan it with your phone.

Open the WebUI.

Done.

### Typical flow

```text
PC starts
   ↓
ASSHOLE DECK starts
   ↓
Local Flask server starts
   ↓
QR code appears
   ↓
Scan with phone
   ↓
WebUI opens
   ↓
Control PC
```

No typing IP addresses manually.

No unnecessary suffering.

---

# 📡 Local Network

ASSHOLE DECK is designed to work over your local network.

The PC runs the server:

```text
0.0.0.0:5000
```

Your phone connects using the PC's local IP address.

Example:

```text
http://192.168.1.100:5000
```

Both devices need to be reachable on the same network.

---

# 🧠 How It Works

The project uses a Python desktop application together with a browser-based control interface.

```text
                 📱 PHONE
                    │
                    │ Wi-Fi
                    ▼
             🌐 Web Browser
                    │
                    │ Socket.IO / HTTP
                    ▼
          🖥️ ASSHOLE DECK SERVER
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
       PyAutoGUI  pygame    System
          │         │         │
          ▼         ▼         ▼
        Mouse    Sound     Controls
```

The phone does **not** directly control the hardware.

The Python application receives commands and performs the actions on the PC.

---

# 🧰 Built With

| Technology                   | Purpose                     |
| ---------------------------- | --------------------------- |
| 🐍 Python                    | Core application            |
| 🌐 Flask                     | Web server                  |
| 🔌 Flask-SocketIO            | Real-time communication     |
| 🖱️ PyAutoGUI                | Mouse & keyboard automation |
| 🔊 pygame                    | Local audio playback        |
| 🖼️ Pillow                   | Image handling              |
| 📱 Tkinter                   | Desktop dashboard           |
| 📷 QRCode                    | QR code generation          |
| ☀️ screen_brightness_control | Brightness control          |
| 📡 Wi-Fi/LAN                 | Device communication        |
| 📦 PyInstaller               | Windows executable          |

---

# 📁 Project Structure

```text
ASSHOLE-DECK/
│
├── main.py
├── index.html
├── README.md
├── requirements.txt
├── icon.ico
│
├── assets/
│   ├── artwork.png
│   ├── pc-dashboard.png
│   └── webui.png
│
├── media/
│
├── sounds/
│
└── config.json
```

---

# ⚙️ Configuration

ASSHOLE DECK stores configurable settings such as:

* Screenshot location
* Soundboard location
* Soundboard volume
* Media folders
* Custom applications
* Custom shortcuts
* Built-in controls

Example configuration:

```json
{
    "soundboard_volume": 1.0,
    "media_folders": [],
    "custom_apps": [],
    "custom_shortcuts": []
}
```

Configure it according to your setup.

---

# 🚀 Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/ASSHOLE-DECK.git
```

Enter the directory:

```bash
cd ASSHOLE-DECK
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python main.py
```

The desktop dashboard should start and the local WebUI server will run.

---

# 📦 Build Windows EXE

Install PyInstaller:

```bash
pip install pyinstaller
```

Build the application:

```bash
pyinstaller --clean --onefile --noconsole --icon=icon.ico --add-data "index.html;." --hidden-import=engineio.async_drivers.threading --hidden-import=flask_socketio main.py
```

The executable will appear inside:

```text
dist/
```

---

# 🖥️ Windows EXE

After building:

```text
dist/
└── main.exe
```

Rename it to something more respectable:

```text
ASSHOLE-DECK.exe
```

Because `main.exe` is boring.

---

# 🔐 Security

ASSHOLE DECK is intended for **your own PC and trusted local networks**.

The application can perform powerful actions such as:

* Keyboard input
* Mouse control
* Application launching
* File access
* Media control
* Sound playback

Therefore, **do not expose the WebUI directly to the public internet** without implementing proper authentication and security controls.

If someone gets unauthorized access to the WebUI...

Congratulations.

You have accidentally created a remote-control nightmare. 💀

---

# ⚠️ Important

This project is provided for:

* Personal use
* Educational purposes
* Home automation
* Local PC control
* Experimentation
* Learning Python/WebSocket-based applications

Do not use it to access or control computers that you do not own or have explicit permission to control.

---

# 🐛 Known Limitations

Depending on your Windows configuration:

* Windows Firewall may block port `5000`
* Some applications may block simulated keyboard/mouse input
* Some applications require administrator privileges
* Media/file access depends on configured folders
* System controls may behave differently across Windows versions
* Port `5000` must be available

If something doesn't work:

```text
Don't panic.

Check the console.

Check the logs.

Then blame Windows.
```

---

# 🛠️ Troubleshooting

## WebUI doesn't open

Check that the server is running and try:

```text
http://127.0.0.1:5000
```

From another device:

```text
http://YOUR-PC-IP:5000
```

Example:

```text
http://192.168.1.10:5000
```

---

## Phone can't connect

Make sure:

* PC and phone are on the same network
* Windows Firewall allows the application
* Port `5000` is available
* The PC's local IP is correct
* The Flask server is running

---

## Sound isn't playing

Make sure:

* `pygame` is installed
* The sound file exists
* The selected sound format is supported
* Your PC audio output is working

Remember:

> **The audio plays on the PC, not inside the phone browser.**

---

# 🧪 Development

Run directly with Python:

```bash
python main.py
```

Modify:

```text
main.py
```

for the backend and:

```text
index.html
```

for the WebUI.

---

# 💡 Future Ideas

Possible future improvements:

* 🔐 Authentication
* 🔑 PIN protection
* 🌙 Better dark mode
* 🎨 Themes
* 📱 Better mobile UI
* 🔄 Automatic device discovery
* 📊 System monitoring
* 💻 CPU/RAM/GPU monitoring
* 🔋 Laptop battery information
* 📋 Clipboard sharing
* 📁 Better file manager
* 🎮 Game launcher
* 🎵 Better media player
* 🔊 More system audio controls
* 🖥️ Multiple monitor controls
* 👥 Multiple device support

And probably...

**more completely unnecessary buttons.**

---

# 🤝 Contributing

Found a bug?

Open an issue.

Have an improvement?

Make a pull request.

Made something completely cursed?

Definitely make a pull request.

---

# ⭐ Star This Project

If you like the project, give it a ⭐.

It doesn't improve the software.

It doesn't make it faster.

It doesn't fix bugs.

But it makes me feel important.

---

# 📜 License

This project is provided under the license included in this repository.

See:

```text
LICENSE
```

for details.

---

# ❤️ Credits

Built with:

🐍 Python
🌐 Flask
🔌 Socket.IO
🖱️ PyAutoGUI
🔊 pygame
🖼️ Pillow
📱 Tkinter

And an unhealthy amount of:

```text
"What if I add one more button?"
```

---

# 🕳️ Final Words

ASSHOLE DECK started with a simple question:

> **"Can I control my PC from my phone?"**

The reasonable answer was:

> "Yes, make a remote."

The answer I chose was:

> **"Let's build an entire control deck."**

And here we are.

---

<p align="center">

## 🕳️ THE BIGGER THE HOLE, THE BIGGER THE CONTROL.

### More control → More leakage → More bugs 💀

</p>

<p align="center">

**ASSHOLE DECK**

*Because your PC deserved a remote.*

</p>

