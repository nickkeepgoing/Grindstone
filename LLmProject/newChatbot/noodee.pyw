import time
import threading
import datetime
import requests
import tkinter as tk
from tkinter import simpledialog
from win11toast import toast
import queue
import re
import random
import os

# ========== ⚙️ ตั้งค่าศูนย์กลาง (Config) ==========
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "scb10x/typhoon2.5-qwen3-4b:latest"

# แก้ไขเวลานอนตรงนี้ที่เดียวจบ! (ระบบ 24 ชม.)
BEDTIME_HOUR = 12    
BEDTIME_MINUTE = 00
# ===============================================

class NoodeeSystem:
    def __init__(self):
        self.history = []
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.attributes("-topmost", True)
        
        self.chat_queue = queue.Queue()
        self.root.after(100, self.process_queue)

    def clean_text(self, text):
        """จัดการตัดตัวอักษรที่ลากยาวเกินไป"""
        text = re.sub(r'([ก-๙a-zA-Z])\1{2,}', r'\1\1', text)
        return text.strip()

    def get_time_context(self):
        """เช็คเวลาปัจจุบันเทียบกับเวลานอน""" 
        now = datetime.datetime.now()
        current_total_min = now.hour * 60 + now.minute
        bedtime_total_min = BEDTIME_HOUR * 60 + BEDTIME_MINUTE
        
        is_bedtime = current_total_min >= bedtime_total_min or now.hour < 7
        
        if is_bedtime:
            return f"ขณะนี้เวลา {now.strftime('%H:%M')} เลยเวลานอน ({BEDTIME_HOUR}:{BEDTIME_MINUTE}) แล้ว ต้องดุให้แฟนไปนอน"
        else:
            return f"ขณะนี้เวลา {now.strftime('%H:%M')} ยังไม่ถึงเวลานอน คุยเล่นปกติ"

    def call_typhoon(self, user_input, is_random_greet=False):
        context = self.get_time_context()
        
        system_prompt = f"""เธอชื่อ 'หนูดี' เป็นแฟนสาวของเขา นิสัยน่ารัก ขี้อ้อน และเป็นห่วงสุขภาพแฟนมาก
        สถานการณ์: {context}
        กฎเหล็ก:
        1. ตอบสั้น 1 ประโยค ไม่เกิน 20 คำ
        2. แทนตัวเองว่า เค้า แทนแฟนว่า เตง/ที่รัก
        3. ห้ามบอกว่าเป็น AI
        4. ถ้าเลยเวลานอนต้องดุให้ไปนอนให้ได้"""
        
        if is_random_greet:
            system_prompt += "\nโจทย์: คุณกำลังทักทายแฟนก่อนเพราะคิดถึง"

        self.history.append({"role": "user", "content": user_input})
        try:
            res = requests.post(OLLAMA_URL, json={
                "model": MODEL_NAME,
                "messages": [{"role": "system", "content": system_prompt}] + self.history[-6:],
                "stream": False,
                "options": {
                    "num_predict": 50,
                    "temperature": 0.8,
                    "presence_penalty": 0.6
                }
            }, timeout=15)
            
            reply = self.clean_text(res.json()["message"]["content"])
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except:
            return "เค้าแอบหลับไปแป๊บนึง... โทษทีนะที่รัก"

    def random_popup_monitor(self):
        """ระบบสุ่มทักหาแฟน"""
        while True:
            wait_seconds = random.randint(1800, 3600)
            time.sleep(wait_seconds)
            
            now = datetime.datetime.now()
            current_total_min = now.hour * 60 + now.minute
            bedtime_total_min = BEDTIME_HOUR * 60 + BEDTIME_MINUTE

            if 8 <= now.hour and current_total_min < bedtime_total_min:
                topics = ["ทักเพราะคิดถึง", "ถามว่าทำอะไรอยู่", "อ้อนหน่อย", "ส่งกำลังใจ"]
                greeting = self.call_typhoon(random.choice(topics), is_random_greet=True)
                
                titles = ["เค้าคิดถึงจัง 💕", "เตงจ๋าาา", "แวะมาจุ๊บทีนึง"]
                self.root.after(0, lambda: self.send_notification(random.choice(titles), greeting))

    def bedtime_monitor(self):
        """ระบบเฝ้าเวลานอนและสั่งปิดเครื่อง"""
        has_warned = False
        shutdown_triggered = False

        while True:
            now = datetime.datetime.now()
            current_total_min = now.hour * 60 + now.minute
            bedtime_total_min = BEDTIME_HOUR * 60 + BEDTIME_MINUTE

            if current_total_min >= bedtime_total_min and not has_warned:
                self.root.after(0, lambda: self.send_notification(
                    "🌙 ดึกแล้วนะที่รัก!", 
                    f"เลยเวลา {BEDTIME_HOUR}:{BEDTIME_MINUTE} แล้ว ไปนอนเดี๋ยวนี้!"
                ))
                has_warned = True

            if current_total_min >= bedtime_total_min + 3 and not shutdown_triggered:
                self.root.after(0, lambda: self.send_notification(
                    "🚨 เค้า เอาจริงแล้ว!", 
                    "จะปิดเครื่องใน 5 นาที เซฟงานแล้วไปนอนซะ!"
                ))
                os.system("shutdown /s /t 300")
                shutdown_triggered = True
            
            if now.hour == 7:
                has_warned = False
                shutdown_triggered = False
                
            time.sleep(30)

    def send_notification(self, title, message):
        toast(title, message, on_click=lambda args: self.chat_queue.put("start_chat"))

    def process_queue(self):
        try:
            while not self.chat_queue.empty():
                cmd = self.chat_queue.get_nowait()
                if cmd == "start_chat":
                    self._ask_user()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def _ask_user(self):
        user_reply = simpledialog.askstring("เค้ารอฟังอยู่...", "พิมพ์บอกเค้าได้เลย:", parent=self.root)
        if user_reply:
            threading.Thread(target=self._process_ai_response, args=(user_reply,), daemon=True).start()

    def _process_ai_response(self, user_reply):
        ai_reply = self.call_typhoon(user_reply)
        self.root.after(0, lambda: self.send_notification("เค้า 💖:", ai_reply))

if __name__ == "__main__":
    noodee = NoodeeSystem()
    noodee.send_notification("เค้ามาแล้วค่ะ", f"วันนี้แฟนสู้ๆน้า จะต้องนอนตอน {BEDTIME_HOUR}:{BEDTIME_MINUTE} น้าา")
    
    threading.Thread(target=noodee.bedtime_monitor, daemon=True).start()
    threading.Thread(target=noodee.random_popup_monitor, daemon=True).start()

    noodee.root.mainloop()