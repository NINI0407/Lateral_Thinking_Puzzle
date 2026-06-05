簡報可能可以用的內容
* 密碼安全性
✅ 密碼使用 SHA256 加密存儲（不存明文）
✅ 帳號和郵箱 唯一性檢查
✅ 密碼 至少6個字符 要求
✅ 帳號 3-20個字符 限制
✅ 登入狀態保存在 客戶端localStorage


* 用 ngrok 讓其他人可以直接玩遊戲：
用 ngrok 的概念是：你的電腦主動連到 ngrok 雲端，ngrok 給你一個公開網址，其他玩家連那個網址，流量再轉回你本機的 5678。這通常不用開防火牆或路由器 port forwarding。

步驟如下：

安裝 ngrok
到 https://ngrok.com/download 下載 Windows 版。

登入 ngrok 帳號，取得 authtoken
ngrok dashboard 會給你一行類似：

ngrok config add-authtoken 你的_token
在 PowerShell 執行一次即可。

啟動你的遊戲伺服器
在專案資料夾執行：
python server.py
你的專案目前是跑在：

http://localhost:5678
另開一個 PowerShell，啟動 ngrok：
ngrok http 5678
ngrok 會顯示類似：
Forwarding  https://xxxx-xxxx.ngrok-free.app -> http://localhost:5678
把 https://xxxx-xxxx.ngrok-free.app 給其他玩家，他們就可以直接進入遊戲。

注意幾點：

不要給玩家 localhost:5678，那只會連到玩家自己的電腦。
免費版 ngrok 網址通常每次重開都會變。
你的 server.py 必須持續開著，ngrok 視窗也不能關。
如果玩家看到 ngrok 的提示頁，按繼續即可。
因為 ngrok 是公開網址，陌生人拿到網址也能進來，測試完建議關掉 ngrok。
停止 ngrok：在 ngrok 那個 PowerShell 視窗按 Ctrl + C。

官方文件說明：ngrok http <port> 會建立公開 URL，並把流量轉到你的本機 port；ngrok agent 是主動連到 ngrok cloud，所以不需要開 inbound port。
來源：https://ngrok.com/docs/guides/share-localhost/tunnels 和 https://ngrok.com/docs/http/