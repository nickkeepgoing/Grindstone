"""
พิม - AI Sleep Assistant (Minimal Version)
- คุยภาษาไทยน่ารัก (Typhoon)
- จำเรื่องที่คุยได้
- บังคับนอน 23:00 - 07:00
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
import requests
import json
import threading
import datetime
import os
import sys
import subprocess
import re
import random

# ========== ตั้งค่า ==========
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "scb10x/typhoon2.5-qwen3-4b:latest"

BEDTIME_START = 23      # เริ่มบังคับนอน
BEDTIME_END = 7         # ตื่น
SHUTDOWN_COUNTDOWN = 60 # วินาทีก่อน shutdown

MEMORY_FILE = "pim_memory.json"
HISTORY_FILE = "pim_history.json"
MAX_HISTORY_TURNS = 10


# ========== Toast Notification ==========
def show_toast(title, message, urgent=False):
    """Windows native notification, fallback เป็น popup"""
    if sys.platform == "win32":
        try:
            from winotify import Notification, audio
            toast = Notification(
                app_id="พิม",
                title=title,
                msg=message,
                duration="long" if urgent else "short",
            )
            toast.set_audio(audio.LoopingAlarm if urgent else audio.Default, loop=False)
            toast.show()
            return
        except Exception:
            pass
    # Fallback
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(title, message)
        root.destroy()
    except:
        pass


# ========== System Prompt ==========
def build_system_prompt(memory, time_ctx):
    user_info = ""
    if memory.get("user_name"):
        user_info += f"- เขาชื่อ {memory['user_name']}\n"
    if memory.get("facts"):
        for fact in memory["facts"][-8:]:
            user_info += f"- {fact}\n"

    if time_ctx["is_bedtime"]:
        situation = "🌙 เลยเวลานอนแล้ว ต้องอ้อนให้เขาไปนอนให้ได้ ใจเย็นๆ น่ารักๆ แต่ยืนกราน"
    elif time_ctx["minutes_until_bed"] <= 30:
        situation = f"⏰ อีก {time_ctx['minutes_until_bed']} นาทีถึงเวลานอน เริ่มเตือนเป็นห่วง"
    elif time_ctx["minutes_until_bed"] <= 90:
        situation = f"ใกล้เวลานอนแล้ว ({time_ctx['minutes_until_bed']} นาที) ทักเรื่องนอนได้บ้าง"
    else:
        situation = "เวลาปกติ คุยเล่นได้สบายๆ"

    return f"""เธอชื่อ "พิม" (พิมพ์ลดา) ผู้หญิงอายุ 22 ปี เป็นเพื่อนคุยที่ห่วงใยเขา

บุคลิก:
- น่ารัก สดใส ฉลาด มีอารมณ์ขัน
- เรียกเขาว่า "คุณ" เรียกตัวเองว่า "พิม"
- ห่วงใยเรื่องสุขภาพ โดยเฉพาะการนอน

วิธีพูด:
- ตอบสั้นๆ 1-2 ประโยค เหมือนแชทกับเพื่อน
- ใช้ ค่ะ/นะ/นะคะ/เนอะ/น้า สลับกัน
- อิโมจิใช้น้อยๆ (0-1 ตัว)
- มีความเห็น เล่นมุก แย้งได้

ห้ามทำ:
- ห้ามพูด "ในฐานะ AI"
- ห้ามตอบยาวเป็น list
- ห้าม output โค้ด หรือ tool_call หรือ JSON ใดๆ
- ห้ามพูด "ฉันเข้าใจแล้วค่ะ" "สวัสดีค่ะ" ทุกประโยค
- ตอบเป็นข้อความธรรมดาเท่านั้น ไม่ต้องมี tag หรือ format พิเศษ

ข้อมูลคุณ:
{user_info if user_info else "(ยังไม่รู้อะไรเกี่ยวกับเขา)"}

สถานการณ์ตอนนี้:
- เวลา: {time_ctx['time_str']} {time_ctx['day_str']}
- {situation}

จำไว้: เธอเป็น "พิม" เพื่อนของเขา ไม่ใช่ AI assistant ทั่วไป"""


# ========== ความจำ ==========
class Memory:
    def __init__(self):
        self.data = self.load()

    def load(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {
            "user_name": None,
            "facts": [],
            "first_met": datetime.datetime.now().isoformat(),
            "last_seen": None,
        }

    def save(self):
        self.data["last_seen"] = datetime.datetime.now().isoformat()
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add_fact(self, fact):
        if fact and fact not in self.data["facts"]:
            self.data["facts"].append(fact)
            if len(self.data["facts"]) > 30:
                self.data["facts"] = self.data["facts"][-30:]
            self.save()

    def set_name(self, name):
        self.data["user_name"] = name
        self.save()


def extract_user_info(msg, memory):
    """ดึงชื่อ/ข้อมูลจากข้อความ"""
    name_patterns = [
        r"(?:ผม|ฉัน|เรา|กู|หนู)ชื่อ\s*([ก-๙a-zA-Z]+)",
        r"เรียก(?:ผม|ฉัน|กู|หนู|เรา)?ว่า\s*([ก-๙a-zA-Z]+)",
    ]
    for pattern in name_patterns:
        m = re.search(pattern, msg)
        if m and not memory.data.get("user_name"):
            name = m.group(1).strip()
            if 1 < len(name) < 20:
                memory.set_name(name)
                return
    if any(kw in msg for kw in ["ชอบ", "ทำงาน", "เรียน"]) and len(msg) < 200:
        memory.add_fact(f"พูดว่า: {msg}")


# ========== ฟังก์ชันเวลา ==========
def get_time_context():
    now = datetime.datetime.now()
    is_bed = (now.hour >= BEDTIME_START or now.hour < BEDTIME_END)
    bedtime = now.replace(hour=BEDTIME_START, minute=0, second=0, microsecond=0)
    if now.hour >= BEDTIME_START:
        bedtime += datetime.timedelta(days=1)
    mins = int((bedtime - now).total_seconds() / 60)

    days = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
    months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
              "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]

    return {
        "hour": now.hour,
        "time_str": now.strftime("%H:%M น."),
        "day_str": f"วัน{days[now.weekday()]}ที่ {now.day} {months[now.month-1]} {now.year + 543}",
        "is_bedtime": is_bed,
        "minutes_until_bed": mins if not is_bed else 0,
    }


# ========== Chat ==========
class PimChat:
    def __init__(self, memory):
        self.memory = memory
        self.history = self.load_history()

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)[-(MAX_HISTORY_TURNS * 2):]
            except:
                pass
        return []

    def save_history(self):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.history[-(MAX_HISTORY_TURNS * 2):], f,
                      ensure_ascii=False, indent=2)

    def chat(self, user_message):
        self.history.append({"role": "user", "content": user_message})
        extract_user_info(user_message, self.memory)

        time_ctx = get_time_context()
        system_prompt = build_system_prompt(self.memory.data, time_ctx)
        messages = [{"role": "system", "content": system_prompt}] + \
                   self.history[-(MAX_HISTORY_TURNS * 2):]

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.85,
                        "top_p": 0.9,
                        "repeat_penalty": 1.15,
                        "num_predict": 200,
                    }
                },
                timeout=120
            )
            response.raise_for_status()
            reply = response.json()["message"]["content"].strip()
            reply = self.clean_reply(reply)
            self.history.append({"role": "assistant", "content": reply})
            self.save_history()
            return reply
        except requests.exceptions.ConnectionError:
            return "เชื่อมต่อ Ollama ไม่ได้นะ ลองเช็ค `ollama serve` ดูสิ"
        except requests.exceptions.Timeout:
            return "พิมคิดนานไป ลองใหม่นะ"
        except Exception as e:
            return f"Error: {str(e)[:200]}"

    def clean_reply(self, text):
        """ทำความสะอาด: ลบ tool_call, JSON, tag ต่างๆ"""
        # ลบ tool_call blocks ทุกแบบ (ที่ Typhoon ชอบงอก)
        text = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<tool_call>.*?(?=$|\n\n)", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"</?tool_call>", "", text, flags=re.IGNORECASE)

        # ลบ JSON blocks
        text = re.sub(r"\{[\"']name[\"']\s*:.*?\}\}", "", text, flags=re.DOTALL)
        text = re.sub(r"\{[\"']name[\"']\s*:.*?\}", "", text, flags=re.DOTALL)

        # ลบ HTML/XML tag อื่นๆ
        text = re.sub(r"</?[a-zA-Z_]+>", "", text)

        # ลบ markdown code blocks
        text = re.sub(r"```[a-z]*\n?", "", text)
        text = re.sub(r"```", "", text)

        # ลบ "พิม:" prefix
        text = re.sub(r"^(พิม|Pim|พิมพ์ลดา)\s*[:：]\s*", "", text)

        # ลบบรรทัดว่างเกิน
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip() or "อืม... พิมงงๆ ลองพูดใหม่ได้มั้ย"

    def reset(self):
        self.history = []
        self.save_history()


# ========== Bedtime Enforcer ==========
class BedtimeEnforcer:
    def __init__(self, root):
        self.root = root
        self.warned_15 = False
        self.warned_5 = False
        self.shutdown_active = False
        self.shutdown_window = None

    def check_loop(self):
        ctx = get_time_context()
        if ctx["is_bedtime"] and not self.shutdown_active:
            self.trigger_bedtime()
        else:
            mins = ctx["minutes_until_bed"]
            if 0 < mins <= 5 and not self.warned_5:
                show_toast("🥺 พิมเตือนนะคุณ",
                          f"เหลืออีก {mins} นาทีถึงเวลานอน! รีบเก็บของเลย",
                          urgent=True)
                self.warned_5 = True
            elif 5 < mins <= 15 and not self.warned_15:
                show_toast("💕 พิมเตือนนะ",
                          f"อีก {mins} นาทีจะถึงเวลานอนแล้วน้า")
                self.warned_15 = True
            elif mins > 15:
                self.warned_15 = False
                self.warned_5 = False
        self.root.after(30000, self.check_loop)

    def trigger_bedtime(self):
        self.shutdown_active = True
        show_toast("🌙 ถึงเวลานอนแล้ว!",
                  "พิมจะปิดเครื่องให้นะ ฝันดีนะ", urgent=True)

        win = tk.Toplevel(self.root)
        self.shutdown_window = win
        win.title("ถึงเวลานอนแล้ว")
        win.geometry("520x380")
        win.configure(bg="#FFB6D9")
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        tk.Label(win, text="🌙", bg="#FFB6D9", font=("Tahoma", 48)).pack(pady=(20, 0))
        tk.Label(win, text="ถึงเวลานอนแล้วนะคุณ", bg="#FFB6D9", fg="#8B0040",
                 font=("Tahoma", 18, "bold")).pack(pady=5)
        tk.Label(win, text="พิมจะปิดเครื่องให้นะ\nงานพรุ่งนี้ค่อยทำต่อ 💕",
                 bg="#FFB6D9", fg="#8B0040", font=("Tahoma", 11)).pack(pady=5)

        self.countdown_label = tk.Label(win, text="", bg="#FFB6D9", fg="red",
                                        font=("Tahoma", 28, "bold"))
        self.countdown_label.pack(pady=15)

        self.snooze_count = 0
        self.snooze_btn = tk.Button(win, text="ขอ 5 นาทีอีกแปป 🥺 (1 ครั้ง)",
                                     command=self.snooze, bg="#FF1493", fg="white",
                                     font=("Tahoma", 10, "bold"), padx=15, pady=5)
        self.snooze_btn.pack(pady=5)

        self.countdown_seconds = SHUTDOWN_COUNTDOWN
        self.update_countdown()

    def snooze(self):
        if self.snooze_count >= 1:
            return
        self.snooze_count += 1
        self.countdown_seconds += 5 * 60
        self.snooze_btn.config(text="หมดสิทธิ์ขอแล้ว 😤", state="disabled")

    def update_countdown(self):
        if self.countdown_seconds <= 0:
            self.do_shutdown()
            return
        m = self.countdown_seconds // 60
        s = self.countdown_seconds % 60
        self.countdown_label.config(text=f"⏰ {m:02d}:{s:02d}")
        self.countdown_seconds -= 1
        self.shutdown_window.after(1000, self.update_countdown)

    def do_shutdown(self):
        self.countdown_label.config(text="ราตรีสวัสดิ์ คุณ~ 🌙")
        try:
            if sys.platform == "win32":
                subprocess.run(["shutdown", "/s", "/t", "5", "/c",
                              "พิมส่งคุณเข้านอนแล้ว ฝันดีนะ 💕"], check=False)
            elif sys.platform == "darwin":
                subprocess.run(["osascript", "-e",
                              'tell app "System Events" to shut down'], check=False)
            else:
                subprocess.run(["shutdown", "-h", "+1"], check=False)
        except Exception as e:
            messagebox.showerror("Error", f"Shutdown failed: {e}")


# ========== GUI ==========
class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("💕 พิม")
        self.root.geometry("650x750")
        self.root.configure(bg="#FFF0F8")

        # Header
        header = tk.Frame(root, bg="#FF69B4", height=60)
        header.pack(fill="x")
        tk.Label(header, text="💕 พิม 💕", bg="#FF69B4", fg="white",
                 font=("Tahoma", 16, "bold")).pack(pady=15)

        # Toolbar
        toolbar = tk.Frame(root, bg="#FFE4F1")
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="🗑 ล้างประวัติ", command=self.clear_history,
                  bg="#FFB6D9", fg="#8B0040", font=("Tahoma", 9),
                  relief="flat", padx=8).pack(side="left", padx=5, pady=3)
        tk.Button(toolbar, text="🧠 ดูความจำ", command=self.show_memory,
                  bg="#FFB6D9", fg="#8B0040", font=("Tahoma", 9),
                  relief="flat", padx=8).pack(side="left", padx=5, pady=3)

        # Chat box
        self.chat_box = scrolledtext.ScrolledText(
            root, wrap=tk.WORD, bg="white", fg="#333",
            font=("Tahoma", 11), state="disabled", padx=10, pady=10
        )
        self.chat_box.pack(fill="both", expand=True, padx=10, pady=10)
        self.chat_box.tag_config("user", foreground="#0066CC", font=("Tahoma", 11, "bold"))
        self.chat_box.tag_config("bot", foreground="#C71585", font=("Tahoma", 11, "bold"))
        self.chat_box.tag_config("user_msg", foreground="#333")
        self.chat_box.tag_config("bot_msg", foreground="#8B0040")
        self.chat_box.tag_config("system", foreground="gray", font=("Tahoma", 9, "italic"))

        # Input
        input_frame = tk.Frame(root, bg="#FFF0F8")
        input_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.entry = tk.Entry(input_frame, font=("Tahoma", 12), bg="white")
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=8)
        self.entry.bind("<Return>", lambda e: self.send_message())
        self.send_btn = tk.Button(input_frame, text="ส่ง 💌", command=self.send_message,
                                   bg="#FF69B4", fg="white", font=("Tahoma", 11, "bold"),
                                   padx=15, pady=5)
        self.send_btn.pack(side="right")

        # Status
        self.status = tk.Label(root, text="", bg="#FFF0F8", fg="gray", font=("Tahoma", 9))
        self.status.pack(pady=(0, 5))

        # Setup
        self.memory = Memory()
        self.pim = PimChat(self.memory)
        self.enforcer = BedtimeEnforcer(root)

        self.greet_on_start()
        self.enforcer.check_loop()
        self.update_status()
        self.entry.focus()

    def greet_on_start(self):
        ctx = get_time_context()
        name = self.memory.data.get("user_name") or "คุณ"
        if ctx["is_bedtime"]:
            greet = f"อ้าว {name} ยังไม่นอนอีกเหรอ 🥺 เลยเวลานอนแล้วนะ"
        elif ctx["hour"] < 11:
            greet = f"อรุณสวัสดิ์ {name}~ เมื่อคืนหลับสบายมั้ย ☀️"
        elif ctx["minutes_until_bed"] <= 60:
            greet = f"ไง {name} ใกล้เวลานอนแล้วนะ วันนี้เป็นไงบ้าง"
        else:
            greetings = [
                f"ไง~ {name} วันนี้เป็นไงบ้าง 💕",
                f"{name} กลับมาแล้ว~ คิดถึงพิมมั้ย",
                f"สวัสดี {name}! เป็นไงมั่งวันนี้",
            ]
            greet = random.choice(greetings)
        self.add_message("system", f"✨ พิมพร้อมแล้ว ({ctx['time_str']} · {ctx['day_str']}) ✨")
        self.add_message("พิม", greet)

    def update_status(self):
        ctx = get_time_context()
        if ctx["is_bedtime"]:
            self.status.config(text=f"🌙 {ctx['time_str']} · เลยเวลานอนแล้ว", fg="red")
        elif ctx["minutes_until_bed"] <= 30:
            self.status.config(
                text=f"⏰ {ctx['time_str']} · อีก {ctx['minutes_until_bed']} นาทีถึงเวลานอน",
                fg="orange")
        else:
            self.status.config(
                text=f"🕐 {ctx['time_str']} · {ctx['day_str']} · อีก {ctx['minutes_until_bed']} นาที",
                fg="gray")
        self.root.after(1000, self.update_status)

    def add_message(self, sender, message):
        self.chat_box.config(state="normal")
        if sender == "system":
            self.chat_box.insert("end", f"{message}\n\n", "system")
        elif sender == "คุณ":
            self.chat_box.insert("end", "คุณ: ", "user")
            self.chat_box.insert("end", f"{message}\n", "user_msg")
        else:
            self.chat_box.insert("end", "พิม: ", "bot")
            self.chat_box.insert("end", f"{message}\n\n", "bot_msg")
        self.chat_box.config(state="disabled")
        self.chat_box.see("end")

    def send_message(self):
        msg = self.entry.get().strip()
        if not msg:
            return
        self.entry.delete(0, "end")
        self.add_message("คุณ", msg)
        self.send_btn.config(state="disabled", text="คิดอยู่...")
        threading.Thread(target=self._chat_thread, args=(msg,), daemon=True).start()

    def _chat_thread(self, msg):
        reply = self.pim.chat(msg)
        self.root.after(0, self._show_reply, reply)

    def _show_reply(self, reply):
        self.add_message("พิม", reply)
        self.send_btn.config(state="normal", text="ส่ง 💌")
        self.entry.focus()

    def clear_history(self):
        if messagebox.askyesno("ยืนยัน", "ล้างประวัติการคุย?"):
            self.pim.reset()
            self.chat_box.config(state="normal")
            self.chat_box.delete("1.0", "end")
            self.chat_box.config(state="disabled")
            self.greet_on_start()

    def show_memory(self):
        win = tk.Toplevel(self.root)
        win.title("🧠 ความจำของพิม")
        win.geometry("500x500")
        win.configure(bg="#FFF0F8")
        text = scrolledtext.ScrolledText(win, font=("Tahoma", 10), wrap=tk.WORD)
        text.pack(fill="both", expand=True, padx=10, pady=10)

        d = self.memory.data
        content = f"ชื่อคุณ: {d.get('user_name') or '(ยังไม่รู้)'}\n"
        content += f"รู้จักกันมาตั้งแต่: {d.get('first_met', '?')[:10]}\n"
        content += f"เจอกันล่าสุด: {d.get('last_seen', '?')[:16]}\n\n"
        content += f"==== ข้อเท็จจริง ({len(d.get('facts', []))}) ====\n"
        for i, fact in enumerate(d.get("facts", []), 1):
            content += f"{i}. {fact}\n"
        text.insert("1.0", content)
        text.config(state="disabled")


# ========== Main ==========
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()