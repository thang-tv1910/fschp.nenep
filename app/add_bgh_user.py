import bcrypt
from database import get_conn

conn = get_conn()
cur = conn.cursor()

username = "bgh"
password = "bgh123"
role = "bangiamhieu"
display_name = "Ban Giám Hiệu"
folder = "all"

hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

cur.execute("""
    INSERT OR REPLACE INTO users
    (username, password, role, display_name, folder, is_active)
    VALUES (?, ?, ?, ?, ?, 1)
""", (username, hashed, role, display_name, folder))

conn.commit()
conn.close()

print("Đã tạo tài khoản Ban Giám Hiệu: bgh / bgh123")