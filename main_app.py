import streamlit as st
import os
import glob
import pandas as pd
from google import genai
from google.genai import types
import datetime

# ---------------------------------------------------------
# UI Setup
# ---------------------------------------------------------
st.set_page_config(page_title="SAKURA Cottage Chatbot", page_icon="🌸", layout="wide")

hide_streamlit_style = """
<style>
[data-testid="stToolbar"] {visibility: hidden !important; display: none !important;}
header {visibility: hidden !important; display: none !important;}
.stChatInput textarea::placeholder {
    color: #555555 !important;
    opacity: 1 !important;
}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("🌸 SAKURA Cottage Izukoge Concierge")
st.markdown(
    '<p style="font-size: 1.15rem; color: #333333;">SAKURAコテージ伊豆高原の宿泊ルールや設備、おすすめの周辺観光地についてお答えします。<br>This page will answer your questions about the rules, facilities, and recommended nearby tourist attractions at SAKURA Cottage Izu Kogen. Please enter your information in your preferred language.</p>',
    unsafe_allow_html=True
)

# ---------------------------------------------------------
# API Key Configuration
# ---------------------------------------------------------
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    api_key_input = st.sidebar.text_input("Gemini API Keyを入力してください", type="password")
    if api_key_input:
        api_key = api_key_input

if not api_key:
    st.warning("左側のサイドバーに Gemini API Key を入力してください。")
    st.stop()

st.sidebar.success("APIキーが設定されました")

# ---------------------------------------------------------
# Data Loading (Cached)
# ---------------------------------------------------------
@st.cache_resource
def load_context_data():
    sakurachat_dir = os.path.join(os.path.dirname(__file__), "sakurachat")
    context_text = "【SAKURA Cottage 基本情報・ルール・周辺施設】\n\n"
    
    if not os.path.exists(sakurachat_dir):
        return "エラー: sakurachat フォルダが見つかりません。"
    
    # 1. Markdownファイルの読み込み
    md_files = glob.glob(os.path.join(sakurachat_dir, "*.md"))
    for file_path in md_files:
        file_name = os.path.basename(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        context_text += f"---\n[File: {file_name}]\n{content}\n"
        
    # 2. Excelファイルの読み込み
    xlsx_files = glob.glob(os.path.join(sakurachat_dir, "*.xlsx"))
    for file_path in xlsx_files:
        file_name = os.path.basename(file_path)
        context_text += f"---\n[File: {file_name}]\n"
        try:
            excel_data = pd.read_excel(file_path, sheet_name=None)
            for sheet_name, df in excel_data.items():
                context_text += f"Sheet: {sheet_name}\n"
                context_text += df.to_csv(index=False) + "\n"
        except Exception as e:
            context_text += f"(Excel読み込みエラー: {str(e)})\n"
            
    return context_text

with st.spinner("資料を読み込んでいます..."):
    context_data = load_context_data()

if "エラー" in context_data:
    st.error(context_data)
    st.stop()

# ---------------------------------------------------------
# Chat Session Setup
# ---------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("質問を入力してください（例1：停電しました。例2：おすすめの周辺観光地は？）"):
    # Add user message to UI
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Prepare messages for Gemini API
    client = genai.Client(api_key=api_key)
    
    # Define system instructions (the context)
    current_time = datetime.datetime.now().strftime("%Y年%m月%d日 %H時%M分")
    system_instruction = f"""# 役割
あなたは「SAKURAコテージ伊豆高原」の専属AIコンシェルジュです。宿泊ゲストが滞在中に抱く疑問を解消し、伊豆高原での旅が最高のものになるようサポートすることが任務です。

# Context
以下の2つの顔を併せ持つプロフェッショナルとして振る舞ってください。

1. **宿の専門コンシェルジュ**：提供された資料デ―タ（ハウスルール、設備の使用方法、トラブル時のFAQなど）に基づき、正確かつ迅速に回答します。 ※重要：資料の情報に忠実に回答を作成しますが、必ずその内容を「ユーザーが質問した言語に全編翻訳」して出力してください。
2. **伊豆高原のプロ観光案内人**：提供された資料の観光地・カフェ・土産店データに基づき、ゲストのニーズに合わせた魅力的な提案を行います。※この2.は、基本資料の情報を利用し回答しますが、例えば所要時間など、Webを調査するともっと精度の高い回答が得られる場合はそちらを優先して回答を作ります。

# ガイドラインとスキル
* **正確な情報提供**: 上記1.の宿の設備（お湯が出ない等のトラブル）やハウスルールついては、資料ソースのみを参照し、誤った案内をしないようにしてください。※これは誤った案内によるクレーム発生や、事故防止などの観点から厳密に守るべき項目です。
* **おもてなしのトーン**: 親しみやすく丁寧な言葉遣いを用い、ゲストが「大切にされている」と感じるホスピタリティ溢れる対応をしてください。
* **付加価値の提案**: 上記2.については、単に質問に答えるだけでなく、「それなら、近くのこちらのカフェもおすすめですよ」といった、旅を楽しくするプラスアルファの提案を心がけてください。
* **現在時刻と季節感**: 現在時刻（{current_time}）を意識し、季節に合わせた服装のアドバイスや旬の観光スポットを案内してください。

# 応答ルール
1. **言語の厳守 (CRITICAL LANGUAGE RULE)**: You MUST strictly reply in the EXACT same language that the user used. If the user types in English, you MUST answer entirely in English. ユーザーが日本語で入力した場合は日本語で、英語で入力した場合は必ず英語で返答してください。いかなる場合もこの言語ルールを最優先してください。
2. **結論/回答**: ゲストの質問に対する答えを最初に提示します。
3. **補足情報（必要に応じて）**: 箇条書きを使用して、操作手順や詳細情報を分かりやすく伝えます。
4. **断り書き**: 1つの質問につき必ず1つ「ご注意：これはAIからの回答です。AIは間違えることがあります。万が一回答に誤りがあってもそれを保証するものではありません」(※回答言語に合わせて翻訳すること)を行末に加えてください。
5. **旅を彩る一言**: 「素敵な思い出になりますように」といった温かいメッセージ(※回答言語に合わせて翻訳)で締めくくります。
6. **緊急時の連絡先案内**: 緊急時やトラブル時の連絡について言及する場合、「緊急時ですので、時間外でもご連絡ください。」などの文言は使わず、常に「チャットまたは電話でご連絡ください」と案内してください。

# 資料データ
{context_data}
"""
    
    # Format chat history for google-genai
    formatted_messages = []
    for i, msg in enumerate(st.session_state.messages):
        role = "user" if msg["role"] == "user" else "model"
        text_content = msg["content"]
        
        # 最後のユーザーメッセージにのみ、言語強制ルールを不可視で追加
        if i == len(st.session_state.messages) - 1 and role == "user":
            text_content += "\n\n[CRITICAL SYSTEM RULE: You MUST reply ALL content in the EXACT language used in the message above. You are STRICTLY FORBIDDEN from outputting Japanese if the user wrote in English. ALL information retrieved from the context (including bullet points, steps, and rules) MUST be fully translated into the user's language before providing it.]"
            
        formatted_messages.append(
            types.Content(role=role, parts=[types.Part.from_text(text=text_content)])
        )

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.4,
        tools=[{"google_search": {}}]
    )

    with st.chat_message("assistant"):
        with st.spinner("回答を生成中..."):
            try:
                # API Call using gemini-2.5-flash
                # We can use the contents list to pass the full history
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=formatted_messages,
                    config=config
                )
                answer = response.text
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # Log to Google Sheets via GAS Webhook
                try:
                    import requests
                    webhook_url = "https://script.google.com/macros/s/AKfycbzBy9MkDfYd1N5XQ85E_pjDa--tb_-hQbrCXuRrAett4zQ5EN8jPQdOtel6atBj08xN/exec"
                    log_data = {
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "user_prompt": prompt,
                        "ai_response": answer
                    }
                    requests.post(webhook_url, json=log_data, timeout=5)
                except Exception as log_e:
                    st.toast(f"ログの保存に失敗しました: {log_e}")
                    
            except Exception as e:
                st.error(f"エラーが発生しました: {str(e)}")
