"""
Thai Lottery LINE Messaging API Bot
- ส่งแจ้งเตือนก่อนหวยออก 1 ชั่วโมง (13:00 น. ของวันที่ 1 และ 16)
- ส่งผลหวยเมื่อประกาศแล้ว (ช่วง 15:00–16:00 น.)
"""

import os
import requests
from datetime import datetime, timezone, timedelta
import sys

# ─── Config ──────────────────────────────────────────────────────────────────
LINE_CHANNEL_TOKEN = os.environ.get("LINE_CHANNEL_TOKEN", "")  # Channel Access Token
LINE_GROUP_ID      = os.environ.get("LINE_GROUP_ID", "")       # Group/Room Chat ID
TZ_BKK = timezone(timedelta(hours=7))

# ─── Helpers ─────────────────────────────────────────────────────────────────

def send_line(message: str) -> bool:
    """ส่งข้อความไปยัง LINE group ผ่าน Messaging API (push message)"""
    if not LINE_CHANNEL_TOKEN or not LINE_GROUP_ID:
        print("❌ ไม่พบ LINE_CHANNEL_TOKEN หรือ LINE_GROUP_ID", flush=True)
        return False
    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "to": LINE_GROUP_ID,
            "messages": [{"type": "text", "text": message}],
        },
        timeout=10,
    )
    ok = resp.status_code == 200
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
