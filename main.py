import os
import json
import random
import asyncio
from datetime import datetime, timezone

from dotenv import load_dotenv
from google import genai
from twikit import Client

# ローカル開発時のみ .env を読み込む（GitHub Actionsでは環境変数が直接渡される）
load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

HISTORY_FILE = "post_history.json"

# 投稿テーマのリスト（自由にカスタマイズ可能）
TOPICS = [
    "今日のAI・テクノロジーに関する豆知識を1つ紹介してください。",
    "Pythonプログラミングの便利なTipsを1つ共有してください。",
    "最近の技術トレンドについて、簡潔に意見を述べてください。",
    "エンジニアの生産性を上げるコツを1つ紹介してください。",
    "プログラミング学習で挫折しないためのアドバイスを1つ述べてください。",
]


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
    """Gemini APIで投稿文を生成する"""
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = (
        f"あなたはX（旧Twitter）の投稿を作成するアシスタントです。\n"
        f"以下のテーマについて、140文字以内の日本語の投稿文を1つ作成してください。\n"
        f"ハッシュタグは2〜3個含めてください。\n"
        f"テーマ：{topic}"
    )
    interaction = client.interactions.create(
        model="gemini-3.8-flash",
        input=prompt,
    )
    return interaction.output_text.strip()


async def post_to_x(text: str):
    """twikitでXに投稿する"""
    client = Client("ja-JP")
    client.load_cookies("cookies.json")
    tweet = await client.create_tweet(text=text)
    return tweet


def main():
    # 1. テーマをランダムに選択
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