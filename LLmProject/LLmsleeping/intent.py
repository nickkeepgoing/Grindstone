"""
intent.py - ตัดสินใจว่าผู้ใช้ต้องการให้พิมทำอะไร โดยใช้ rule-based + keyword matching
แม่นยำกว่าให้ LLM ตัดสินใจเอง (เพราะ LLM ไทยไม่เก่งพอ)
"""

import re
from tools import (
    open_path, search_files, open_website, search_youtube, search_google,
    run_program, close_program, system_status, control_media, list_running_programs
)


# ========== Pattern-based Intent Detection ==========

INTENTS = [
    # ====== เปิดโปรแกรม (whitelist - priority สูงสุด) ======
    {
        "patterns": [
            r"^(?:เปิด|run|รัน|เรียก)\s*(?:โปรแกรม)?\s*(notepad|โน้ตแพด|calculator|calc|เครื่องคิดเลข|paint|mspaint|เพ้นท์|cmd|powershell|explorer|task\s*manager|taskmgr|control\s*panel|chrome|edge|firefox|vscode|vs\s*code|discord|spotify|steam|settings)\s*$",
        ],
        "extract": "program",
        "action": lambda p: run_program(p),
        "reply": "เปิด {p} ให้แล้ว ▶",
    },

    # ====== ปิดโปรแกรม ======
    {
        "patterns": [
            r"^(?:ปิด|kill|close|หยุด)\s*(?:โปรแกรม)?\s*(notepad|chrome|edge|firefox|spotify|discord|calc|mspaint|cmd|powershell|.+?\.exe)\s*$",
        ],
        "extract": "program",
        "action": lambda p: close_program(p),
        "reply": "ปิด {p} ให้แล้ว ❌",
    },

    # ====== เปิดโฟลเดอร์/ไฟล์ (whitelist) ======
    {
        "patterns": [
            r"^(?:เปิด|open|ไป)\s*(?:โฟลเดอร์|folder)?\s*(desktop|เดสก์ทอป|หน้าจอ|documents|เอกสาร|downloads|ดาวน์โหลด|pictures|รูปภาพ|music|เพลง|videos|วิดีโอ|home)\s*$",
            r"^(?:เปิด|open)\s+([A-Z]:[\\\/].+)$",
        ],
        "extract": "path",
        "action": lambda p: open_path(p),
        "reply": "เปิด {p} ให้แล้ว 📂",
    },

    # ====== ค้นหาใน Google (เฉพาะคำสั่งที่ระบุ google ชัดเจน) ======
    {
        "patterns": [
            r"(?:หา|ค้นหา|search)\s+(.+?)\s+(?:ใน|บน|จาก)\s*google\s*$",
            r"google\s+(?:หา|ค้นหา)\s+(.+)$",
        ],
        "extract": "google_query",
        "action": lambda q: search_google(q),
        "reply": "ค้นหา \"{q}\" ใน Google ให้แล้ว 🔍",
    },

    # ====== ค้นหาไฟล์ ======
    {
        "patterns": [
            r"(?:หาไฟล์|ค้นหาไฟล์)\s+(.+)$",
            r"(?:หา|ค้นหา|find)\s+([a-zA-Z0-9_\-\.\*]+\.[a-zA-Z0-9]+)\s*$",
        ],
        "extract": "filename",
        "action": lambda f: search_files(f),
        "reply": "ค้นหา {f} ให้แล้ว 🔍",
    },

    # ====== เปิดเว็บไซต์ (whitelist เว็บยอดฮิต) ======
    {
        "patterns": [
            r"^(?:เปิด|open)\s*(?:เว็บ|website)?\s*(google|facebook|fb|twitter|x|github|gmail|drive|netflix|discord|reddit|chatgpt|claude)\s*$",
        ],
        "extract": "website",
        "action": lambda w: open_website(w),
        "reply": "เปิด {w} ให้แล้ว 🌐",
    },

    # ====== เปิดเว็บที่มี .com .net etc ======
    {
        "patterns": [
            r"^(?:เปิด|open)\s+(?:เว็บ|website)?\s*([a-zA-Z][a-zA-Z0-9\-]+\.[a-z]{2,})(?:\/.*)?$",
        ],
        "extract": "website",
        "action": lambda w: open_website(w),
        "reply": "เปิด {w} ให้แล้ว 🌐",
    },

    # ====== System Status ======
    {
        "patterns": [
            r"(?:เช็ค|ดู|check|สถานะ|status)\s*(?:cpu|ram|memory|disk|เครื่อง|ระบบ|system)",
            r"(?:cpu|ram|memory|disk|ระบบ|เครื่อง)\s*(?:เป็นไง|เท่าไหร่|ใช้|ตอนนี้|อยู่ที่|กี่)",
            r"^สถานะ(?:เครื่อง|ระบบ)?$",
        ],
        "action": lambda: system_status(),
        "reply": None,
    },

    # ====== Media Control ======
    {
        "patterns": [r"^(?:หยุดเพลง|pause|กดเพลง|หยุด\s*เพลง)$"],
        "action": lambda: control_media("play_pause"),
        "reply": "เรียบร้อย 🎵",
    },
    {
        "patterns": [r"^(?:เพลง)?\s*(?:ถัดไป|ต่อไป|next|skip|ข้าม)$"],
        "action": lambda: control_media("next"),
        "reply": "เพลงถัดไป ⏭",
    },
    {
        "patterns": [r"^(?:เพลง)?\s*(?:ก่อนหน้า|previous|prev|ย้อน)$"],
        "action": lambda: control_media("previous"),
        "reply": "เพลงก่อนหน้า ⏮",
    },
    {
        "patterns": [r"(?:เพิ่มเสียง|เร่งเสียง|ดังขึ้น|volume\s*up)"],
        "action": lambda: control_media("volume_up"),
        "reply": "เพิ่มเสียงให้แล้ว 🔊",
    },
    {
        "patterns": [r"(?:ลดเสียง|เบาเสียง|เบาลง|volume\s*down)"],
        "action": lambda: control_media("volume_down"),
        "reply": "ลดเสียงให้แล้ว 🔉",
    },
    {
        "patterns": [r"(?:ปิดเสียง|mute|ไม่มีเสียง|silent)"],
        "action": lambda: control_media("mute"),
        "reply": "ปิดเสียงให้แล้ว 🔇",
    },

    # ====== List Programs ======
    {
        "patterns": [
            r"(?:ดู|list|show)\s*(?:โปรแกรม|program)\s*(?:ที่|ทั้งหมด)?\s*(?:เปิด|ทำงาน|รัน|กำลัง)",
            r"โปรแกรม(?:อะไร)?(?:เปิดอยู่|ทำงานอยู่|รันอยู่)",
        ],
        "action": lambda: list_running_programs(),
        "reply": None,
    },
]


def detect_intent(user_message: str):
    """
    วิเคราะห์ข้อความ user → ถ้าเข้า pattern คืน (action_result, friendly_reply)
    ถ้าไม่เข้า pattern คืน (None, None) → ส่งให้ LLM คุยปกติ
    """
    msg = user_message.strip()

    for intent in INTENTS:
        for pattern in intent["patterns"]:
            m = re.search(pattern, msg, re.IGNORECASE)
            if m:
                try:
                    extract_type = intent.get("extract")
                    if extract_type and m.groups():
                        # ดึง argument จาก regex group
                        arg = m.group(1).strip() if m.lastindex else None
                        if not arg:
                            continue
                        result = intent["action"](arg)
                        reply_template = intent.get("reply")
                        if reply_template:
                            placeholder_map = {"q": arg, "w": arg, "p": arg, "f": arg}
                            for key, val in placeholder_map.items():
                                reply_template = reply_template.replace("{" + key + "}", val)
                            friendly_reply = reply_template
                        else:
                            friendly_reply = result
                        return result, friendly_reply
                    else:
                        # ไม่มี argument
                        result = intent["action"]()
                        reply_template = intent.get("reply")
                        friendly_reply = reply_template if reply_template else result
                        return result, friendly_reply
                except Exception as e:
                    return f"❌ Error: {e}", f"เอ๊~ พิมทำไม่ได้นะ ({e})"
    return None, None


# ========== Special: extract YouTube query ==========
def extract_youtube_query(msg: str):
    """ดึงคำค้นหาจากประโยคที่บอกให้เปิด/เล่นใน YouTube"""
    # ลบคำสั่งออก
    cleanup = [
        r"(?:เปิด|เล่น|ดู|หา|ค้นหา|search|open|play)\s*",
        r"(?:เพลง|วิดีโอ|video|คลิป)\s*",
        r"(?:ใน|บน|ที่|จาก)\s*(?:youtube|ยูทูป|ยูทูบ)\s*",
        r"(?:youtube|ยูทูป|ยูทูบ)\s*",
        r"\s*(?:ให้|หน่อย|ที|นะ|ครับ|ค่ะ|น้า|จ้า)\s*",
    ]
    q = msg
    for c in cleanup:
        q = re.sub(c, " ", q, flags=re.IGNORECASE)
    q = re.sub(r"\s+", " ", q).strip()
    return q if len(q) >= 2 else None


# ========== Smart YouTube Detection ==========
def is_youtube_intent(msg: str) -> str | None:
    """
    ตรวจว่าเป็นคำสั่งเปิด YouTube พร้อม query หรือไม่
    คืน: '' = เปิดหน้าแรก YouTube, 'xxx' = search xxx, None = ไม่ใช่
    
    Logic เข้มงวด: ต้องมีคำว่า youtube/ยูทูป/ยูทูบ ในประโยค
    หรือเริ่มด้วย "เล่นเพลง"/"เปิดเพลง"/"หาเพลง" เท่านั้น
    """
    msg_lower = msg.lower()
    youtube_kws = ["youtube", "ยูทูป", "ยูทูบ"]
    has_youtube = any(kw in msg_lower for kw in youtube_kws)

    # กรณี 1: มีคำ "youtube" ในประโยค
    if has_youtube:
        # "เปิด youtube" ตรงๆ → ไม่มี query
        if re.match(r"^(?:เปิด|open)\s*(?:เว็บ)?\s*(?:youtube|ยูทูป|ยูทูบ)\s*$",
                    msg.strip(), re.IGNORECASE):
            return ""
        # มีคำสั่ง action + youtube + อะไรก็ตาม → search
        action_kws = ["เปิด", "เล่น", "ดู", "หา", "ค้นหา", "open", "play", "search"]
        if any(kw in msg_lower for kw in action_kws):
            q = extract_youtube_query(msg)
            return q if q else ""

    # กรณี 2: เริ่มด้วย "เล่นเพลง"/"เปิดเพลง"/"หาเพลง" (เพลง = ชัดเจนว่าเป็น YouTube)
    if re.match(r"^(?:เล่นเพลง|เปิดเพลง|หาเพลง)\s+(.{2,})", msg, re.IGNORECASE):
        q = extract_youtube_query(msg)
        return q if q else None

    # กรณีอื่นๆ: ไม่ถือเป็น YouTube
    return None


def smart_dispatch(user_message: str):
    """
    Master dispatcher: รวม logic ทั้งหมด
    คืน (tool_executed: bool, tool_log: str, friendly_reply: str)
    """
    # 1. เช็ค YouTube intent ก่อน (เพราะกินคำว่า "เปิด" ที่อาจถูก match ผิด)
    yt_query = is_youtube_intent(user_message)
    if yt_query is not None:
        if yt_query == "":
            # เปิดหน้าแรก YouTube
            log = open_website("youtube")
            return True, log, "เปิด YouTube ให้แล้ว 🎵"
        else:
            log = search_youtube(yt_query)
            return True, log, f"เปิด YouTube หา \"{yt_query}\" ให้แล้วน้า~ 🎵"

    # 2. ลอง pattern อื่นๆ
    result, reply = detect_intent(user_message)
    if result is not None:
        return True, result, reply

    # 3. ไม่เข้า pattern → ให้ LLM จัดการ
    return False, None, None