import sqlite3
import bcrypt
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "nenep.db"

POINT_RULES = [
    (1, "Học sinh có hành động tích cực", 5, "khen", ""),
    (2, "Tham gia hỗ trợ sự kiện", 3, "khen", "Tính theo học sinh"),
    (3, "Nhặt được đồ rơi", 5, "khen", ""),
    (4, "Tỉ lệ điền phiếu khảo sát trên 90%", 30, "khen", "Theo thời hạn quy định"),
    (5, "Lớp đạt giải tập thể - Nhất", 30, "khen", "Cuộc thi trong trường"),
    (6, "Lớp đạt giải tập thể - Nhì", 20, "khen", "Cuộc thi trong trường"),
    (7, "Lớp đạt giải tập thể - Ba", 15, "khen", "Cuộc thi trong trường"),
    (8, "Lớp đạt giải tập thể - Phụ", 10, "khen", "Cuộc thi trong trường"),
    (9, "80% số ngày trong tuần đạt tiêu chuẩn vệ sinh lớp học", 30, "khen", "Theo tuần"),
    (10, "Đánh nhau", -30, "nenep", ""),
    (11, "Có thái độ chưa tốt với thầy cô", -30, "nenep", ""),
    (12, "Tàng trữ, sử dụng chất cấm", -30, "nenep", ""),
    (13, "Trộm cắp, trấn lột, tàng trữ, tiêu thụ tài sản do vi phạm mà có", -30, "nenep", ""),
    (14, "Cờ bạc/cá độ dưới mọi hình thức", -30, "nenep", ""),
    (15, "Lưu hành, tuyên truyền, sử dụng các phim, ảnh, sách, báo... có nội dung phản cảm, phản nhân văn", -30, "nenep", ""),
    (16, "Xúc phạm nhân phẩm, danh dự/xâm phạm thân thể người khác", -30, "nenep", ""),
    (17, "Phá hoại tài sản của nhà trường", -20, "nenep", ""),
    (18, "Gây gổ, xô xát làm mất trật tự, an ninh trong trường", -20, "nenep", ""),
    (19, "Tự ý ra khỏi trường", -10, "nenep", ""),
    (20, "Sử dụng thiết bị điện tử sai mục đích", -10, "nenep", ""),
    (21, "Trốn tiết", -10, "nenep", ""),
    (22, "Không tắt điện/điều hoà sau khi ra khỏi lớp", -10, "nenep", ""),
    (23, "Thể hiện tình cảm đôi lứa trong trường", -10, "nenep", ""),
    (24, "Tàng trữ/sử dụng chất cháy nổ", -10, "nenep", ""),
    (25, "Sử dụng điện thoại trong trường (từ 7h45-16h15)", -10, "nenep", ""),
    (26, "Cố ý phá hoại cảnh quan nhà trường", -10, "nenep", ""),
    (27, "Gây gổ, xô xát với bạn học", -10, "nenep", ""),
    (28, "Vi phạm quy chế thi", -10, "nenep", ""),
    (29, "Lớp học để giày, dép không đúng quy định", -10, "nenep", ""),
    (30, "Mang đồ ăn ngoài vào lớp liên hoan chưa có sự phê duyệt", -10, "nenep", ""),
    (31, "Sai đồng phục", -5, "nenep", ""),
    (32, "Đi học muộn", -5, "nenep", ""),
    (33, "Nói bậy", -5, "nenep", ""),
    (34, "Ăn quà vặt, mua quà vặt mang vào lớp trong và sau giờ học", -5, "nenep", ""),
    (35, "Vệ sinh lớp học không đạt 80% số buổi trong tuần", -20, "nenep", ""),
    (36, "Sử dụng nước uống để rửa tay/nô đùa", -5, "nenep", ""),
    (37, "Đá bóng/chơi thể thao trong lớp học và hành lang", -5, "nenep", ""),
    (38, "Nô đùa gây mất vệ sinh trường học", -5, "nenep", ""),
    (39, "Uống nước trực tiếp bằng miệng ở vòi cây nước", -5, "nenep", ""),
    (40, "Lấy hàng, bưu phẩm trong thời gian ở tại trường không có sự cho phép", -5, "nenep", ""),
    (41, "Mang động vật vào trường", -5, "nenep", ""),
    (42, "Tủ locker không có khoá", -1, "nenep", ""),
    (43, "Đi giày, dép trong lớp học", -5, "nenep", ""),
    (44, "Vào tiết muộn", -2, "nenep", ""),
    (45, "Tỉ lệ điền phiếu khảo sát sau sự kiện dưới 50%", -5, "nenep", ""),
    (46, "Thiếu túi ngủ", -5, "bantru", ""),
    (47, "Mất trật tự giờ bán trú", -5, "bantru", ""),
    (48, "Túi ngủ không để đúng quy định", -5, "bantru", ""),
    (49, "Trốn ngủ", -10, "bantru", ""),
    (50, "Tự ý đổi phòng ngủ", -10, "bantru", ""),
    (51, "Vào phòng ngủ muộn", -2, "bantru", ""),
    (52, "Vi phạm nề nếp bán trú giờ ăn", -10, "bantru", ""),
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT UNIQUE NOT NULL,
            password     TEXT NOT NULL,
            role         TEXT NOT NULL,
            display_name TEXT NOT NULL,
            folder       TEXT,
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS imported_files (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name    TEXT NOT NULL,
            source_type  TEXT NOT NULL,
            source_url   TEXT,
            folder       TEXT NOT NULL,
            uploaded_by  TEXT NOT NULL,
            row_count    INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'OK',
            imported_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS discipline_records (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date         TEXT,
            date_label   TEXT,
            week         TEXT,
            month        TEXT,
            level        TEXT,
            grade        TEXT,
            class_name   TEXT,
            student_id   TEXT,
            student_name TEXT,
            issue        TEXT,
            category     TEXT,
            point        REAL DEFAULT 0,
            note         TEXT,
            source_file  TEXT,
            source_sheet TEXT,
            is_violation INTEGER DEFAULT 0,
            file_id      INTEGER,
            folder       TEXT,
            FOREIGN KEY (file_id) REFERENCES imported_files(id)
        );

        CREATE TABLE IF NOT EXISTS point_rules (
            id          INTEGER PRIMARY KEY,
            keyword     TEXT UNIQUE NOT NULL,
            point       REAL NOT NULL,
            rule_type   TEXT NOT NULL,
            note        TEXT,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS upload_audit_logs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id           INTEGER,
            file_name         TEXT NOT NULL,
            folder            TEXT NOT NULL,
            action            TEXT NOT NULL,
            old_rows          INTEGER DEFAULT 0,
            new_rows          INTEGER DEFAULT 0,
            user              TEXT NOT NULL,
            reason            TEXT,
            required_password INTEGER DEFAULT 0,
            created_at        TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (file_id) REFERENCES imported_files(id)
        );
    """)

    existing_users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing_users == 0:
        default_users = [
            ("admin",   "admin123",   "admin",   "Quản trị viên", "all"),
            ("quanly",  "quanly123",  "quanly",  "Quản lý trường", "all"),
            ("giamthi", "giamthi123", "giamthi", "Bộ phận Giám thị", "giamthi"),
            ("bantru",  "bantru123",  "bantru",  "Bộ phận Bán trú", "bantru"),
        ]
        for username, password, role, display_name, folder in default_users:
            hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            cur.execute(
                "INSERT INTO users (username, password, role, display_name, folder) VALUES (?,?,?,?,?)",
                (username, hashed, role, display_name, folder)
            )

    cur.executemany(
        """
        INSERT INTO point_rules (id, keyword, point, rule_type, note, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        ON CONFLICT(id) DO UPDATE SET
            keyword=excluded.keyword,
            point=excluded.point,
            rule_type=excluded.rule_type,
            note=excluded.note,
            is_active=1
        """,
        POINT_RULES
    )

    conn.commit()
    conn.close()