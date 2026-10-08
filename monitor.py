import os
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# =========================
# 監視設定
# =========================

CHECKIN_DATE = "20261217"
ADULTS = 4

# 東京ディズニーランドホテル・4名・1泊
DISNEY_URL = (
    "https://reserve.tokyodisneyresort.jp/en/hotel/list/"
    "?adultNum=4"
    "&childNum=0"
    "&roomsNum=1"
    "&stayingDays=1"
    "&useDate=20261217"
    "&hotelSearchDetail=true"
    "&displayType=data-hotel"
    "&reservationStatus=1"
    "&searchHotelCD=TDH"
)

STATE_FILE = "availability_state.json"


# =========================
# メール通知
# =========================

def send_email(room_text):
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    alert_to = os.environ["ALERT_TO"]

    subject = "【空室発見】東京ディズニーランドホテル コンシェルジュ"

    body = f"""
東京ディズニーランドホテルに空室が出た可能性があります！

宿泊日：2026年12月17日
人数：4名
対象：コンシェルジュ系客室

検出した内容：
{room_text}

今すぐ公式予約ページを確認してください。

{DISNEY_URL}

※空室はリアルタイムで変動するため、
リンク先で実際の空室状況を確認して予約してください。
"""

    message = MIMEMultipart()
    message["From"] = smtp_user
    message["To"] = alert_to
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)


# =========================
# 前回状態を読み込む
# =========================

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"available": False}


def save_state(available):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"available": available}, f)


# =========================
# 空室チェック
# =========================

def check_availability():

    print("東京ディズニーランドホテルを確認します……")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            locale="en-US",
            timezone_id="Asia/Tokyo"
        )

        try:
            page.goto(
                DISNEY_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            # ページの表示を少し待つ
            page.wait_for_timeout(10000)

            text = page.locator("body").inner_text()

            print("ページを取得しました。")

            # コンシェルジュ関連の部分を探す
            lines = [
                line.strip()
                for line in text.splitlines()
                if line.strip()
            ]

            matches = []

            for i, line in enumerate(lines):

                if "Concierge" in line:

                    surrounding = "\n".join(
                        lines[max(0, i - 3):min(len(lines), i + 8)]
                    )

                    if (
                        "Available" in surrounding
                        or "Select" in surrounding
                        or "¥" in surrounding
                    ):
                        matches.append(surrounding)

            available = len(matches) > 0

            previous = load_state()

            print("コンシェルジュ空室判定：", available)

            # 今回初めて空室を発見した場合だけメール
            if available and not previous.get("available", False):

                room_text = "\n\n---\n\n".join(matches[:5])

                print("空室を発見！メールを送信します。")

                send_email(room_text)

            elif available:

                print("空室はありますが、すでに通知済みです。")

            else:

                print("現在、対象客室の空室は確認できません。")

            save_state(available)

        finally:

            browser.close()


if __name__ == "__main__":
    check_availability()
