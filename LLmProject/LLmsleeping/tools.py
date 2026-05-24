"""
tools.py - ฟังก์ชันที่พิมเรียกใช้ได้
"""

import os
import sys
import subprocess
import webbrowser
import psutil
import glob
from pathlib import Path
from urllib.parse import quote


def open_path(path: str) -> str:
    """เปิดไฟล์/โฟลเดอร์"""
    try:
        shortcuts = {
            "desktop": str(Path.home() / "Desktop"),
            "เดสก์ทอป": str(Path.home() / "Desktop"),
            "หน้าจอ": str(Path.home() / "Desktop"),
            "documents": str(Path.home() / "Documents"),
            "เอกสาร": str(Path.home() / "Documents"),
            "downloads": str(Path.home() / "Downloads"),
            "ดาวน์โหลด": str(Path.home() / "Downloads"),
            "pictures": str(Path.home() / "Pictures"),
            "รูปภาพ": str(Path.home() / "Pictures"),
            "music": str(Path.home() / "Music"),
            "เพลง": str(Path.home() / "Music"),
            "videos": str(Path.home() / "Videos"),
            "วิดีโอ": str(Path.home() / "Videos"),
            "home": str(Path.home()),
        }
        path_lower = path.lower().strip()
        if path_lower in shortcuts:
            path = shortcuts[path_lower]

        path = os.path.expandvars(os.path.expanduser(path))
        if not os.path.exists(path):
            return f"❌ ไม่พบ: {path}"

        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
        return f"✅ เปิด {path} แล้ว"
    except Exception as e:
        return f"❌ เปิดไม่ได้: {e}"


def search_files(pattern: str, search_in: str = None) -> str:
    """ค้นหาไฟล์"""
    try:
        if search_in:
            search_dirs = [os.path.expandvars(os.path.expanduser(search_in))]
        else:
            home = Path.home()
            search_dirs = [str(home / "Desktop"), str(home / "Documents"), str(home / "Downloads")]

        found = []
        for d in search_dirs:
            if not os.path.exists(d):
                continue
            for f in glob.glob(os.path.join(d, "**", pattern), recursive=True):
                found.append(f)
                if len(found) >= 10:
                    break
            if len(found) >= 10:
                break

        if not found:
            return f"❌ ไม่พบไฟล์ '{pattern}'"
        result = f"✅ พบ {len(found)} ไฟล์:\n"
        for f in found[:10]:
            result += f"  • {f}\n"
        return result
    except Exception as e:
        return f"❌ ค้นหาไม่ได้: {e}"


def open_website(url: str) -> str:
    """เปิดเว็บ"""
    try:
        url = url.strip()
        # เว็บยอดฮิต
        common_sites = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "facebook": "https://www.facebook.com",
            "fb": "https://www.facebook.com",
            "twitter": "https://twitter.com",
            "x": "https://x.com",
            "github": "https://github.com",
            "gmail": "https://mail.google.com",
            "drive": "https://drive.google.com",
            "netflix": "https://www.netflix.com",
            "discord": "https://discord.com",
            "reddit": "https://reddit.com",
            "chatgpt": "https://chat.openai.com",
            "claude": "https://claude.ai",
        }
        if url.lower() in common_sites:
            url = common_sites[url.lower()]
        elif not url.startswith(("http://", "https://")):
            if "." not in url:
                url = f"https://www.google.com/search?q={quote(url)}"
            else:
                url = "https://" + url
        webbrowser.open(url)
        return f"✅ เปิด {url} แล้ว"
    except Exception as e:
        return f"❌ เปิดเว็บไม่ได้: {e}"


def search_youtube(query: str) -> str:
    """ค้นหาใน YouTube"""
    try:
        url = f"https://www.youtube.com/results?search_query={quote(query)}"
        webbrowser.open(url)
        return f"✅ ค้นหา '{query}' ใน YouTube แล้ว"
    except Exception as e:
        return f"❌ ค้นหาไม่ได้: {e}"


def search_google(query: str) -> str:
    """ค้นหาใน Google"""
    try:
        url = f"https://www.google.com/search?q={quote(query)}"
        webbrowser.open(url)
        return f"✅ ค้นหา '{query}' ใน Google แล้ว"
    except Exception as e:
        return f"❌ ค้นหาไม่ได้: {e}"


def run_program(program: str) -> str:
    """รันโปรแกรม"""
    try:
        program = program.strip().lower()
        aliases = {
            "notepad": "notepad.exe",
            "โน้ตแพด": "notepad.exe",
            "เครื่องคิดเลข": "calc.exe",
            "calc": "calc.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "mspaint": "mspaint.exe",
            "เพ้นท์": "mspaint.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "explorer": "explorer.exe",
            "task manager": "taskmgr.exe",
            "taskmgr": "taskmgr.exe",
            "control panel": "control.exe",
            "settings": "ms-settings:",
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "firefox": "firefox.exe",
            "vscode": "code",
            "vs code": "code",
            "discord": "discord.exe",
            "spotify": "spotify.exe",
            "steam": "steam.exe",
        }
        cmd = aliases.get(program, program)

        if sys.platform == "win32":
            if cmd.startswith("ms-settings:"):
                os.system(f"start {cmd}")
            else:
                subprocess.Popen(cmd, shell=True)
        else:
            subprocess.Popen(cmd, shell=True)
        return f"✅ เปิด {program} แล้ว"
    except Exception as e:
        return f"❌ เปิดไม่ได้: {e}"


def close_program(program: str) -> str:
    """ปิดโปรแกรม"""
    try:
        program = program.strip().lower()
        if not program.endswith(".exe"):
            program += ".exe"
        killed = 0
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == program:
                    proc.kill()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed > 0:
            return f"✅ ปิด {program} แล้ว ({killed} processes)"
        return f"❌ ไม่พบ {program} ที่ทำงานอยู่"
    except Exception as e:
        return f"❌ ปิดไม่ได้: {e}"


def system_status() -> str:
    """เช็คสถานะระบบ"""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None

        status = (
            f"📊 สถานะเครื่อง:\n"
            f"  CPU: {cpu}%\n"
            f"  RAM: {mem.percent}% ({mem.used // (1024**3)} / {mem.total // (1024**3)} GB)\n"
            f"  Disk: {disk.percent}% ({disk.used // (1024**3)} / {disk.total // (1024**3)} GB)"
        )
        if battery:
            status += f"\n  Battery: {battery.percent}%"
            if battery.power_plugged:
                status += " (ชาร์จอยู่)"
        return status
    except Exception as e:
        return f"❌ เช็คไม่ได้: {e}"


def control_media(action: str) -> str:
    """ควบคุม media"""
    try:
        if sys.platform != "win32":
            return "❌ รองรับเฉพาะ Windows"
        import ctypes
        VK_CODES = {
            "play_pause": 0xB3, "next": 0xB0, "previous": 0xB1,
            "volume_up": 0xAF, "volume_down": 0xAE, "mute": 0xAD,
        }
        code = VK_CODES.get(action)
        if code is None:
            return f"❌ ไม่รู้จักคำสั่ง {action}"
        ctypes.windll.user32.keybd_event(code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(code, 0, 2, 0)

        names = {"play_pause": "เล่น/หยุด", "next": "เพลงถัดไป", "previous": "เพลงก่อนหน้า",
                 "volume_up": "เพิ่มเสียง", "volume_down": "ลดเสียง", "mute": "ปิดเสียง"}
        return f"✅ {names.get(action, action)} แล้ว"
    except Exception as e:
        return f"❌ ทำไม่ได้: {e}"


def list_running_programs() -> str:
    """ดูโปรแกรมที่ทำงาน"""
    try:
        procs = []
        for p in psutil.process_iter(["name", "memory_percent"]):
            try:
                procs.append(p.info)
            except:
                pass
        procs.sort(key=lambda x: x.get("memory_percent", 0) or 0, reverse=True)
        result = "📋 โปรแกรมที่ทำงาน (top 10):\n"
        for p in procs[:10]:
            result += f"  • {p['name']} - RAM: {p.get('memory_percent', 0):.1f}%\n"
        return result
    except Exception as e:
        return f"❌ ดูไม่ได้: {e}"