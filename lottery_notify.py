"""
Lottery LINE Notify Bot
- ส่งแจ้งเตือนก่อนหวยออก 1 hours
- ดึงผลจาก raakaadee.com หลังออก 5 mins (retry ทุก 15 นาที สูงสุด 3 ครั้ง)
- บันทึก state ใน state/sent_YYYY-MM-DD.json (commit กลับ repo)
"""

import os, sys, json, time, re
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
import requests

# ─── Config ──────────────────────────────────────────────────────────────────
LINE_CHANNEL_TOKEN = os.environ.get("LINE_CHANNEL_TOKEN", "")
LINE_GROUP_ID      = os.environ.get("LINE_GROUP_ID", "")
TZ_BKK = timezone(timedelta(hours=7))

# ─── ตารางเวลาออกผล (เวลาไทย HH:MM) ─────────────────────────────────────────
LOTTERY_SCHEDULE = {
    "ลาว Extra":          "08:30",
    "นิเคอิ VIP เช้า":    "09:05",
    "ฮานอย อาเซียน":      "09:30",
    "จีน VIP เช้า":       "10:05",
    "ลาว TV":             "10:30",
    "ฮั่งเส็ง VIP เช้า":  "10:35",
    "ฮานอย HD":           "11:30",
    "ไต้หวัน VIP":        "11:35",
    "ฮานอย STAR":         "12:30",
    "เกาหลี VIP":         "12:35",
    "นิเคอิ VIP บ่าย":    "13:25",
    "ลาว HD":             "13:45",
    "จีน VIP บ่าย":       "14:25",
    "ฮานอย TV":           "14:30",
    "ฮั่งเส็ง VIP บ่าย":  "15:25",
    "ลาว STAR":           "15:45",
    "ฮานอย กาชาด":        "16:30",
    "สิงคโปร์ VIP":       "17:15",
    "ฮานอย สามัคคี":      "17:30",
    "ฮานอย พัฒนา":        "19:30",
    "ลาว สามัคคี":        "20:30",
    "ลาว อาเซียน":        "21:00",
    "ลาว สามัคคี VIP":    "21:30",
    "อังกฤษ VIP":         "21:50",
    "ลาว STAR VIP":       "22:00",
    "ฮานอย EXTRA":        "22:30",
    "เยอรมัน VIP":        "22:50",
    "ลาว กาชาด":          "23:30",
    "รัสเซีย VIP":        "23:50",
    "ดาวโจนส์ VIP":       "00:30",   # ข้ามคืน
    "ดาวโจนส์ STAR":      "01:30",   # ข้ามคืน
}

# URL สำหรับดึงผลบน raakaadee.com (ชื่อหวย → path)
RAAKAADEE_PATHS = {
    "ลาว Extra":          "หวยลาว-Extra",
    "นิเคอิ VIP เช้า":    "หุ้นนิเคอิเช้า-VIP",
    "ฮานอย อาเซียน":      "หวยฮานอยอาเซียน",
    "จีน VIP เช้า":       "หุ้นจีนเช้า-VIP",
    "ลาว TV":             "หวยลาว-TV",
    "ฮั่งเส็ง VIP เช้า":  "หุ้นฮั่งเส็งเช้า-VIP",
    "ฮานอย HD":           "หวยฮานอย-HD",
    "ไต้หวัน VIP":        "หุ้นไต้หวัน-VIP",
    "ฮานอย STAR":         "หวยฮานอย-STAR",
    "เกาหลี VIP":         "หุ้นเกาหลี-VIP",
    "นิเคอิ VIP บ่าย":    "หุ้นนิเคอิบ่าย-VIP",
    "ลาว HD":             "หวยลาว-HD",
    "จีน VIP บ่าย":       "หุ้นจีนบ่าย-VIP",
    "ฮานอย TV":           "หวยฮานอย-TV",
    "ฮั่งเส็ง VIP บ่าย":  "หุ้นฮั่งเส็งบ่าย-VIP",
    "ลาว STAR":           "หวยลาว-STAR",
    "ฮานอย กาชาด":        "หวยฮานอยกาชาด",
    "สิงคโปร์ VIP":       "หุ้นสิงคโปร์-VIP",
    "ฮานอย สามัคคี":      "หวยฮานอยสามัคคี",
    "ฮานอย พัฒนา":        "หวยฮานอยพัฒนา",
    "ลาว สามัคคี":        "หวยลาวสามัคคี",
    "ลาว อาเซียน":        "หวยลาวอาเซียน",
    "ลาว สามัคคี VIP":    "หวยลาวสามัคคี-VIP",
    "อังกฤษ VIP":         "หุ้นอังกฤษ-VIP",
    "ลาว STAR VIP":       "หวยลาว-STAR-VIP",
    "ฮานอย EXTRA":        "หวยฮานอย-EXTRA",
    "เยอรมัน VIP":        "หุ้นเยอรมัน-VIP",
    "ลาว กาชาด":          "หวยลาวกาชาด",
    "รัสเซีย VIP":        "หุ้นรัสเซีย-VIP",
    "ดาวโจนส์ VIP":       "หุ้นดาวโจนส์-VIP",
    "ดาวโจนส์ STAR":      "หุ้นดาวโจนส์-STAR",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
}

# ─── State (บันทึกว่าส่งอะไรไปแล้ววันนี้) ─────────────────────────────────────
STATE_DIR = Path("state")

def state_path(d: date) -> Path:
    return STATE_DIR / f"sent_{d.isoformat()}.json"

def load_state(d: date) -> dict:
    p = state_path(d)
    if p.exists():
        return json.loads(p.read_text())
    return {}

def save_state(d: date, state: dict):
    STATE_DIR.mkdir(exist_ok=True)
    state_path(d).write_text(json.dumps(state, ensure_ascii=False, indent=2))

# ─── LINE ─────────────────────────────────────────────────────────────────────
def send_line(message: str) -> bool:
    if not LINE_CHANNEL_TOKEN or not LINE_GROUP_ID:
        print("❌ ไม่พบ LINE_CHANNEL_TOKEN หรือ LINE_GROUP_ID")
        return False
    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {LINE_CHANNEL_TOKEN}", "Content-Type": "application/json"},
        json={"to": LINE_GROUP_ID, "messages": [{"type": "text", "text": message}]},
        timeout=10,
    )
    ok = resp.status_code == 200
    print(f"LINE: {'✅' if ok else f'❌ {resp.status_code} {resp.text}'}")
    return ok

# ─── ดึงผลจาก raakaadee.com ───────────────────────────────────────────────────
def fetch_result(name: str, draw_date: date) -> dict | None:
    """
    ดึงผล 3บน และ 2ล่าง จาก raakaadee.com
    Returns {"top3": "xxx", "bot2": "xx"} หรือ None ถ้ายังไม่มีผล
    """
    path = RAAKAADEE_PATHS.get(name)
    if not path:
        print(f"⚠️ ไม่พบ path สำหรับ: {name}")
        return None

    url = f"https://www.raakaadee.com/ตรวจหวย-หุ้น/{path}/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"HTTP {r.status_code} สำหรับ {name}")
            return None

        html = r.text
        # หา 3บน และ 2ล่าง จาก HTML — ปรับ pattern ตามโครงสร้างจริงของเว็บ
        # Pattern ทั่วไปของ raakaadee.com
        top3_match = re.search(r'3\s*ตัวบน[^<]*<[^>]+>(\d{3})', html)
        bot2_match = re.search(r'2\s*ตัวล่าง[^<]*<[^>]+>(\d{2})', html)

        # fallback: หาตัวเลขจาก table row แรก
        if not top3_match:
            top3_match = re.search(r'<td[^>]*>(\d{3})</td>', html)
        if not bot2_match:
            bot2_match = re.search(r'<td[^>]*>(\d{2})</td>', html)

        if top3_match and bot2_match:
            return {"top3": top3_match.group(1), "bot2": bot2_match.group(1)}
        else:
            print(f"⏳ ยังไม่พบผลใน HTML สำหรับ {name}")
            return None

    except Exception as e:
        print(f"❌ fetch error [{name}]: {e}")
        return None

# ─── เวลาออกในรูป datetime ───────────────────────────────────────────────────
def draw_datetime(name: str, ref_now: datetime) -> datetime:
    """
    คืน datetime (aware, BKK) ของเวลาออกผลของ name
    หวยที่ออกหลังเที่ยงคืน (00:xx, 01:xx) → ถือเป็นวันถัดไป
    """
    t = LOTTERY_SCHEDULE[name]
    h, m = int(t.split(":")[0]), int(t.split(":")[1])
    # วันฐาน
    base = ref_now.date()
    # ถ้าเวลาออก < 06:00 → ถือว่าเป็นวันถัดไป (ข้ามคืน)
    if h < 6:
        base = base + timedelta(days=1)
    return datetime(base.year, base.month, base.day, h, m, 0, tzinfo=TZ_BKK)

# ─── Main logic ──────────────────────────────────────────────────────────────
def run():
    now = datetime.now(TZ_BKK)
    today = now.date()
    state = load_state(today)
    changed = False

    print(f"\n⏰ รัน: {now.strftime('%Y-%m-%d %H:%M')} (BKK)\n")

    for name in LOTTERY_SCHEDULE:
        draw_dt = draw_datetime(name, now)
        diff_min = (draw_dt - now).total_seconds() / 60  # บวก = ยังไม่ออก

        reminder_key = f"{name}_reminder"
        result_key   = f"{name}_result"

        # ── แจ้งเตือนก่อนออก 1 ชั่วโมง (window 55–75 นาที) ──────────────────
        if 55 <= diff_min <= 75 and not state.get(reminder_key):
            draw_str = draw_dt.strftime("%H:%M")
            msg = (
                f"🔔 แจ้งเตือนหวย\n"
                f"📌 {name}\n"
                f"⏰ ออกผลเวลา {draw_str} น. (อีก ~1 ชั่วโมง)\n"
                f"🍀 ขอให้โชคดีนะครับ!"
            )
            if send_line(msg):
                state[reminder_key] = now.isoformat()
                changed = True
            print(f"  🔔 Reminder: {name}")

        # ── ดึงผล (window: 5–50 นาทีหลังออก, retry ทุก 15 นาที) ────────────
        elif -50 <= diff_min <= -5 and not state.get(result_key):
            attempt = state.get(f"{name}_attempts", 0)
            if attempt < 3:
                print(f"  🔍 ลองดึงผล ({attempt+1}/3): {name}")
                result = fetch_result(name, draw_dt.date())
                if result:
                    draw_str = draw_dt.strftime("%H:%M")
                    msg = (
                        f"🎰 ผลหวย: {name}\n"
                        f"📅 งวด {draw_dt.strftime('%d/%m')} เวลา {draw_str} น.\n\n"
                        f"3 ตัวบน: {result['top3']}\n"
                        f"2 ตัวล่าง: {result['bot2']}"
                    )
                    if send_line(msg):
                        state[result_key] = now.isoformat()
                        state[f"{name}_result_data"] = result
                        changed = True
                        print(f"  ✅ ส่งผล: {name} → {result}")
                else:
                    state[f"{name}_attempts"] = attempt + 1
                    changed = True
                    print(f"  ⏳ ยังไม่มีผล → retry ครั้งถัดไป")
            else:
                print(f"  ⚠️ หมด retry: {name}")

    if changed:
        save_state(today, state)
        print(f"\n💾 บันทึก state แล้ว")
    else:
        print("\n✅ ไม่มีการเปลี่ยนแปลง")

if __name__ == "__main__":
    run()
    print(f"LINE Messaging API: {'✅ ส่งสำเร็จ' if ok else f'❌ {resp.status_code} {resp.text}'}", flush=True)
    return ok


def fetch_lottery_result(date_str: str) -> dict | None:
    """
    ดึงผลหวยไทยรัฐบาล
    date_str: 'YYYY-MM-DD'  เช่น '2025-06-01'
    Returns dict with keys: date, first, last2, last3f, last3b, near1, near1_low  หรือ None ถ้าไม่มีข้อมูล
    """
    # ── API หลัก: api.maejo.ac.th (ฟรี, ไม่ต้อง key) ──────────────────────
    try:
        url = f"https://www.xn--l3calh4ab5g.com/api/latest"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # ตรวจว่าเป็นงวดที่ต้องการ
            if data.get("date", "").replace("/", "-") == date_str or date_str in data.get("date", ""):
                return _parse_api1(data)
    except Exception as e:
        print(f"API1 error: {e}", flush=True)

    # ── API สำรอง: github หวยไทย ──────────────────────────────────────────
    try:
        # ดึงจาก dataset สาธารณะ
        dd, mm, yyyy = date_str.split("-")[2], date_str.split("-")[1], date_str.split("-")[0]
        url2 = f"https://ruay.com/checkResult/checkResult.php?date={dd}{mm}{yyyy}"
        r2 = requests.get(url2, timeout=10)
        if r2.status_code == 200 and r2.text.strip():
            return _parse_ruay(r2.text)
    except Exception as e:
        print(f"API2 error: {e}", flush=True)

    return None


def _parse_api1(data: dict) -> dict:
    return {
        "date": data.get("date", ""),
        "first":    data.get("1", {}).get("prizes", [""])[0] if "1" in data else data.get("first", ""),
        "last3b":   data.get("last3b", {}).get("prizes", []),
        "last3f":   data.get("last3f", {}).get("prizes", []),
        "last2":    data.get("last2", {}).get("prizes", [""])[0],
        "near1":    data.get("near1", {}).get("prizes", []),
    }


def _parse_ruay(text: str) -> dict | None:
    """Parse ruay.com response (tab-separated)"""
    try:
        parts = text.strip().split("\t")
        if len(parts) < 4:
            return None
        return {
            "date": parts[0],
            "first": parts[1],
            "near1": [parts[2], parts[3]] if len(parts) > 3 else [],
            "last3b": parts[4:6] if len(parts) > 5 else [],
            "last3f": parts[6:8] if len(parts) > 7 else [],
            "last2": parts[8] if len(parts) > 8 else "",
        }
    except Exception:
        return None


def format_result_message(result: dict) -> str:
    near = " | ".join(result.get("near1", []))
    last3b = " | ".join(result.get("last3b", []))
    last3f = " | ".join(result.get("last3f", []))
    return f"""
🎰 ผลสลากกินแบ่งรัฐบาล
📅 งวดวันที่ {result.get('date', '')}

🥇 รางวัลที่ 1:     {result.get('first', '-')}
🔢 เลขท้าย 2 ตัว:  {result.get('last2', '-')}
🔢 เลขท้าย 3 ตัว:  {last3b or '-'}
🔢 เลขหน้า 3 ตัว:  {last3f or '-'}
🎯 เลขใกล้เคียงที่ 1: {near or '-'}
""".strip()


# ─── Modes ───────────────────────────────────────────────────────────────────

def run_reminder():
    """โหมด: แจ้งเตือนก่อนหวยออก 1 ชั่วโมง"""
    now = datetime.now(TZ_BKK)
    msg = f"""
🔔 แจ้งเตือน: สลากกินแบ่งรัฐบาล
📅 งวดวันที่ {now.day}/{now.month}/{now.year + 543}

⏰ อีก 1 ชั่วโมงผลจะออก! (14:00 น.)
🍀 ขอให้โชคดีกับทุกคนนะครับ 🙏
""".strip()
    send_line(msg)


def run_check_result():
    """โหมด: ตรวจสอบและส่งผลหวย"""
    now = datetime.now(TZ_BKK)
    # วันที่งวดนี้ในรูปแบบ YYYY-MM-DD
    date_str = f"{now.year}-{now.month:02d}-{now.day:02d}"
    print(f"ดึงผลหวยงวด {date_str}...", flush=True)

    result = fetch_lottery_result(date_str)
    if result and result.get("first"):
        msg = format_result_message(result)
        send_line(msg)
    else:
        print("ยังไม่มีผล หรือดึงข้อมูลไม่ได้", flush=True)
        # ส่งข้อความแจ้งว่ายังรอผล
        send_line(f"🔄 รอผลสลากฯ งวด {now.day}/{now.month}/{now.year+543} — ยังไม่ประกาศ")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode == "reminder":
        run_reminder()
    else:
        run_check_result()
