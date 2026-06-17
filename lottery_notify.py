import os
import sys
import json
import re
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
import requests

LINE_CHANNEL_TOKEN = os.environ.get("LINE_CHANNEL_TOKEN", "")
LINE_GROUP_ID = os.environ.get("LINE_GROUP_ID", "")
TZ_BKK = timezone(timedelta(hours=7))

LOTTERY_SCHEDULE = {
    "ลาว Extra": "08:30",
    "นิเคอิ VIP เช้า": "09:05",
    "ฮานอย อาเซียน": "09:30",
    "จีน VIP เช้า": "10:05",
    "ลาว TV": "10:30",
    "ฮั่งเส็ง VIP เช้า": "10:35",
    "ฮานอย HD": "11:30",
    "ไต้หวัน VIP": "11:35",
    "ฮานอย STAR": "12:30",
    "เกาหลี VIP": "12:35",
    "นิเคอิ VIP บ่าย": "13:25",
    "ลาว HD": "13:45",
    "จีน VIP บ่าย": "14:25",
    "ฮานอย TV": "14:30",
    "ฮั่งเส็ง VIP บ่าย": "15:25",
    "ลาว STAR": "15:45",
    "ฮานอย กาชาด": "16:30",
    "สิงคโปร์ VIP": "17:15",
    "ฮานอย สามัคคี": "17:30",
    "ฮานอย พัฒนา": "19:30",
    "ลาว สามัคคี": "20:30",
    "ลาว อาเซียน": "21:00",
    "ลาว สามัคคี VIP": "21:30",
    "อังกฤษ VIP": "21:50",
    "ลาว STAR VIP": "22:00",
    "ฮานอย EXTRA": "22:30",
    "เยอรมัน VIP": "22:50",
    "ลาว กาชาด": "23:30",
    "รัสเซีย VIP": "23:50",
    "ดาวโจนส์ VIP": "00:30",
    "ดาวโจนส์ STAR": "01:30",
}

RAAKAADEE_PATHS = {
    "ลาว Extra": "หวยลาว-Extra",
    "นิเคอิ VIP เช้า": "หุ้นนิเคอิเช้า-VIP",
    "ฮานอย อาเซียน": "หวยฮานอยอาเซียน",
    "จีน VIP เช้า": "หุ้นจีนเช้า-VIP",
    "ลาว TV": "หวยลาว-TV",
    "ฮั่งเส็ง VIP เช้า": "หุ้นฮั่งเส็งเช้า-VIP",
    "ฮานอย HD": "หวยฮานอย-HD",
    "ไต้หวัน VIP": "หุ้นไต้หวัน-VIP",
    "ฮานอย STAR": "หวยฮานอย-STAR",
    "เกาหลี VIP": "หุ้นเกาหลี-VIP",
    "นิเคอิ VIP บ่าย": "หุ้นนิเคอิบ่าย-VIP",
    "ลาว HD": "หวยลาว-HD",
    "จีน VIP บ่าย": "หุ้นจีนบ่าย-VIP",
    "ฮานอย TV": "หวยฮานอย-TV",
    "ฮั่งเส็ง VIP บ่าย": "หุ้นฮั่งเส็งบ่าย-VIP",
    "ลาว STAR": "หวยลาว-STAR",
    "ฮานอย กาชาด": "หวยฮานอยกาชาด",
    "สิงคโปร์ VIP": "หุ้นสิงคโปร์-VIP",
    "ฮานอย สามัคคี": "หวยฮานอยสามัคคี",
    "ฮานอย พัฒนา": "หวยฮานอยพัฒนา",
    "ลาว สามัคคี": "หวยลาวสามัคคี",
    "ลาว อาเซียน": "หวยลาวอาเซียน",
    "ลาว สามัคคี VIP": "หวยลาวสามัคคี-VIP",
    "อังกฤษ VIP": "หุ้นอังกฤษ-VIP",
    "ลาว STAR VIP": "หวยลาว-STAR-VIP",
    "ฮานอย EXTRA": "หวยฮานอย-EXTRA",
    "เยอรมัน VIP": "หุ้นเยอรมัน-VIP",
    "ลาว กาชาด": "หวยลาวกาชาด",
    "รัสเซีย VIP": "หุ้นรัสเซีย-VIP",
    "ดาวโจนส์ VIP": "หุ้นดาวโจนส์-VIP",
    "ดาวโจนส์ STAR": "หุ้นดาวโจนส์-STAR",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
}

STATE_DIR = Path("state")


def state_path(d):
    return STATE_DIR / "sent_{}.json".format(d.isoformat())


def load_state(d):
    p = state_path(d)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_state(d, state):
    STATE_DIR.mkdir(exist_ok=True)
    state_path(d).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def send_line(message):
    if not LINE_CHANNEL_TOKEN or not LINE_GROUP_ID:
        print("No LINE credentials")
        return False
    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": "Bearer " + LINE_CHANNEL_TOKEN,
            "Content-Type": "application/json",
        },
        json={"to": LINE_GROUP_ID, "messages": [{"type": "text", "text": message}]},
        timeout=10,
    )
    ok = resp.status_code == 200
    print("LINE: {} {}".format("OK" if ok else "FAIL", resp.status_code))
    return ok


def fetch_result(name):
    path = RAAKAADEE_PATHS.get(name)
    if not path:
        return None
    url = "https://www.raakaadee.com/ตรวจหวย-หุ้น/{}/".format(path)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        html = r.text
        top3 = re.search(r"(\d{3})", html)
        bot2 = re.search(r"(\d{2})", html)
        if top3 and bot2:
            return {"top3": top3.group(1), "bot2": bot2.group(1)}
        return None
    except Exception as e:
        print("fetch error {}: {}".format(name, e))
        return None


def draw_datetime(name, now):
    t = LOTTERY_SCHEDULE[name]
    h = int(t.split(":")[0])
    m = int(t.split(":")[1])
    base = now.date()
    if h < 6:
        base = base + timedelta(days=1)
    return datetime(base.year, base.month, base.day, h, m, 0, tzinfo=TZ_BKK)


def run():
    now = datetime.now(TZ_BKK)
    today = now.date()
    state = load_state(today)
    changed = False

    print("Run: {} BKK".format(now.strftime("%Y-%m-%d %H:%M")))

    for name in LOTTERY_SCHEDULE:
        draw_dt = draw_datetime(name, now)
        diff_min = (draw_dt - now).total_seconds() / 60

        reminder_key = name + "_reminder"
        result_key = name + "_result"

        if 55 <= diff_min <= 75 and not state.get(reminder_key):
            draw_str = draw_dt.strftime("%H:%M")
            msg = (
                "แจ้งเตือนหวย\n"
                "{}\n"
                "ออกผลเวลา {} น. (อีก ~1 ชั่วโมง)\n"
                "ขอให้โชคดีครับ!"
            ).format(name, draw_str)
            if send_line(msg):
                state[reminder_key] = now.isoformat()
                changed = True
            print("Reminder: {}".format(name))

        elif -50 <= diff_min <= -5 and not state.get(result_key):
            attempt = state.get(name + "_attempts", 0)
            if attempt < 3:
                print("Fetch result ({}/3): {}".format(attempt + 1, name))
                result = fetch_result(name)
                if result:
                    draw_str = draw_dt.strftime("%H:%M")
                    msg = (
                        "ผลหวย: {}\n"
                        "งวด {} เวลา {} น.\n\n"
                        "3 ตัวบน: {}\n"
                        "2 ตัวล่าง: {}"
                    ).format(
                        name,
                        draw_dt.strftime("%d/%m"),
                        draw_str,
                        result["top3"],
                        result["bot2"],
                    )
                    if send_line(msg):
                        state[result_key] = now.isoformat()
                        state[name + "_result_data"] = result
                        changed = True
                        print("Sent result: {} -> {}".format(name, result))
                else:
                    state[name + "_attempts"] = attempt + 1
                    changed = True
                    print("No result yet, will retry: {}".format(name))

    if changed:
        save_state(today, state)
        print("State saved.")
    else:
        print("No changes.")


run()
