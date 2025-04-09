import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Union

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    status,
    Query, # 用來讀取查詢參數
    WebSocket,
    WebSocketDisconnect,
    Request # 用來獲取 Request headers (雖然此例不用)
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# --- 配置 ---
# 強烈建議從環境變數或配置文件讀取！
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key") # 請務必更換成強密鑰
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- 密碼處理 ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Pydantic 模型 ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Union[str, None] = None

class User(BaseModel):
    username: str
    email: Union[str, None] = None
    full_name: Union[str, None] = None
    disabled: Union[bool, None] = None

class UserInDB(User):
    hashed_password: str

# --- 模擬資料庫 ---
# 實際應用中應使用真實資料庫
fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": pwd_context.hash("secretpassword"), # 使用 bcrypt 加密
        "disabled": False,
    }
}

# --- 輔助函數 ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None

# --- JWT 創建與驗證 ---
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 這個函數用於從 Token 中獲取用戶，WebSocket 端點會用到
async def get_current_user_from_token(token: str) -> User | None:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None # 或 raise credentials_exception 如果你想更嚴格
        token_data = TokenData(username=username)
    except JWTError:
        return None # 或 raise credentials_exception

    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        return None # 或 raise credentials_exception
    return user

# --- FastAPI 應用 ---
app = FastAPI()

# --- 登入端點 (HTTP POST) ---
@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    user = get_user(fake_users_db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.disabled:
         raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- WebSocket 端點 ---
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    # !!! 關鍵：從查詢參數 ?token=... 讀取 token !!!
    token: Annotated[str | None, Query()] = None
):
    if token is None:
        # 如果沒有提供 token，直接關閉連接
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 驗證 Token 並獲取用戶
    user = await get_current_user_from_token(token)

    if user is None or user.disabled:
        # 如果 Token 無效或用戶被禁用，關閉連接
        print(f"WebSocket connection rejected for token: {token[:10]}...") # Log for debugging
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Token 有效，接受連接
    await websocket.accept()
    print(f"WebSocket connection accepted for user: {user.username}") # Log for debugging

    try:
        while True:
            # 接收客戶端消息
            data = await websocket.receive_text()
            print(f"Message from {user.username}: {data}") # Log for debugging
            # 回傳消息給客戶端
            await websocket.send_text(f"Message text was: {data}, from user: {user.username}")
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for user: {user.username}") # Log for debugging
    except Exception as e:
        print(f"Error in WebSocket for user {user.username}: {e}") # Log errors
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)


# --- 簡單的根路徑，方便測試服務是否運行 ---
@app.get("/")
async def read_root():
    return {"message": "Welcome to the JWT WebSocket Example API"}

# --- (可選) 提供一個簡單的 HTML 頁面用於測試 ---
from fastapi.responses import HTMLResponse

@app.get("/client", response_class=HTMLResponse)
async def get_client_page():
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>WebSocket Test Client</title>
        </head>
        <body>
            <h1>WebSocket Test Client</h1>
            <div>
                <h2>Login</h2>
                <label>Username: <input type="text" id="username" value="johndoe"></label><br>
                <label>Password: <input type="password" id="password" value="secretpassword"></label><br>
                <button onclick="login()">Login</button>
                <p>Status: <span id="loginStatus">Not logged in</span></p>
                <p>Token: <span id="tokenSpan" style="word-break: break-all;"></span></p>
            </div>
            <hr>
            <div>
                <h2>WebSocket</h2>
                <button onclick="connectWs()" id="connectButton" disabled>Connect WebSocket</button>
                <button onclick="disconnectWs()" id="disconnectButton" disabled>Disconnect</button>
                <p>WS Status: <span id="wsStatus">Disconnected</span></p>
                <label>Message: <input type="text" id="messageText" autocomplete="off"/></label>
                <button onclick="sendMessage()" id="sendButton" disabled>Send</button>
                <h2>Messages</h2>
                <ul id='messages'>
                </ul>
            </div>
            <script>
                let ws = null;
                let token = null;

                async function login() {
                    const username = document.getElementById('username').value;
                    const password = document.getElementById('password').value;
                    const loginStatus = document.getElementById('loginStatus');
                    const tokenSpan = document.getElementById('tokenSpan');
                    const connectButton = document.getElementById('connectButton');

                    const formData = new URLSearchParams();
                    formData.append('username', username);
                    formData.append('password', password);

                    loginStatus.textContent = 'Logging in...';
                    tokenSpan.textContent = '';
                    connectButton.disabled = true;

                    try {
                        const response = await fetch('/token', {
                            method: 'POST',
                            body: formData
                        });

                        if (!response.ok) {
                            const errorData = await response.json();
                            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                        }

                        const data = await response.json();
                        token = data.access_token;
                        loginStatus.textContent = 'Logged in successfully!';
                        tokenSpan.textContent = token;
                        connectButton.disabled = false;

                    } catch (error) {
                        console.error('Login failed:', error);
                        loginStatus.textContent = `Login Failed: ${error.message}`;
                        token = null;
                    }
                }

                function connectWs() {
                    if (!token) {
                        alert("Please login first to get a token.");
                        return;
                    }
                    if (ws) {
                        console.log("Already connected or connecting.");
                        return;
                    }

                    const wsStatus = document.getElementById('wsStatus');
                    const messages = document.getElementById('messages');
                    const sendButton = document.getElementById('sendButton');
                    const connectButton = document.getElementById('connectButton');
                    const disconnectButton = document.getElementById('disconnectButton');

                    // 重要：將 token 附加到查詢參數
                    const wsUrl = `ws://${window.location.host}/ws?token=${encodeURIComponent(token)}`;
                    ws = new WebSocket(wsUrl);
                    wsStatus.textContent = 'Connecting...';
                    messages.innerHTML = ''; // Clear previous messages
                    connectButton.disabled = true;


                    ws.onopen = function(event) {
                        wsStatus.textContent = 'Connected';
                        sendButton.disabled = false;
                        disconnectButton.disabled = false;
                        console.log("WebSocket connection opened");
                         // Optionally send an initial message
                        // ws.send("Hello Server!");
                    };

                    ws.onmessage = function(event) {
                        const message = event.data;
                        const messagesList = document.getElementById('messages');
                        const li = document.createElement('li');
                        li.textContent = `Received: ${message}`;
                        messagesList.appendChild(li);
                        console.log("Message from server: ", message);
                    };

                    ws.onerror = function(event) {
                        wsStatus.textContent = 'Error occurred';
                        console.error("WebSocket error observed:", event);
                        sendButton.disabled = true;
                        connectButton.disabled = false; // Allow retry after login
                        disconnectButton.disabled = true;
                         ws = null; // Reset ws object on error
                    };

                    ws.onclose = function(event) {
                        wsStatus.textContent = `Disconnected (Code: ${event.code}, Reason: ${event.reason || 'N/A'})`;
                        console.log("WebSocket connection closed:", event);
                        sendButton.disabled = true;
                        connectButton.disabled = !token; // Re-enable connect if still logged in
                        disconnectButton.disabled = true;
                        ws = null; // Important to nullify ws object
                    };
                }

                function disconnectWs() {
                     if (ws) {
                        ws.close();
                     }
                }

                function sendMessage(event) {
                    if (!ws || ws.readyState !== WebSocket.OPEN) {
                         console.log("WebSocket is not connected.");
                         return;
                    }
                    const input = document.getElementById("messageText")
                    ws.send(input.value);
                    input.value = '';
                    // event.preventDefault(); // Use if inside a form
                }

            </script>
        </body>
    </html>
    """

