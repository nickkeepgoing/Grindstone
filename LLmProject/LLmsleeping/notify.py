"""notify.py - Windows native toast notifications"""

import sys


def show_notification(title: str, message: str, duration: str = "short", urgent: bool = False):
    if sys.platform == "win32":
        try:
            from winotify import Notification, audio
            toast = Notification(
                app_id="พิม - AI Assistant",
                title=title,
                msg=message,
                duration=duration,
            )
            if urgent:
                toast.set_audio(audio.LoopingAlarm, loop=False)
            else:
                toast.set_audio(audio.Default, loop=False)
            toast.show()
            return True
        except ImportError:
            pass
        except Exception as e:
            print(f"Toast error: {e}")
    return _fallback_popup(title, message)


def _fallback_popup(title, message):
    import tkinter as tk
    from tkinter import messagebox
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(title, message)
        root.destroy()
        return True
    except:
        return False    