import os
import json
import random
import asyncio
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from google import genai
from twikit import Client

# ローカル開発時のみ .env を読み込む
load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

HISTORY_FILE = "post_history.json"

# 投稿テーマ（自由に追加・変更可）
TOPICS = [
    "今日のAI・テクノロジーに関する豆知識を1つ紹介してください。",
    "Pythonプログラミングの便利なTipsを1つ共有してください。",
    "最近の技術トレンドについて、簡潔に意見を述べてください。",
    "エンジニアの生産性を上げるコツを1つ紹介してください。",
    "プログラミング学習で挫折しないためのアドバイスを1つ述べてください。",
]

# フォールバック用モデルリスト（上から順に試行）
# 存在しないモデル名を指定した場合は404エラーとなり、自動的に次のモデルへ進みます
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]

MAX_RETRIES_PER_MODEL = 3


def load_history() -> list:
    """投稿履歴を読み込む"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history: list) -> None:
    """投稿履歴を保存する（直近100件のみ保持）"""
    history = history[-100:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def generate_post_text(topic: str) -> str:
    """Gemini APIで投稿文を生成する（リトライ＆フォールバック付き）"""
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = (
        f"あなたはX（旧Twitter）の投稿を作成するアシスタントです。\n"
        f"以下のテーマについて、140文字以内の日本語の投稿文を1つ作成してください。\n"
        f"ハッシュタグは2〜3個含めてください。\n"
        f"テーマ：{topic}"
    )

    last_error = None
    for model_name in MODELS:
        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            try:
                print(f"  [試行] モデル={model_name} ({attempt}/{MAX_RETRIES_PER_MODEL})")
                interaction = client.interactions.create(
                    model=model_name,
                    input=prompt,
                )
                text = interaction.output_text.strip()
                if not text:
                    raise ValueError("空の応答が返されました")
                return text
            except Exception as e:
                last_error = e
                msg = str(e)
                print(f"  [警告] {model_name}: {msg[:200]}")

                # リトライ対象のエラーか判定
                retryable = any(k in msg for k in [
                    "503", "429",
                    "UNAVAILABLE", "RESOURCE_EXHAUSTED",
                    "high demand", "overloaded",
                ])

                if retryable and attempt < MAX_RETRIES_PER_MODEL:
                    wait = (2 ** (attempt - 1)) + random.uniform(0, 1)
                    print(f"  [待機] {wait:.1f}秒後にリトライします...")
                    time.sleep(wait)
                    continue
                # リトライ不可 or 回数上限 → 次のモデルへ
                break

    raise RuntimeError(f"全てのモデルで生成に失敗しました。最後のエラー: {last_error}")


async def post_to_x(text: str):
    """twikitでXに投稿する"""
    client = Client("ja-JP")
    client.load_cookies("cookies.json")
    tweet = await client.create_tweet(text=text)
    return tweet


def main():
    # 1. テーマをランダム選択
    topic = random.choice(TOPICS)

    # 2. Geminiで投稿文を生成
    print(f"[{datetime.now(timezone.utc)}] テーマ: {topic}")
    text = generate_post_text(topic)
    print(f"生成された投稿文:\n{text}\n")

    # 3. Xに投稿
    tweet = asyncio.run(post_to_x(text))
    print(f"投稿成功: https://x.com/i/status/{tweet.id}")

    # 4. 投稿履歴を保存
    history = load_history()
    history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "text": text,
        "tweet_id": str(tweet.id),
    })
    save_history(history)

    print("完了しました。")


if __name__ == "__main__":
    main()