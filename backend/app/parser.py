import re
import pandas as pd
from datetime import datetime
from difflib import SequenceMatcher
from app.database import get_conn


def clean_value(value):
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def normalize_text(text):
    return clean_value(text).lower()


OFFICIAL_CLASS_RE = re.compile(r"^(6|7|8|9|10|11|12)A\d{1,2}$", re.IGNORECASE)

def normalize_class_name(value):
    """Chuẩn hóa tên lớp hành chính: 11a2 -> 11A2."""
    text = clean_value(value).upper().replace(" ", "")
    return text

def is_official_class_name(value):
    """Chỉ lớp hành chính được tính thi đua/ranking: 6A1..12Axx.
    Các lớp đội tuyển/phụ đạo như ĐT ASMO, ĐT TOÁN... không phải lớp chính.
    """
    text = normalize_class_name(value)
    return bool(OFFICIAL_CLASS_RE.match(text))

def parse_date_from_value(value):
    """Parse ngày từ cell Excel với nhiều định dạng thường gặp."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
        if pd.notna(parsed):
            return parsed.to_pydatetime()
    except Exception:
        pass
    text = clean_value(value)
    patterns = [
        r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})",
        r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})",
        r"(\d{1,2})[./\-](\d{1,2})",
    ]
    for idx, pattern in enumerate(patterns):
        m = re.search(pattern, text)
        if not m:
            continue
        try:
            if idx == 0:
                day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif idx == 1:
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            else:
                day, month, year = int(m.group(1)), int(m.group(2)), datetime.now().year
            return datetime(year, month, day)
        except Exception:
            continue
    return None

def get_row_date(row, default_date):
    """Lấy ngày từ các cột thường gặp; fallback về ngày mặc định."""
    for col in ["Ngày", "Ngày vi phạm", "Ngày ghi nhận", "Ngày tháng", "Date", "Thời gian", "Timestamp"]:
        try:
            date_obj = parse_date_from_value(row.get(col))
            if date_obj:
                return date_obj
        except Exception:
            continue
    return default_date


def fuzzy_score(a, b):
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def load_active_point_rules():
    conn = get_conn()
    try:
        rules = conn.execute("""
            SELECT keyword, point
            FROM point_rules
            WHERE is_active=1
        """).fetchall()
        return [{"keyword": r["keyword"], "point": r["point"]} for r in rules]
    finally:
        conn.close()


def get_point_from_rule(issue_text, rules, is_violation=True):
    best_score = 0
    best_point = None

    for rule in rules:
        keyword = rule["keyword"]
        score = fuzzy_score(issue_text, keyword)

        if normalize_text(keyword) in normalize_text(issue_text):
            score = max(score, 0.9)

        if normalize_text(issue_text) in normalize_text(keyword):
            score = max(score, 0.85)

        if score > best_score:
            best_score = score
            best_point = rule["point"]

    if best_score >= 0.55 and best_point is not None:
        return best_point

    return -5 if is_violation else 5


def parse_date_from_text(text):
    text = clean_value(text)
    date_obj = parse_date_from_value(text)
    if date_obj:
        return date_obj

    # File dạng "Lỗi tháng 11 - 2025" không có ngày cụ thể:
    # fallback ngày đầu tháng để không rơi vào tháng hiện tại.
    m = re.search(r"th[aá]ng\s*(\d{1,2}).*?(\d{4})", text, flags=re.IGNORECASE)
    if m:
        try:
            return datetime(int(m.group(2)), int(m.group(1)), 1)
        except Exception:
            pass

    return datetime.now()


def build_row(
    date_obj,
    class_name,
    student_name,
    issue,
    point,
    note="",
    source_file="",
    source_sheet="",
    student_id="",
    category="",
    is_violation=1,
    folder="giamthi"
):
    class_name = normalize_class_name(class_name)
    student_name = clean_value(student_name)
    issue = clean_value(issue)
    note = clean_value(note)
    student_id = clean_value(student_id)
    category = clean_value(category)

    grade = ""
    level = ""

    grade_match = re.search(r"(\d+)", class_name)
    if grade_match:
        grade = grade_match.group(1)
        try:
            grade_num = int(grade)
            level = "THCS" if grade_num <= 9 else "THPT"
        except Exception:
            level = ""

    return {
        "date": date_obj.strftime("%Y-%m-%d"),
        "date_label": date_obj.strftime("%d/%m/%Y"),
        "week": f"W{date_obj.isocalendar()[1]}",
        "month": f"{date_obj.month:02d}/{date_obj.year}",
        "level": level,
        "grade": grade,
        "class_name": class_name,
        "class_is_official": is_official_class_name(class_name),
        "student_id": student_id,
        "student_name": student_name,
        "issue": issue,
        "category": category,
        "point": point,
        "note": note,
        "source_file": source_file,
        "source_sheet": source_sheet,
        "is_violation": is_violation,
        "folder": folder
    }


def parse_loi_file(file_path, folder, filename):
    rows = []
    excel = pd.ExcelFile(file_path)

    target_sheets = ["Chi Tiết", "CT 2"]
    date_obj = parse_date_from_text(filename)
    rules = load_active_point_rules()

    for sheet in excel.sheet_names:
        if sheet not in target_sheets:
            continue

        df = pd.read_excel(file_path, sheet_name=sheet, header=4)

        for _, row in df.iterrows():
            student = clean_value(row.get("Tên học sinh"))
            class_name = clean_value(row.get("Lớp"))
            issue = clean_value(row.get("Lỗi vi phạm"))
            note = clean_value(row.get("Ghi chú"))
            category = clean_value(row.get("Phân loại"))

            if not student or not issue:
                continue

            point = get_point_from_rule(issue, rules, is_violation=True)
            row_date = get_row_date(row, date_obj)

            rows.append(build_row(
                date_obj=row_date,
                class_name=class_name,
                student_name=student,
                issue=issue,
                point=point,
                note=note,
                source_file=filename,
                source_sheet=sheet,
                category=category,
                is_violation=1,
                folder=folder
            ))

    return rows


def parse_khen_file(file_path, folder, filename):
    rows = []
    excel = pd.ExcelFile(file_path)

    skip_sheets = ["Tổng Hợp", "Tong Hop", "Sheet1", "Sheet2", "Sheet3", "Sheet4"]
    rules = load_active_point_rules()

    for sheet in excel.sheet_names:
        if sheet.strip() in skip_sheets:
            continue

        date_obj = parse_date_from_text(sheet)
        df = pd.read_excel(file_path, sheet_name=sheet, header=3)

        for _, row in df.iterrows():
            student_id = clean_value(row.get("Mã học sinh"))
            student = clean_value(row.get("Tên học sinh"))
            class_name = clean_value(row.get("Lớp"))
            issue = clean_value(row.get("Nội dung"))
            note = clean_value(row.get("Ghi chú"))

            if not student or not issue:
                continue

            point = get_point_from_rule(issue, rules, is_violation=False)
            row_date = get_row_date(row, date_obj)

            rows.append(build_row(
                date_obj=row_date,
                class_name=class_name,
                student_name=student,
                issue=issue,
                point=point,
                note=note,
                source_file=filename,
                source_sheet=sheet,
                student_id=student_id,
                category="Khen thưởng",
                is_violation=0,
                folder=folder
            ))

    return rows


def parse_fsp_file(file_path, folder, filename):
    rows = []
    excel = pd.ExcelFile(file_path)
    date_obj = datetime.now()

    for sheet in excel.sheet_names:
        sheet_lower = sheet.lower()

        if "nhận xét học sinh" in sheet_lower or "nhan xet hoc sinh" in sheet_lower:
            df = pd.read_excel(file_path, sheet_name=sheet)

            for _, row in df.iterrows():
                student_id = clean_value(row.get("Mã học sinh"))
                student = clean_value(row.get("Họ và tên")) or clean_value(row.get("Tên học sinh"))
                class_name = clean_value(row.get("Lớp"))
                issue = clean_value(row.get("Nhận xét"))

                if not student or not issue:
                    continue
                if not is_official_class_name(class_name):
                    continue
                row_date = get_row_date(row, date_obj)

                rows.append(build_row(
                    date_obj=row_date,
                    class_name=class_name,
                    student_name=student,
                    issue=issue,
                    point=0,
                    note=issue,
                    source_file=filename,
                    source_sheet=sheet,
                    student_id=student_id,
                    category="Nhận xét FSP",
                    is_violation=0,
                    folder=folder
                ))

        if "schedule" in sheet_lower:
            df = pd.read_excel(file_path, sheet_name=sheet)

            for _, row in df.iterrows():
                student_id = clean_value(row.get("Mã học sinh"))
                student = clean_value(row.get("Họ và tên")) or clean_value(row.get("Tên học sinh"))
                class_name = clean_value(row.get("Lớp"))

                khong_phep = clean_value(row.get("Không phép"))
                nhan_xet = clean_value(row.get("Nhận xét lớp")) or clean_value(row.get("Đánh giá học sinh"))

                if not student:
                    continue
                if not is_official_class_name(class_name):
                    continue
                row_date = get_row_date(row, date_obj)

                if khong_phep and khong_phep not in ["0", "0.0"]:
                    issue = "Vắng không phép"
                    point = -5

                    rows.append(build_row(
                        date_obj=row_date,
                        class_name=class_name,
                        student_name=student,
                        issue=issue,
                        point=point,
                        note=nhan_xet,
                        source_file=filename,
                        source_sheet=sheet,
                        student_id=student_id,
                        category="FSP",
                        is_violation=1,
                        folder=folder
                    ))

    return rows


def parse_duration_minutes(value):
    if value is None:
        return None
    s = str(value).strip().lower().replace("phút", "").replace("p", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def extract_date_from_sheet_title(file_path, sheet_name):
    try:
        raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=3)
    except Exception:
        return None
    text = " ".join(str(v) for v in raw.values.flatten() if v is not None and str(v) != "nan")
    m = re.search(r"ng[àa]y\s*(\d{1,2})\s*th[áa]ng\s*(\d{1,2})\s*n[ăa]m\s*(\d{4})", text, re.IGNORECASE)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except Exception:
            return None
    return None


def _find_col(columns, *keywords):
    norm_cols = {str(c).strip().lower(): c for c in columns}
    for kw in keywords:
        for norm, original in norm_cols.items():
            if kw in norm:
                return original
    return None


def build_teacher_row(date_obj, teacher_name, subject_group, specialty, error_type,
                       class_name, period, duration_minutes, reason, note, source_file):
    return {
        "date": date_obj.strftime("%Y-%m-%d"),
        "date_label": date_obj.strftime("%d/%m/%Y"),
        "week": f"W{date_obj.isocalendar()[1]}",
        "month": f"{date_obj.month:02d}/{date_obj.year}",
        "teacher_name": clean_value(teacher_name),
        "subject_group": clean_value(subject_group),
        "specialty": clean_value(specialty),
        "error_type": clean_value(error_type),
        "class_name": clean_value(class_name),
        "period": clean_value(period),
        "duration_minutes": duration_minutes,
        "reason": clean_value(reason),
        "note": clean_value(note),
        "source_file": source_file,
    }


def parse_teacher_excel(file_path, filename=""):
    rows = []
    excel = pd.ExcelFile(file_path)

    for sheet in excel.sheet_names:
        date_obj = parse_date_from_text(sheet)
        if not date_obj:
            date_obj = extract_date_from_sheet_title(file_path, sheet)
        if not date_obj and len(excel.sheet_names) == 1:
            date_obj = parse_date_from_text(filename)
        if not date_obj:
            continue

        try:
            df = pd.read_excel(file_path, sheet_name=sheet, header=3)
        except Exception:
            continue

        col_name = _find_col(df.columns, "họ và tên", "ho va ten", "họ tên")
        col_group = _find_col(df.columns, "tổ chuyên môn", "to chuyen mon")
        col_specialty = _find_col(df.columns, "chuyên môn", "chuyen mon")
        col_error = _find_col(df.columns, "lỗi ghi nhận", "loi ghi nhan", "lỗi")
        col_class = _find_col(df.columns, "lớp", "lop")
        col_period = _find_col(df.columns, "tiết", "tiet")
        col_duration = _find_col(df.columns, "thời gian", "thoi gian")
        col_reason = _find_col(df.columns, "lý do", "ly do")
        col_note = _find_col(df.columns, "ghi chú", "ghi chu")

        if not col_name or not col_error:
            continue

        for _, row in df.iterrows():
            teacher_name = clean_value(row.get(col_name))
            error_type = clean_value(row.get(col_error))
            if not teacher_name or not error_type:
                continue
            rows.append(build_teacher_row(
                date_obj=date_obj,
                teacher_name=teacher_name,
                subject_group=clean_value(row.get(col_group)) if col_group else "",
                specialty=clean_value(row.get(col_specialty)) if col_specialty else "",
                error_type=error_type,
                class_name=clean_value(row.get(col_class)) if col_class else "",
                period=clean_value(row.get(col_period)) if col_period else "",
                duration_minutes=parse_duration_minutes(row.get(col_duration)) if col_duration else None,
                reason=clean_value(row.get(col_reason)) if col_reason else "",
                note=clean_value(row.get(col_note)) if col_note else "",
                source_file=filename,
            ))

    return rows


def parse_excel(file_path, folder="giamthi", filename=""):
    filename_lower = filename.lower()

    if "lỗi" in filename_lower or "loi" in filename_lower:
        return parse_loi_file(file_path, folder, filename)

    if "khen" in filename_lower:
        return parse_khen_file(file_path, folder, filename)

    if "fsp" in filename_lower:
        return parse_fsp_file(file_path, folder, filename)

    return []