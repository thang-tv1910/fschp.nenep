from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from datetime import timedelta, datetime
from pathlib import Path
import os
import re
import tempfile
import time
import requests
from urllib.parse import urlparse

from app.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.config import get_settings
from app.database import get_conn, init_db
from app.parser import parse_excel
from app.security import verify_password

settings = get_settings()
FRONTEND_DIR = settings.frontend_dir
RATE_LIMIT_BUCKETS: dict[tuple[str, str], list[float]] = {}
ALLOWED_ROLES = {"admin", "bangiamhieu", "quanly", "giamthi", "bantru"}
GLOBAL_ROLES = {"admin", "bangiamhieu", "quanly"}
UPLOAD_EXTENSIONS = {".xlsx", ".xls"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
SAFE_FILENAME_RE = re.compile(r"^[\w .()\-]+$", re.UNICODE)

app = FastAPI(title="FSCHP Nề nếp API")


class DriveLinkRequest(BaseModel):
    url: str = Field(min_length=20, max_length=500)
    overwrite: bool = False
    reason: str = Field(default="", max_length=500)
    override_password: str = Field(default="", max_length=200)


@app.on_event("startup")
def startup():
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


def rate_limit_key(request: Request) -> str:
    client_host = request.client.host if request.client else "unknown"
    return client_host


def enforce_rate_limit(request: Request, bucket_name: str, max_requests: int):
    now = time.time()
    key = (bucket_name, rate_limit_key(request))
    cutoff = now - settings.rate_limit_window_seconds
    entries = [timestamp for timestamp in RATE_LIMIT_BUCKETS.get(key, []) if timestamp >= cutoff]
    if len(entries) >= max_requests:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    entries.append(now)
    RATE_LIMIT_BUCKETS[key] = entries


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.url.path == "/auth/login":
        enforce_rate_limit(request, "auth", settings.auth_rate_limit)
    elif request.url.path.startswith(("/data/", "/upload/", "/auth/me")):
        enforce_rate_limit(request, "api", settings.api_rate_limit)

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if settings.cookie_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data:; font-src 'self' data: https://fonts.gstatic.com; connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    )
    response.headers.setdefault("Cache-Control", "no-store" if request.url.path.startswith("/auth/") else "private")
    return response


@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/login.html")
def login_page():
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/dashboard.html")
def dashboard_page():
    return FileResponse(FRONTEND_DIR / "dashboard.html")


@app.post("/auth/login")
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai tên đăng nhập hoặc mật khẩu"
        )

    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    response.set_cookie(
        key=settings.cookie_name,
        value=access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )

    return {
        "role": user["role"],
        "display_name": user["display_name"]
    }


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return {"message": "Đã đăng xuất"}


@app.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


def parse_sqlite_datetime(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None


def verify_override_password(password: str):
    if not settings.override_password_hash:
        raise HTTPException(
            status_code=500,
            detail="Override password is not configured"
        )
    if not verify_password(password, settings.override_password_hash):
        raise HTTPException(
            status_code=403,
            detail="Mật khẩu xác nhận chỉnh sửa sau 24h không đúng"
        )


def normalize_user_folder(current_user: dict) -> str:
    role = current_user.get("role", "")
    folder = current_user.get("folder") or role
    if role in GLOBAL_ROLES and folder == "all":
        return "all"
    if folder == "all":
        return role
    return folder


def upload_folder_for_user(current_user: dict) -> str:
    folder = normalize_user_folder(current_user)
    return "giamthi" if folder == "all" else folder


def assert_role(current_user: dict, allowed_roles: set[str]):
    role = current_user.get("role", "")
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")


def validate_file_name(file_name: str) -> str:
    cleaned = Path(file_name or "").name.strip()
    if not cleaned or len(cleaned) > 180 or not SAFE_FILENAME_RE.match(cleaned):
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ")
    suffix = Path(cleaned).suffix.lower()
    if suffix not in UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file Excel .xlsx hoặc .xls")
    return cleaned


def write_upload_to_temp(file: UploadFile, tmp_file):
    total = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File vượt quá giới hạn 15MB")
        tmp_file.write(chunk)


def validate_google_sheet_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {"docs.google.com", "www.docs.google.com"}:
        raise HTTPException(status_code=400, detail="Link Google Sheet không hợp lệ")
    sheet_id = extract_google_sheet_id(url)
    if not sheet_id:
        raise HTTPException(status_code=400, detail="Link Google Sheet không hợp lệ")
    return sheet_id


def download_to_temp(url: str, tmp_file):
    total = 0
    with requests.get(url, timeout=30, stream=True) as response:
        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail="Không tải được Google Sheet. Hãy kiểm tra file đã để public chưa."
            )
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Google Sheet export vượt quá giới hạn 15MB")
            tmp_file.write(chunk)


def get_existing_file(file_name, folder):
    conn = get_conn()
    file = conn.execute("""
        SELECT *
        FROM imported_files
        WHERE file_name = ?
          AND folder = ?
          AND status != 'DELETED'
        ORDER BY id DESC
        LIMIT 1
    """, (file_name, folder)).fetchone()
    conn.close()
    return dict(file) if file else None


@app.get("/upload/check-duplicate")
def check_duplicate(
    file_name: str = Query(..., min_length=1, max_length=180),
    current_user: dict = Depends(get_current_user)
):
    assert_role(current_user, ALLOWED_ROLES)
    file_name = validate_file_name(file_name)
    role = current_user["role"]
    if role not in ["admin", "bangiamhieu", "quanly", "giamthi", "bantru"]:
        raise HTTPException(status_code=403, detail="Không có quyền upload")

    folder = upload_folder_for_user(current_user)

    old_file = get_existing_file(file_name, folder)
    if not old_file:
        return {
            "exists": False,
            "requires_password": False,
            "message": "File chưa tồn tại"
        }

    imported_at = parse_sqlite_datetime(old_file.get("imported_at"))
    age_hours = 0
    if imported_at:
        age_hours = ((datetime.utcnow() + timedelta(hours=7)) - imported_at).total_seconds() / 3600

    requires_password = age_hours >= 24 and role != "admin"

    return {
        "exists": True,
        "file": old_file,
        "age_hours": round(age_hours, 2),
        "requires_password": requires_password,
        "message": "File đã tồn tại"
    }


def save_rows_to_db(
    rows,
    file_name,
    source_type,
    folder,
    uploaded_by,
    source_url=None,
    overwrite=False,
    reason="",
    override_password="",
    current_role=""
):
    if not rows:
        raise HTTPException(status_code=400, detail="Không tìm thấy dữ liệu hợp lệ trong file")

    conn = get_conn()
    cur = conn.cursor()

    old_file = cur.execute("""
        SELECT *
        FROM imported_files
        WHERE file_name = ?
          AND folder = ?
          AND status != 'DELETED'
        ORDER BY id DESC
        LIMIT 1
    """, (file_name, folder)).fetchone()

    replaced = False
    old_deleted_rows = 0
    required_password = 0

    if old_file:
        imported_at = parse_sqlite_datetime(old_file["imported_at"])
        age_hours = 0
        if imported_at:
            age_hours = (datetime.now() - imported_at).total_seconds() / 3600

        if not overwrite:
            conn.close()
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "File đã tồn tại. Bạn có muốn ghi đè không?",
                    "file_name": file_name,
                    "folder": folder,
                    "old_rows": old_file["row_count"],
                    "imported_at": old_file["imported_at"],
                    "age_hours": round(age_hours, 2),
                    "requires_password": age_hours >= 24 and current_role != "admin"
                }
            )

        if age_hours >= 24 and current_role != "admin":
            required_password = 1

            if not reason or not reason.strip():
                conn.close()
                raise HTTPException(
                    status_code=400,
                    detail="File đã quá 24h. Cần nhập lý do chỉnh sửa số liệu."
                )

            try:
                verify_override_password(override_password)
            except HTTPException:
                conn.close()
                raise

        old_file_id = old_file["id"]

        old_deleted_rows = cur.execute("""
            DELETE FROM discipline_records
            WHERE file_id = ?
        """, (old_file_id,)).rowcount

        cur.execute("""
            UPDATE imported_files
            SET source_type = ?,
                source_url = ?,
                uploaded_by = ?,
                row_count = ?,
                status = 'OK',
                imported_at = datetime('now')
            WHERE id = ?
        """, (
            source_type,
            source_url,
            uploaded_by,
            len(rows),
            old_file_id
        ))

        file_id = old_file_id
        replaced = True

    else:
        cur.execute("""
            INSERT INTO imported_files
            (file_name, source_type, source_url, folder, uploaded_by, row_count, status)
            VALUES (?, ?, ?, ?, ?, ?, 'OK')
        """, (file_name, source_type, source_url, folder, uploaded_by, len(rows)))

        file_id = cur.lastrowid

    for r in rows:
        cur.execute("""
            INSERT INTO discipline_records
            (date, date_label, week, month, level, grade, class_name,
             student_id, student_name, issue, category, point, note,
             source_file, source_sheet, is_violation, file_id, folder)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            r.get("date"),
            r.get("date_label"),
            r.get("week"),
            r.get("month"),
            r.get("level"),
            r.get("grade"),
            r.get("class_name"),
            r.get("student_id"),
            r.get("student_name"),
            r.get("issue"),
            r.get("category"),
            r.get("point"),
            r.get("note"),
            r.get("source_file"),
            r.get("source_sheet"),
            r.get("is_violation"),
            file_id,
            r.get("folder", folder)
        ))

    cur.execute("""
        INSERT INTO upload_audit_logs
        (file_id, file_name, folder, action, old_rows, new_rows, user, reason, required_password)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        file_id,
        file_name,
        folder,
        "replace" if replaced else "upload",
        old_deleted_rows,
        len(rows),
        uploaded_by,
        reason,
        required_password
    ))

    conn.commit()
    conn.close()

    return {
        "file_id": file_id,
        "replaced": replaced,
        "old_deleted_rows": old_deleted_rows,
        "new_rows": len(rows),
        "required_password": required_password
    }


@app.post("/upload/excel")
async def upload_excel(
    file: UploadFile = File(...),
    overwrite: bool = Form(False),
    reason: str = Form(""),
    override_password: str = Form(""),
    current_user: dict = Depends(get_current_user)
):
    assert_role(current_user, ALLOWED_ROLES)
    role = current_user["role"]
    if role not in ["admin", "bangiamhieu", "quanly", "giamthi", "bantru"]:
        raise HTTPException(status_code=403, detail="Không có quyền upload")

    folder = upload_folder_for_user(current_user)
    file_name = validate_file_name(file.filename)

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file Excel (.xlsx, .xls)")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")

    try:
        write_upload_to_temp(file, tmp)
        tmp.close()

        rows = parse_excel(tmp.name, folder, file_name)

        result = save_rows_to_db(
            rows=rows,
            file_name=file_name,
            source_type="excel",
            folder=folder,
            uploaded_by=current_user["username"],
            overwrite=overwrite,
            reason=reason,
            override_password=override_password,
            current_role=role
        )

        return {
            "message": "Đã thay thế file cũ" if result["replaced"] else "Upload thành công",
            "file": file_name,
            "rows": result["new_rows"],
            "folder": folder,
            "replaced": result["replaced"],
            "old_deleted_rows": result["old_deleted_rows"],
            "required_password": result["required_password"]
        }

    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def extract_google_sheet_id(url: str):
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    return None


@app.post("/upload/drive-link")
def upload_drive_link(
    payload: DriveLinkRequest,
    current_user: dict = Depends(get_current_user)
):
    role = current_user["role"]
    if role not in ["admin", "giamthi", "bantru"]:
        raise HTTPException(status_code=403, detail="Không có quyền upload")

    folder = upload_folder_for_user(current_user)

    sheet_id = validate_google_sheet_url(payload.url)
    if not sheet_id:
        raise HTTPException(status_code=400, detail="Link Google Sheet không hợp lệ")

    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")

    try:
        download_to_temp(export_url, tmp)

        tmp.close()

        file_name = f"GoogleSheet_{sheet_id}.xlsx"
        rows = parse_excel(tmp.name, folder, file_name)

        result = save_rows_to_db(
            rows=rows,
            file_name=file_name,
            source_type="google_sheet",
            source_url=payload.url,
            folder=folder,
            uploaded_by=current_user["username"],
            overwrite=payload.overwrite,
            reason=payload.reason,
            override_password=payload.override_password,
            current_role=role
        )

        return {
            "message": "Đã thay thế Google Sheet cũ" if result["replaced"] else "Import Google Sheet thành công",
            "source_url": payload.url,
            "file": file_name,
            "rows": result["new_rows"],
            "folder": folder,
            "replaced": result["replaced"],
            "old_deleted_rows": result["old_deleted_rows"],
            "required_password": result["required_password"]
        }

    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@app.get("/data/rows")
def get_all_rows(current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    role = current_user["role"]
    folder = normalize_user_folder(current_user)

    if role in GLOBAL_ROLES:
        rows = conn.execute("""
            SELECT * FROM discipline_records
            ORDER BY date DESC, id DESC
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM discipline_records
            WHERE folder=?
            ORDER BY date DESC, id DESC
        """, (folder,)).fetchall()

    conn.close()
    return {"rows": [dict(r) for r in rows], "total": len(rows)}


@app.get("/data/files")
def get_imported_files(current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    role = current_user["role"]
    folder = normalize_user_folder(current_user)

    if role in GLOBAL_ROLES:
        files = conn.execute("""
            SELECT * FROM imported_files
            WHERE status != 'DELETED'
            ORDER BY imported_at DESC
        """).fetchall()
    else:
        files = conn.execute("""
            SELECT * FROM imported_files
            WHERE folder=? AND status != 'DELETED'
            ORDER BY imported_at DESC
        """, (folder,)).fetchall()

    conn.close()
    return {"files": [dict(f) for f in files]}


@app.get("/data/audit-logs")
def get_audit_logs(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "quanly"]:
        raise HTTPException(status_code=403, detail="Không có quyền xem lịch sử chỉnh sửa")

    conn = get_conn()
    logs = conn.execute("""
        SELECT *
        FROM upload_audit_logs
        ORDER BY created_at DESC
        LIMIT 300
    """).fetchall()
    conn.close()

    return {"logs": [dict(l) for l in logs]}


@app.delete("/data/files/{file_id}")
def delete_file_data(file_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được xóa")

    conn = get_conn()
    cur = conn.cursor()

    file = conn.execute(
        "SELECT * FROM imported_files WHERE id=?",
        (file_id,)
    ).fetchone()

    if not file:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy file")

    deleted = cur.execute(
        "DELETE FROM discipline_records WHERE file_id=?",
        (file_id,)
    ).rowcount

    cur.execute(
        "DELETE FROM imported_files WHERE id=?",
        (file_id,)
    )

    cur.execute("""
        INSERT INTO upload_audit_logs
        (file_id, file_name, folder, action, old_rows, new_rows, user, reason, required_password)
        VALUES (?, ?, ?, 'delete', ?, 0, ?, ?, 0)
    """, (
        file_id,
        file["file_name"],
        file["folder"],
        deleted,
        current_user["username"],
        "Admin xóa file"
    ))

    conn.commit()
    conn.close()

    return {
        "message": "Đã xóa",
        "file": dict(file)["file_name"],
        "deleted_rows": deleted
    }


@app.get("/data/permissions")
def get_permissions(current_user: dict = Depends(get_current_user)):
    ROLE_PERMISSIONS = {
    "admin": {
        "tabs": ["overview", "ranking", "issues", "warning", "trend", "daily", "detail", "audit", "admin"],
        "can_upload": True,
        "can_manage_users": True,
        "can_delete_files": True,
    },
    "bangiamhieu": {
        "tabs": ["overview", "ranking", "issues", "warning", "trend", "daily", "detail", "audit", "admin"],
        "can_upload": True,
        "can_manage_users": False,
        "can_delete_files": False,
    },
    "quanly": {
        "tabs": ["overview", "ranking", "issues", "warning", "trend", "daily", "detail", "admin"],
        "can_upload": True,
        "can_manage_users": False,
        "can_delete_files": False,
    },
    "giamthi": {
        "tabs": ["overview", "ranking", "issues", "warning", "trend", "daily", "detail", "admin"],
        "can_upload": True,
        "can_manage_users": False,
        "can_delete_files": False,
    },
    "bantru": {
        "tabs": ["overview", "ranking", "issues", "warning", "trend", "daily", "detail", "admin"],
        "can_upload": True,
        "can_manage_users": False,
        "can_delete_files": False,
    },
}


    role = current_user["role"]
    perms = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["bantru"])

    return {
        "user": current_user,
        "permissions": perms
    }
