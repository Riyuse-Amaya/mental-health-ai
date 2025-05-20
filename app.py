from flask import Flask, request, jsonify, render_template, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask import redirect
import os
import uuid
import traceback
import spacy
from mlask import MLAsk
import unicodedata
import random
import csv
import re
from io import StringIO
from flask import Response
from dotenv import load_dotenv

# ✅ .env 読み込み（このタイミングで実行）
load_dotenv()


# ✅ パス設定
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.urandom(24)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "instance", "chat.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

nlp = spacy.load("ja_ginza")
emotion_analyzer = MLAsk()

# ✅ モデル定義
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    preferred_response_type = db.Column(db.String(10), nullable=False, default="共感")
    last_psychological_state = db.Column(db.String(20), nullable=False, default="普通")
    previous_psychological_state = db.Column(db.String(20), nullable=False, default="普通")
    stress_count = db.Column(db.Integer, nullable=False, default=0)
    department = db.Column(db.String(50))
    age_group = db.Column(db.String(20))

from datetime import datetime  # ← 追加

class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), db.ForeignKey("user.session_id"), nullable=False)
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    department = db.Column(db.String(50))
    age_group = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    psychological_state = db.Column(db.String(20))  # ← ✅ 追加
    harassment_flag = db.Column(db.Boolean, default=False)
    sensitive_flag = db.Column(db.Boolean, default=False)


# ✅ アドバイス生成
def provide_advice(state):
    if state == "ストレスが高い":
        advice_list = [
            "無理をせず、まずは深呼吸をしてリラックスしてみましょう。",
            "ストレスを感じたら、一度手を止めてゆっくりお茶を飲む時間を作るのもおすすめです。",
            "誰かに話すだけでも心が軽くなります。信頼できる人に少し話してみては？",
            "心と身体の回復のために、睡眠をしっかり取ることも大切です。",
            "日光を浴びて散歩するだけでも、気分が少し和らぐかもしれません。",
            "気持ちが落ち着かないときは、軽い運動やストレッチを取り入れてみましょう。"
        ]
        return random.choice(advice_list), "https://www.mhlw.go.jp/kokoro/soudan.html"

    elif state == "気分が良い":
        advice_list = [
            "その良い気分を持続させるために、好きなことをたくさん楽しみましょう！",
            "ポジティブな気持ちを、周りの人にも分けてあげるとさらに気分が上がりますよ！",
            "この気分を忘れないように日記に残してみるのもおすすめです。",
            "気分が良い日は、新しいことにチャレンジする絶好のチャンスです！",
            "笑顔の時間を意識的に作ると、気持ちの良さがさらに深まりますよ。"
        ]
        return random.choice(advice_list), None

    else:  # 普通
        advice_list = [
            "今の穏やかな状態を大切にしながら、小さな楽しみを見つけてみましょう。",
            "少しの運動や自然の中を歩くと、気持ちがリフレッシュできますよ。",
            "心が落ち着いているときに、自分の内面と向き合ってみるのも良い時間です。",
            "いつも頑張っている自分をねぎらうことも忘れずに。",
            "少し先の予定に、楽しみを入れてみると気持ちが明るくなりますよ。"
        ]
        return random.choice(advice_list), None

# 追加：会話を続けるための質問テンプレート
FOLLOW_UP_QUESTIONS = [
    "その出来事でいちばん嬉しかったことは何ですか？",
    "もう少し詳しく教えてもらえますか？",
    "それを感じたとき、どんな気持ちでしたか？",
    "他にもシェアしたいことはありますか？",
    "その後、何か変化はありましたか？"
]

# ✅ 応答テンプレート関数（修正済み）
def get_response_by_mood(mood, response_type):
    responses = {
        "ストレスが高い": {
            "共感": [
                "とてもお疲れのようですね…。少し休む時間を作れそうですか？",
                "無理をしていませんか？自分をいたわることも大切ですよ。",
                "気持ちが沈んでいるときは、無理せず少し立ち止まっても大丈夫です。",
                "最近頑張りすぎていませんか？自分に優しくしてあげてください。",
                "心の声に耳を傾ける時間も大切です。ひと息つきましょう。",
                "しんどい気持ち、よく伝わってきました。話してくれてありがとう。",
                "何かに追われすぎていませんか？まずは深呼吸してみましょう。",
                "疲れがたまっているようですね。ゆっくり休めていますか？"
            ],
            "アドバイス": [
                "深呼吸やリラックスできる時間を作ると良いですよ。",
                "一度リフレッシュしてみてはいかがでしょうか？",
                "気分転換に外に出たり、好きな音楽を聴いてみるのもおすすめです。",
                "生活の中に小さな楽しみや安心できる時間を取り入れてみましょう。",
                "必要なときは、専門家に相談するのも前向きな選択です。",
                "自分の心のペースに合わせて、少しずつ進んでいけば大丈夫です。",
                "休息は贅沢ではなく、心のメンテナンスです。しっかり休んでください。",
                "焦らなくていいんです。今は自分のための時間を大切に。"
            ]
        },
        "気分が良い": {
            "共感": [
                "いい気分のようですね！その前向きなエネルギー、素敵です！",
                "ご機嫌ですね！何か嬉しいことがありましたか？",
                "そういう気持ち、どんどんシェアしていきましょう！",
                "素晴らしいです！今日一日がもっと良くなりそうですね！",
                "その元気、こちらにも伝わってきました！",
                "気持ちが明るいときって、周りにも良い影響を与えますよね！",
                "元気そうで何よりです。その調子を保ちましょう！",
                "楽しそうですね！今日という日を大切にしてくださいね。",
                "よく頑張りましたね！その努力、素晴らしいです！",
                "やり遂げたんですね！本当に立派です！",
                "すごいですね！そういう報告、とても嬉しいです！",
                "日々の小さな成功も、大きな一歩ですね！"
            ],
            "アドバイス": [
                "気分が良い日は、新しいことに挑戦するチャンスかもしれませんね！",
                "そのポジティブな気持ちを周りにもシェアしてみましょう！",
                "ご自身を褒めてあげる時間をつくるのも大切です。",
                "笑顔の多い一日を意識して過ごしてみると、もっと素敵な一日になりますよ。",
                "その気持ちを日記に書いておくと、後で読み返して元気をもらえますよ。",
                "気分が良い日は、大切な人に連絡を取ってみるのもおすすめです。",
                "その良い気分を維持できるよう、リラックスした時間も忘れずに。"
            ]
        },
        "普通": {
            "共感": [
                "少し落ち着いた一日ですか？何気ない日常も大切ですよね。",
                "特別なことがなくても、あなたの気持ちは大切です。",
                "今日の気分はまあまあ、そんな日もありますよね。",
                "気持ちが安定しているときも、自分を見つめるチャンスです。",
                "平穏な日も心のケアは忘れずに。",
                "普通の日常でも、自分の心を大切にしましょう。",
                "何気ない瞬間にこそ、幸せが隠れているかもしれません。"
            ],
            "アドバイス": [
                "ちょっとした気分転換に、深呼吸やストレッチをしてみては？",
                "普段の生活に小さな楽しみを取り入れてみましょう。",
                "普通の日こそ、自分にやさしくしてあげてくださいね。",
                "今の自分の気持ちに気づけるのも大切な力です。",
                "無理せず、でもできることを少しずつやってみましょう。",
                "平常なときにこそ、心の余裕を持つトレーニングになります。",
                "ゆったりとした時間を意識的にとってみましょう。"
            ]
        }
    }

    base = random.choice(
        responses.get(mood, responses["普通"]).get(response_type, responses["普通"]["共感"])
    )

    if mood in ("気分が良い", "普通"):
        follow = random.choice(FOLLOW_UP_QUESTIONS)
        return f"{base} {follow}"

    return base


# ✅ ハラスメントキーワードと検出関数
harassment_keywords = [
    "いじめ", "嫌がらせ", "無視された", "暴言", "パワハラ", "セクハラ", "モラハラ",
    "怒鳴られた", "強制された", "叩かれた", "暴力", "蹴られた", "圧力", "脅された"
]

def detect_harassment(text):
    normalized = unicodedata.normalize("NFKC", text)
    hiragana_text = to_hiragana(normalized).replace(" ", "")
    return any(keyword in hiragana_text for keyword in harassment_keywords)

# ✅ ひらがな変換のためのインポート（ファイル冒頭に追加しておく）
from pykakasi import kakasi

kakasi_inst = kakasi()
kakasi_inst.setMode("J", "H")  # 漢字→ひらがな
kakasi_inst.setMode("K", "H")  # カタカナ→ひらがな
kakasi_inst.setMode("H", "H")  # ひらがな→ひらがな（そのまま）
converter = kakasi_inst.getConverter()

def to_hiragana(text):
    return converter.do(text).replace(" ", "").lower()

def extract_nouns(text):
    doc = nlp(text)
    return [token.text for token in doc if token.pos_ == "NOUN"]

# ✅ トピック一貫性分析
def analyze_topic_consistency(current_text, session_id, limit=5):
    current_nouns = set(extract_nouns(current_text))
    if not current_nouns:
        return 0.0  # 名詞がない場合は一貫性なし

    past_logs = (
        ChatHistory.query
        .filter_by(session_id=session_id)
        .order_by(ChatHistory.id.desc())
        .limit(limit)
        .all()
    )

    past_noun_sets = [set(extract_nouns(log.user_message)) for log in past_logs]
    overlap_scores = [
        len(current_nouns & nouns) / len(current_nouns | nouns) if nouns else 0
        for nouns in past_noun_sets
    ]

    if not overlap_scores:
        return 0.0

    average_score = sum(overlap_scores) / len(overlap_scores)
    return average_score

# ✅ 時系列的なキーワード出現傾向
def get_keyword_trend(session_id, keywords, limit=10):
    logs = (
        ChatHistory.query
        .filter_by(session_id=session_id)
        .order_by(ChatHistory.id.desc())
        .limit(limit)
        .all()
    )

    trend = []
    for log in reversed(logs):  # 古い順に並べてカウント
        text = unicodedata.normalize("NFKC", log.user_message)
        text_hiragana = to_hiragana(text).replace(" ", "")
        count = sum(1 for kw in keywords if kw in text_hiragana)
        trend.append(count)

    return trend


# ✅ 感情分析本体

def analyze_mood(text):
    doc = nlp(text)
    tokens = [token.text for token in doc]
    wakati_text = " ".join(tokens)
    emotion = emotion_analyzer.analyze(wakati_text)
    print("🔍 ML-Askの結果:", emotion)

    normalized_text = unicodedata.normalize("NFKC", text)
    hiragana_text = to_hiragana(normalized_text).replace(" ", "")
    print("🧪 ひらがな変換後のテキスト:", hiragana_text)

    # ✅ 感情カテゴリを抽出（文字列でも辞書でも対応）
    emotion_data = emotion.get("emotion") if isinstance(emotion, dict) else None
    if isinstance(emotion_data, dict):
        emotions = set(emotion_data.keys())
    elif isinstance(emotion_data, str):
        emotions = {emotion_data}
    else:
        emotions = set()

    print("🧪 感情カテゴリ:", emotions)

    # ✅ 英語カテゴリに基づく感情セット
    is_stress_emotion = emotions.intersection({"anger", "fear", "dislike", "sadness"})
    is_positive_emotion = emotions.intersection({"joy", "relief", "like"})

    # ✅ キーワード判定（ひらがな対応）
    stress_keywords = [
        "つかれ", "つらい", "しんどい", "しにたい", "おこられた", "もうむり",
        "やばい", "きらい", "むかつく", "いらいら", "にがて", "きもちわるい", "いそがしい",
        "だるい", "ねむい", "へとへと", "すとれす", "きがおもい", "にげたい", "かなし",
        "おちこむ", "げんかい", "こどく", "ふあん", "ゆううつ", "どなられた", "ののしられた", "こわい", "もうだめ", "ひどいことをされた"
    ]
    positive_keywords = [
    "たのしい", "うれしい", "ほめられた", "ありがとう", "さいこう", "だいじょうぶ",
    "すき", "あいしてる", "あんしん", "おもしろい", "わらえた", "はっぴー", "いやされた",
    "げんきでた", "はげまされた", "ぽじてぃぶ", "じしんがある", "きぶんがいい", "すっきり", "まえむき", "しあわせ",
    "せいちょう", "できた", "がんばった", "しゅうちゅうできた", "たっせい",
    "しゅうりょう", "しゅくだいおわった", "まにあった", "ほめられて", "やりとげた",
    "うまくいった", "じぶんにかてた", "やくにたった", "いいかんじ", "のりこえた"
]

    import re
    contains_stress_word = any(re.search(word, hiragana_text) for word in stress_keywords)
    contains_positive_word = any(re.search(word, hiragana_text) for word in positive_keywords)

    print("🧪 キーワード判定（ストレス）:", contains_stress_word)
    print("🧪 キーワード判定（ポジティブ）:", contains_positive_word)

    # ✅ 最終的な感情の分類（優先度つき）
    if contains_stress_word:
        mood = "ストレスが高い"
    elif contains_positive_word:
        mood = "気分が良い"
    elif is_stress_emotion:
        mood = "ストレスが高い"
    elif is_positive_emotion:
        # joy 単体のみ → 普通 にする
        if emotions == {"joy"}:
            mood = "普通"
        else:
            mood = "気分が良い"
    else:
        mood = "普通"

    print("🧪 判定結果:", mood)
    return mood


# ✅ セッションID取得
@app.route("/session_info", methods=["GET"])
def session_info():
    if "session_id" not in session or not session["session_id"]:
        session["session_id"] = str(uuid.uuid4())
        db.session.add(User(session_id=session["session_id"]))
        db.session.commit()
    return jsonify({"session_id": session["session_id"]})

# ✅ プロフィール取得
@app.route("/get_profile", methods=["GET"])
def get_profile():
    if "session_id" not in session:
        return jsonify({"error": "セッションがありません"}), 400

    user = User.query.filter_by(session_id=session["session_id"]).first()
    if not user:
        return jsonify({"error": "ユーザーが見つかりません"}), 404

    return jsonify({
        "department": user.department,
        "age_group": user.age_group
    })

# ✅ プロフィール登録
@app.route("/set_profile", methods=["POST"])
def set_profile():
    if "session_id" not in session:
        return jsonify({"error": "セッションがありません"}), 400

    data = request.get_json()
    department = data.get("department")
    age_group = data.get("age_group")
    preferred_response_type = data.get("preferred_response_type")

    # ✅ 入力バリデーション
    valid_departments = [
        "営業部", "設計部", "IC部", "積算部", "工事部",
        "木材部", "Re:eiwa", "走る大工", "不動産部", "管理統括部"
    ]
    valid_age_groups = ["10代", "20代", "30代", "40代", "50代", "60代以上"]
    valid_response_types = ["共感", "アドバイス"]

    if not department or not age_group or not preferred_response_type:
        return jsonify({"error": "部署・年代・応答タイプをすべて入力してください"}), 400
    if department not in valid_departments or age_group not in valid_age_groups:
        return jsonify({"error": "無効な部署または年代です"}), 400
    if preferred_response_type not in valid_response_types:
        return jsonify({"error": "無効な応答タイプです"}), 400

    # ✅ ユーザーが存在しなければ作成
    user = User.query.filter_by(session_id=session["session_id"]).first()
    if not user:
        user = User(session_id=session["session_id"])
        db.session.add(user)

    # ✅ 各プロフィール情報の保存
    user.department = department
    user.age_group = age_group
    user.preferred_response_type = preferred_response_type
    db.session.commit()

    print(f"🧑‍💼 ユーザー情報 - セッションID: {user.session_id}, 部署: {user.department}, 年代: {user.age_group}, 応答タイプ: {user.preferred_response_type}")
    return jsonify({"message": "プロフィールを更新しました。"})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session_id = request.form.get("session_id")
        if session_id:
            session["session_id"] = session_id
            if not User.query.filter_by(session_id=session_id).first():
                db.session.add(User(session_id=session_id))
                db.session.commit()
            return redirect("/")
    return render_template("login.html")

# ✅ トップページ
from flask import redirect, url_for

@app.route("/")
def index():
    # ✅ セッションIDが未設定ならログイン画面にリダイレクト
    if "session_id" not in session or not session["session_id"]:
        return redirect(url_for("login"))

    # ✅ セッションIDに対応するユーザーが存在しなければログイン画面に戻す
    user = User.query.filter_by(session_id=session["session_id"]).first()
    if not user:
        return redirect(url_for("login"))

    return render_template("index.html")

# ✅ 直近ログの応答履歴を取得（文脈分析用）
def get_recent_mood_trend(session_id, limit=3):
    recent_logs = (
        ChatHistory.query
        .filter_by(session_id=session_id)
        .order_by(ChatHistory.id.desc())
        .limit(limit)
        .all()
    )
    return [log.bot_response for log in reversed(recent_logs)]

# センシティブキーワード一覧
SENSITIVE_KEYWORDS = [
    "死にたい", "消えたい", "いなくなりたい", "限界", "やめたい",
    "消えたくなる", "つらい", "もう無理", "終わりにしたい"
]

# センシティブ判定関数
def detect_sensitive_content(text):
    print("📣 センシティブ判定開始")
    normalized = unicodedata.normalize("NFKC", text.lower())
    hiragana_text = to_hiragana(normalized)

    for keyword in SENSITIVE_KEYWORDS:
        keyword_hiragana = to_hiragana(keyword)
        if keyword in normalized or keyword_hiragana in hiragana_text:
            print(f"🔍 センシティブキーワード検出: {keyword}")
            return True
    return False

@app.route("/chat", methods=["POST"])
def chat():
    if "session_id" not in session:
        return jsonify({"error": "セッションがありません"}), 400

    try:
        data = request.get_json()
        user_input = data.get("message", "").strip()

        print(f"🛠 ユーザー入力: {user_input}")
        print(f"🛠 センシティブ検出結果: {detect_sensitive_content(user_input)}")


        user = User.query.filter_by(session_id=session["session_id"]).first()
        if not user:
            return jsonify({"error": "ユーザーが見つかりません"}), 400

        if not user.department or not user.age_group:
            return jsonify({"error": "プロフィール（部署・年代）を先に設定してください。"}), 400

        previous_state = user.last_psychological_state
        mood = analyze_mood(user_input)

        user.stress_count = user.stress_count + 1 if mood == "ストレスが高い" else 0
        user.previous_psychological_state = previous_state
        user.last_psychological_state = mood
        db.session.commit()

        # ✅ センシティブ発言検出（優先処理）
        sensitive_flag = detect_sensitive_content(user_input)
        if sensitive_flag:
            response_text = (
                "そのようなお気持ちを打ち明けてくださってありがとうございます。\n"
                "つらい時には一人で抱えず、誰かに話すことがとても大切です。\n"
                "必要であれば、以下の相談窓口もご利用ください：\n"
                "📞 いのちの電話：https://www.find-help.jp/"
            )
            support = "https://www.find-help.jp/"

            db.session.add(ChatHistory(
                session_id=user.session_id,
                user_message=user_input,
                bot_response=response_text,
                department=user.department,
                age_group=user.age_group,
                psychological_state=mood,
                harassment_flag=False,
                sensitive_flag=True
            ))

            db.session.commit()

            return jsonify({
                "response": response_text,
                "state": mood,
                "support": support
            })

        # 通常の応答処理開始（センシティブでない場合）
        if user.stress_count >= 4:
            response_text = "ストレスが続いているようですね。無理せず専門家の相談を受けてみませんか？"
            support = "https://www.mhlw.go.jp/kokoro/soudan.html"
        elif user.stress_count == 3:
            response_text = "最近ストレスが続いていますね…大丈夫ですか？"
            support = None
        else:
            response_text = get_response_by_mood(mood, user.preferred_response_type)
            support = None

        if previous_state != mood:
            response_text += f"（前回の心理状態「{previous_state}」から変化がありますね）"

        recent_responses = get_recent_mood_trend(user.session_id)
        if len(recent_responses) >= 2:
            last = recent_responses[-1]
            second_last = recent_responses[-2]
            if "ストレス" in second_last and "ストレス" in last and mood == "ストレスが高い":
                response_text += " 最近ストレスの傾向が続いているようですね。心と体の休息を意識してみてくださいね。"
            elif "気分が良い" in second_last and mood == "ストレスが高い":
                response_text += " 少し気分が落ちているようですね。無理しないでください。"

        harassment_detected = detect_harassment(user_input)
        if harassment_detected:
            response_text += " ※ハラスメントの可能性がある内容が確認されました。困ったときは管理統括部に相談してくださいね。"
            if not support:
                support = "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000189195.html"

        advice, advice_support = provide_advice(mood)

        consistency_score = analyze_topic_consistency(user_input, user.session_id)
        if consistency_score is not None:
            if consistency_score < 0.2:
                response_text += "（最近の話題と少しずれているようですね。何かあったのかもしれませんね）"
            elif consistency_score > 0.7:
                response_text += "（最近の会話内容とつながりがありますね）"

        # ✅ 通常ログ保存
        db.session.add(ChatHistory(
            session_id=user.session_id,
            user_message=user_input,
            bot_response=response_text,
            department=user.department,
            age_group=user.age_group,
            psychological_state=mood,
            harassment_flag=harassment_detected,
            sensitive_flag=False
        ))

        if harassment_detected:
            db.session.add(ChatHistory(
                session_id="admin-notice",
                user_message=f"[通知] セッション {user.session_id} にてハラスメント疑いの発言: {user_input}",
                bot_response="管理統括部に通知されました。",
                department=user.department,
                age_group=user.age_group,
                psychological_state="ストレスが高い"
            ))

        db.session.commit()

        result = {
            "response": response_text,
            "state": mood,
            "advice": advice
        }
        if support or advice_support:
            result["support"] = support or advice_support

        return jsonify(result)

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": f"サーバー内部エラー: {str(e)}"}), 500



# ✅ ログアウト機能（関数外に置くこと）
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")



# ✅ ログ表示画面（logs.html へのレンダリング）
@app.route("/logs")
def view_logs():
    logs = ChatHistory.query.order_by(ChatHistory.id.desc()).all()
    users_raw = User.query.all()
    users = {user.session_id: user for user in users_raw}
    return render_template("logs.html", logs=logs, users=users)

# ✅ ここに CSVエクスポート機能を追加
@app.route("/export_csv")
def export_csv():
    logs = ChatHistory.query.order_by(ChatHistory.id.asc()).all()
    output = StringIO()
    writer = csv.writer(output)

    # ヘッダー行
    writer.writerow(["ID", "セッションID", "部署", "年代", "ユーザー発言", "AI応答", "心理状態", "日時"])

    for log in logs:
        writer.writerow([
            log.id,
            log.session_id,
            log.department or "",
            log.age_group or "",
            log.user_message,
            log.bot_response,
            log.psychological_state,
            log.timestamp.strftime('%Y-%m-%d %H:%M') if log.timestamp else ""
        ])

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=chat_logs.csv"
    return response

# ✅ JST変換フィルター
from datetime import timezone, timedelta

@app.template_filter("to_jst")
def to_jst(utc_dt):
    if utc_dt is None:
        return "N/A"
    jst = timezone(timedelta(hours=9))
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(jst).strftime('%Y-%m-%d %H:%M')

# ✅ メイン起動
if __name__ == "__main__":
    app.run(debug=True)
