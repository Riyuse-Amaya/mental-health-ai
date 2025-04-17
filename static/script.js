document.addEventListener("DOMContentLoaded", function () {
    console.log("✅ JavaScript ロード完了");

    const sendButton = document.getElementById("send-button");
    const userInput = document.getElementById("user-input");
    const toggleThemeBtn = document.getElementById("toggle-theme-btn");
    const setProfileBtn = document.getElementById("set-profile-btn");
    const body = document.body;

    // ✅ セッションIDを取得して表示
    fetch("/session_info")
        .then(response => response.json())
        .then(data => {
            document.getElementById("session-info").textContent = "🆔 セッションID: " + data.session_id;
        })
        .catch(error => {
            console.error("❌ セッション情報取得エラー:", error);
        });

    // ✅ プロフィール取得してUIに反映
    fetch("/get_profile")
        .then(res => res.json())
        .then(data => {
            console.log("📋 現在のプロフィール:", data);
            if (data.department) {
                document.getElementById("department").value = data.department;
            }
            if (data.age_group) {
                document.getElementById("age_group").value = data.age_group;
            }
        })
        .catch(err => {
            console.error("❌ プロフィール取得エラー:", err);
        });

    // ✅ テーマ切り替え
    if (toggleThemeBtn) {
        toggleThemeBtn.addEventListener("click", () => {
            body.classList.toggle("dark-theme");
            toggleThemeBtn.textContent = body.classList.contains("dark-theme")
                ? "ライトテーマに切り替え"
                : "ダークテーマに切り替え";
        });
    }

    // ✅ プロフィール送信処理
    if (setProfileBtn) {
        setProfileBtn.addEventListener("click", () => {
    const department = document.getElementById("department").value;
const ageGroup = document.getElementById("age_group").value;
const responseType = document.getElementById("preferred_response_type").value; // ←追加

fetch("/set_profile", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ 
    department, 
    age_group: ageGroup, 
    preferred_response_type: responseType // ✅ ←ここ修正！
  })
})



                .then(res => {
                    if (!res.ok) {
                        return res.json().then(err => {
                            throw new Error(`サーバーエラー: ${res.status} - ${err.error || '不明なエラー'}`);
                        });
                    }
                    return res.json();
                })
                .then(data => {
                    alert("✅ プロフィールが設定されました。");
                    console.log("📋 プロフィール送信成功:", department, ageGroup);
                })
                .catch(err => {
                    alert("❌ プロフィール送信に失敗しました: " + err.message);
                    console.error("送信エラー:", err);
                });
        });
    }

    // ✅ メッセージ送信
    if (!sendButton || !userInput) {
        console.error("❌ エラー: 必要な要素が見つかりません。");
        return;
    }

    sendButton.addEventListener("click", sendMessage);
    userInput.addEventListener("keypress", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            sendMessage();
        }
    });
});

// ✅ メッセージ送信関数
function sendMessage() {
    const userInputElement = document.getElementById("user-input");
    const userInput = userInputElement.value.trim();
    if (userInput === "") return;
const department = document.getElementById("department").value;
const ageGroup = document.getElementById("age_group").value;

if (!department || !ageGroup) {
    alert("⚠️ チャットを送る前にプロフィール（部署と年代）を設定してください。");
    return;
}

    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML += `<div class='message user-message'>${userInput}</div>`;
    userInputElement.value = "";
    chatBox.scrollTop = chatBox.scrollHeight;

    const loadingMessage = document.createElement("div");
    loadingMessage.className = "message bot-message";
    loadingMessage.textContent = "AI: 送信中...";
    chatBox.appendChild(loadingMessage);
    chatBox.scrollTop = chatBox.scrollHeight;

    const sendButton = document.getElementById("send-button");
    if (sendButton) sendButton.disabled = true;

    fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userInput })
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`サーバーエラー: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            loadingMessage.remove();
            chatBox.innerHTML += `<div class='message bot-message'>AI: ${data.response}</div>`;

            if (data.advice) {
                chatBox.innerHTML += `<div class='message bot-message'><strong>アドバイス:</strong> ${data.advice}</div>`;
            }
            if (data.support) {
                chatBox.innerHTML += `<div class='message bot-message'><strong>専門機関:</strong> <a href="${data.support}" target="_blank">相談窓口</a></div>`;
            }

            chatBox.scrollTop = chatBox.scrollHeight;
        })
        .catch(error => {
            console.error("❌ エラー:", error);
            loadingMessage.remove();
            chatBox.innerHTML += `<div class='message bot-message' style="color:red;">エラー: メッセージを送信できませんでした。</div>`;
        })
        .finally(() => {
            if (sendButton) sendButton.disabled = false;
        });
}
