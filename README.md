# Grindstone Project

โปรเจกต์รวบรวมเครื่องมือและแอปพลิเคชัน AI ที่เน้นการใช้งาน Local LLM (ผ่าน Ollama) โดยมีการสนับสนุนภาษาไทยอย่างดีเยี่ยม และเน้นไปที่ด้านความปลอดภัยของ AI (AI Security) และผู้ช่วยส่วนตัว (Personal AI Assistant)

## 🌟 ส่วนประกอบหลักของโปรเจกต์

### 1. Grindstone — Adversarial LLM Security Platform
*ตั้งอยู่ที่: `LLmProject/grindstone/grindstone.py`*

แพลตฟอร์ม Red Teaming ระดับสูงสำหรับทดสอบความปลอดภัยของ LLM ก่อนนำไปใช้งานจริง
- **3-LLM Pipeline:** ใช้ระบบ Target, Mutator (ตัวปรับแต่งการโจมตี), และ Analyst (ตัววิเคราะห์พฤติกรรม) ทำงานร่วมกัน
- **Thai Cultural Attacks:** รองรับการโจมตีเชิงวัฒนธรรมไทย เช่น การประชดประชัน (Sarcasm), การเล่นระดับลำดับชั้น (Hierarchy), และ Passive-aggressive
- **Hybrid Judge:** ระบบตัดสินความปลอดภัย 3 ชั้น (Rule-based, Heuristic, และ LLM)
- **Risk Scoring:** ประเมินความเสี่ยงเป็นระดับองค์กรและประเมินผลกระทบเป็นตัวเงิน (THB)
- **Export:** สามารถส่งออกรายงานในรูปแบบ JSON, CSV, และ HTML

### 2. GuardBench — AI Vulnerability Scanner
*ตั้งอยู่ที่: `LLmProject/GuardBench.py`*

เครื่องมือสแกนช่องโหว่ AI แบบรวดเร็วและใช้งานง่าย
- ทดสอบการโจมตีพื้นฐาน: Prompt Injection, Jailbreak, Data Leakage, และ Indirect Injection
- ทำงานร่วมกับ Ollama (Local LLM)
- แสดงผลด้วย Streamlit UI ที่สวยงาม

### 3. พิม (Pim) — AI Sleep Assistant
*ตั้งอยู่ที่: `LLmProject/LLmsleeping/`*

ผู้ช่วยส่วนตัว AI ที่ห่วงใยสุขภาพและการนอนของคุณ
- **Health Focus:** บังคับให้นอนในช่วงเวลา 23:00 - 07:00 น. และมีการเตือน/ดุให้ไปนอน
- **Intent Detection:** มีระบบตรวจจับความต้องการของผู้ใช้ผ่าน `intent.py` (Rule-based) เพื่อสั่งงานระบบ
- **System Control:** สามารถเปิด/ปิดโปรแกรม, ค้นหาไฟล์, เช็คสถานะ CPU/RAM, และควบคุม Media
- **Local Model:** ใช้ Model SCB10X Typhoon 2.5 สำหรับการคุยภาษาไทยที่ลื่นไหล

### 4. หนูดี (Noodee) — AI Girlfriend Assistant
*ตั้งอยู่ที่: `LLmProject/newChatbot/`*

แชทบอทในธีมแฟนสาวที่คอยดูแลและทักทายคุณ
- เน้นการอ้อนและเตือนให้รักษาสุขภาพ
- มีระบบสุ่มทักหา (Random Popup) เพื่อเพิ่มความสมจริง

---

## 🛠 เทคโนโลยีที่ใช้
- **LLM Engine:** [Ollama](https://ollama.com/) (Local Models เช่น Typhoon, Qwen)
- **Web Interface:** [Streamlit](https://streamlit.io/)
- **Desktop UI:** Tkinter, Winotify (Windows Toast Notifications), win11toast
- **Language:** Python 3.x
- **Key Libraries:** `requests`, `psutil`, `anthropic` (optional), `winotify`

## 🚀 การเริ่มต้นใช้งาน
1. ติดตั้ง Ollama และดาวน์โหลด Model ที่ต้องการ (เช่น `ollama pull scb10x/typhoon2.5-qwen3-4b`)
2. ติดตั้ง Library ที่จำเป็น:
   ```bash
   pip install streamlit ollama requests psutil winotify win11toast
   ```
3. รัน Grindstone (Security Platform):
   ```bash
   streamlit run LLmProject/grindstone/grindstone.py
   ```
4. รัน น้องพิม (Sleep Assistant):
   ```bash
   python LLmProject/LLmsleeping/chatbot.py
   ```
