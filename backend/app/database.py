import re
import psycopg2
import psycopg2.extras
import psycopg2.pool
from app.config import get_settings
from app.security import hash_password

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


# ──────────────────────────────────────────────────────────────────────────
# Compatibility shim: makes psycopg2 behave enough like sqlite3 that
# main.py / auth.py (written for sqlite3) don't need to change at all.
#   - translates "?" placeholders -> "%s"
#   - translates datetime('now') -> NOW() (formatted to match sqlite's TEXT output)
#   - translates PRAGMA table_info(x) -> information_schema query
#   - conn.execute(...) / cur.execute(...) both return something chainable
#     with .fetchone() / .fetchall() / .rowcount, like sqlite3 does
#   - cur.lastrowid works by transparently adding "RETURNING id" to INSERTs
#   - rows come back as dict-like objects, so row["col"] keeps working
# ──────────────────────────────────────────────────────────────────────────

_INSERT_RE = re.compile(r"^\s*INSERT\s+INTO\s+\w+", re.IGNORECASE)
_DATETIME_NOW_RE = re.compile(r"datetime\(\s*'now'\s*\)", re.IGNORECASE)
_PRAGMA_RE = re.compile(r"PRAGMA\s+table_info\((\w+)\)", re.IGNORECASE)


_VALUES_RE = re.compile(r"VALUES\s*\(\s*%s(?:\s*,\s*%s)*\s*\)", re.IGNORECASE)


def _translate(sql: str) -> str:
    sql = _DATETIME_NOW_RE.sub("NOW()", sql)
    sql = re.sub(r"\buser\b", '"user"', sql)  # "user" is a reserved word in Postgres
    sql = sql.replace("?", "%s")
    return sql


class PGCursor:
    def __init__(self, raw_cursor):
        self._cur = raw_cursor
        self._insert_happened = False

    def execute(self, sql, params=None):
        pragma_match = _PRAGMA_RE.search(sql)
        if pragma_match:
            table = pragma_match.group(1)
            self._cur.execute(
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s",
                (table,),
            )
            self._insert_happened = False
            return self

        pg_sql = _translate(sql)
        self._cur.execute(pg_sql, params or ())
        self._insert_happened = bool(_INSERT_RE.match(pg_sql))
        return self

    @property
    def lastrowid(self):
        # Lazy: only costs an extra query when main.py actually reads .lastrowid,
        # not on every single row inserted in a bulk-upload loop.
        if not self._insert_happened:
            return None
        try:
            tmp = self._cur.connection.cursor()
            tmp.execute("SELECT lastval()")
            row = tmp.fetchone()
            return row[0] if row else None
        except Exception:
            return None

    def executescript(self, sql):
        self._cur.execute(sql)
        return self

    def executemany(self, sql, seq_of_params):
        pg_sql = _translate(sql)
        seq_of_params = list(seq_of_params)
        m = _VALUES_RE.search(pg_sql)
        if _INSERT_RE.match(pg_sql) and m and seq_of_params:
            template_sql = pg_sql[:m.start()] + "VALUES %s" + pg_sql[m.end():]
            psycopg2.extras.execute_values(self._cur, template_sql, seq_of_params, page_size=500)
            self._insert_happened = True
        else:
            self._cur.executemany(pg_sql, seq_of_params)
            self._insert_happened = bool(_INSERT_RE.match(pg_sql))
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def rowcount(self):
        return self._cur.rowcount


class PGConnection:
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        return PGCursor(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def executescript(self, sql):
        return self.cursor().executescript(sql)

    def commit(self):
        self._conn.commit()

    def close(self):
        try:
            self._conn.rollback()  # reset any leftover open transaction before returning to the pool
        except Exception:
            pass
        _get_pool().putconn(self._conn)


_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=settings.database_url,
        )
    return _pool


def get_conn():
    raw_conn = _get_pool().getconn()
    return PGConnection(raw_conn)


def init_db():
    settings = get_settings()
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id           SERIAL PRIMARY KEY,
            username     TEXT UNIQUE NOT NULL,
            password     TEXT NOT NULL,
            role         TEXT NOT NULL,
            display_name TEXT NOT NULL,
            folder       TEXT,
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );

        CREATE TABLE IF NOT EXISTS imported_files (
            id           SERIAL PRIMARY KEY,
            file_name    TEXT NOT NULL,
            source_type  TEXT NOT NULL,
            source_url   TEXT,
            folder       TEXT NOT NULL,
            uploaded_by  TEXT NOT NULL,
            row_count    INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'OK',
            imported_at  TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );

        CREATE TABLE IF NOT EXISTS discipline_records (
            id           SERIAL PRIMARY KEY,
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
            created_at  TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );

        CREATE TABLE IF NOT EXISTS upload_audit_logs (
            id                SERIAL PRIMARY KEY,
            file_id           INTEGER,
            file_name         TEXT NOT NULL,
            folder            TEXT NOT NULL,
            action            TEXT NOT NULL,
            old_rows          INTEGER DEFAULT 0,
            new_rows          INTEGER DEFAULT 0,
            "user"            TEXT NOT NULL,
            reason            TEXT,
            required_password INTEGER DEFAULT 0,
            created_at        TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            FOREIGN KEY (file_id) REFERENCES imported_files(id)
        );
    """)

    legacy_admin = []
    if settings.bootstrap_admin_username and settings.bootstrap_admin_password:
        legacy_admin.append({
            "username": settings.bootstrap_admin_username,
            "password": settings.bootstrap_admin_password,
            "role": "admin",
            "display_name": settings.bootstrap_admin_display_name,
            "folder": "all",
        })

    bootstrap_users = settings.bootstrap_users or legacy_admin
    for user in bootstrap_users:
        cur.execute(
            """
            INSERT INTO users (username, password, role, display_name, folder, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(username) DO UPDATE SET
                password=excluded.password,
                role=excluded.role,
                display_name=excluded.display_name,
                folder=excluded.folder,
                is_active=1
            """,
            (
                user["username"],
                hash_password(user["password"]),
                user["role"],
                user["display_name"],
                user["folder"],
            )
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
