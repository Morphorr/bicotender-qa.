import os
import re
from datetime import datetime
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials
from core.analyzer import AuditResult

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

HARDCODED_SHEET_ID = "1kxeXlbMVuc7FDmwtgD_FkaitfIU2LrYtouzAYhsmYU0"
TARGET_WORKSHEET_NAME = "Аудит звонков"


def hex_to_rgb(hex_str: str):
    hex_clean = hex_str.lstrip("#")
    return {
        "red": int(hex_clean[0:2], 16) / 255.0,
        "green": int(hex_clean[2:4], 16) / 255.0,
        "blue": int(hex_clean[4:6], 16) / 255.0
    }


def clean_caps_lock(text: str) -> str:
    """Удаляет сплошной CAPS LOCK и форматирует предложения с заглавной буквы."""
    if not text:
        return ""
    val = str(text).strip()
    letters = [c for c in val if c.isalpha()]
    if letters and (sum(1 for c in letters if c.isupper()) / len(letters)) > 0.55:
        val = val.lower()
        val = re.sub(r'(^|[.!?]\s+)([a-zа-яё])', lambda p: p.group(1) + p.group(2).upper(), val)
    return val


def normalize_target_to_infinitive(text: str) -> str:
    """Преобразует глаголы повелительного наклонения в инфинитивы регламента РОПа."""
    if not text:
        return ""
    val = clean_caps_lock(text)

    replacements = [
        (r'\bпродавай\b', 'продавать'), (r'\bфиксируй\b', 'фиксировать'),
        (r'\bзакрывай\b', 'закрывать'), (r'\bуточняй\b', 'уточнять'),
        (r'\bудерживай\b', 'удерживать'), (r'\bделай\b', 'делать'),
        (r'\bпереводи\b', 'переводить'), (r'\bисключи\b', 'исключить'),
        (r'\bубери\b', 'убрать'), (r'\bне называй\b', 'не называть'),
        (r'\bне сливай\b', 'не сливать'), (r'\bне отправляй\b', 'не отправлять'),
        (r'\bвнедряй\b', 'внедрять'), (r'\bобозначай\b', 'обозначать'),
        (r'\bснимай\b', 'снимать'), (r'\bпоказывай\b', 'показывать'),
        (r'\bслушай\b', 'слушать'), (r'\bзадавай\b', 'задавать'),
        (r'\bперебивай\b', 'перебивать'), (r'\bпробивай\b', 'пробивать'),
        (r'\bвыявляй\b', 'выявлять'),
    ]
    for pattern, repl in replacements:
        val = re.sub(pattern, repl, val, flags=re.IGNORECASE)

    val = re.sub(r'\bвсегда\s+', '', val, flags=re.IGNORECASE)
    val = re.sub(r'\bобязательно\s+', '', val, flags=re.IGNORECASE)
    
    val = val.strip()
    if val:
        val = val[0].upper() + val[1:]
    return val


def clean_alternative_script(raw_val: str, quote_fallback: str = "") -> str:
    """Гарантирует полноценный текст двухшаговой связки и отсекает таймкоды."""
    val = str(raw_val or "").strip()
    if re.fullmatch(r"^\d{1,2}:\d{2}$", val) or len(val) < 10:
        val = (
            "«Давайте на 10 минут подключимся в Zoom/экран, я открою систему и на ваших позициях покажу скрытые закупки: сегодня в 15:00 или завтра в 11:30?»\n"
            "Если отказ / просит КП: «Именно поэтому на 10 минут на экран: КП не покажет реальную динамику снижения конкурентов. Когда удобнее зайти: до обеда или после 15:00?»"
        )
    return val


def append_audit_to_sheet(
    audit: AuditResult,
    manager_name: str,
    company_name: str,
    crm_url: str,
    meeting_date: str = "",
    selected_error_idx: int = 0,
    creds_path: str | None = None,
    sheet_id: str | None = None
) -> int:
    target_sheet_id = (sheet_id or os.getenv("GOOGLE_SHEET_ID") or HARDCODED_SHEET_ID).strip()
    creds = None

    # 1. Попытка авторизации через Streamlit Secrets
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    except Exception:
        creds = None

    # 2. Фолбэк на локальный файл credentials.json
    if creds is None:
        resolved_creds = (creds_path or os.getenv("CREDENTIALS_FILE") or "credentials.json").strip()
        if not os.path.exists(resolved_creds):
            fallback = "google_creds.json" if resolved_creds == "credentials.json" else "credentials.json"
            if os.path.exists(fallback):
                resolved_creds = fallback
            else:
                raise FileNotFoundError(f"Файл ключа '{resolved_creds}' не найден!")
        creds = Credentials.from_service_account_file(resolved_creds, scopes=SCOPES)

    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(target_sheet_id)

    try:
        sheet = spreadsheet.worksheet(TARGET_WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.get_worksheet(0)

    # Извлечение данных фокусной ошибки
    if audit.all_errors and selected_error_idx < len(audit.all_errors):
        err = audit.all_errors[selected_error_idx]
        desc = clean_caps_lock(getattr(err, "description", ""))
        quote = str(getattr(err, "quote", "")).strip()
        raw_script = getattr(err, "correct_alternative_script", "")
        raw_growth = getattr(err, "support_growth_potential", "")
        raw_target = getattr(err, "sprint_target", "")
        tag_val = getattr(err, "chronic_tag", "Слив цены")

        error_cell = f"{desc}\nЦитата: «{quote}»" if quote else desc
        alt_replica = clean_alternative_script(raw_script, quote)
        
        growth_potential = clean_caps_lock(raw_growth)
        if not growth_potential or len(growth_potential) < 10:
            growth_potential = "У сотрудника высокая экспертность в ведении диалога. Важно перейти от формата справочной консультации к уверенному закрытию сделки на зеркальный экран."

        target_rule = normalize_target_to_infinitive(raw_target)
        if not target_rule or len(target_rule) < 8:
            target_rule = "Удерживать регламент квалификации: не называть цену вслепую, переводить клиента на 10-минутный показ экрана."

        chronic_bag = clean_caps_lock(tag_val)
    else:
        error_cell = "Критичных ошибок не зафиксировано"
        alt_replica = (
            "«Давайте подключимся на 10 минут в Zoom/экран, я открою систему и покажу чистую аналитику по вашей нише: сегодня в 15:00 или завтра в 11:00?»\n"
            "Если отказ: «Именно поэтому на 10 минут на экран: отсечем мусорные закупки сразу в системе.»"
        )
        growth_potential = "Поддерживать стабильный уровень качества и инициативу в ведении диалога."
        target_rule = "Соблюдать стандарты квалификации и закрытия на онлайн-показ экрана."
        chronic_bag = "Ошибок нет"

    meeting_val = meeting_date if meeting_date else datetime.now().strftime("%d.%m.%Y")
    duration = getattr(audit, "call_duration", "07:29")
    contact_duration = f"{datetime.now().strftime('%d.%m.%Y')}, {duration}"
    score_val = int(getattr(audit, "total_score", 0))
    score_justification = clean_caps_lock(getattr(audit, "score_justification", "Оценка сформирована по чек-листу BicoTender"))
    victory = clean_caps_lock(getattr(audit, "main_victory", "Уверенное начало диалога и качественный контакт"))
    rop_script = str(getattr(audit, "rop_1on1_script", "")).strip()

    crm_cell = f'=HYPERLINK("{crm_url}"; "{crm_url}")' if crm_url.startswith("http") else (crm_url or "Нет ссылки")

    # ПОИСК СВОБОДНОЙ СТРОКИ
    col_c = sheet.col_values(3)
    col_d = sheet.col_values(4) 
    target_row = None

    for idx, name in enumerate(col_c):
        r = idx + 1
        if r >= 8 and name.strip().lower() == manager_name.strip().lower():
            col_d_val = col_d[idx] if idx < len(col_d) else ""
            if not col_d_val or str(col_d_val).strip() == "":
                target_row = r
                break

    if target_row is None:
        target_row = max(len(col_d) + 1, 8)

    col_a_vals = sheet.col_values(1)[7:]
    valid_nums = [int(x) for x in col_a_vals if str(x).strip().isdigit()]
    actual_id = max(valid_nums) + 1 if valid_nums else (target_row - 7)

    # РАСКЛАДКА СТРОКИ
    row_data = [
        actual_id, meeting_val, manager_name, company_name or "Не указана", 
        contact_duration, crm_cell, score_val, score_justification, 
        victory, error_cell, alt_replica, growth_potential, 
        target_rule, rop_script, "", chronic_bag, "Запланирована"
    ]

    cell_range = f"A{target_row}:Q{target_row}"
    # ЗАПИСЬ ДАННЫХ
    sheet.update(values=[row_data], range_name=cell_range, value_input_option="USER_ENTERED")

    # ФОРМАТИРОВАНИЕ
    sheet_id_int = sheet.id
    row_start_0 = target_row - 1
    row_end_0 = target_row
    border_style = {"style": "SOLID", "width": 1, "color": hex_to_rgb("#D9D9D9")}
    base_bg = hex_to_rgb("#F8F9FC")

    if score_val < 50:
        score_bg, score_fg = hex_to_rgb("#FCE8E6"), hex_to_rgb("#C5221F")
    elif score_val < 70:
        score_bg, score_fg = hex_to_rgb("#FEF7E0"), hex_to_rgb("#B06000")
    else:
        score_bg, score_fg = hex_to_rgb("#E6F4EA"), hex_to_rgb("#0D652D")

    requests = [
        {
            "updateBorders": {
                "range": {"sheetId": sheet_id_int, "startRowIndex": row_start_0, "endRowIndex": row_end_0, "startColumnIndex": 0, "endColumnIndex": 17},
                "top": border_style, "bottom": border_style, "left": border_style, "right": border_style, "innerHorizontal": border_style, "innerVertical": border_style
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id_int, "startRowIndex": row_start_0, "endRowIndex": row_end_0, "startColumnIndex": 0, "endColumnIndex": 17},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": base_bg, "verticalAlignment": "TOP", "horizontalAlignment": "LEFT", "wrapStrategy": "WRAP",
                        "textFormat": {"fontFamily": "Google Sans", "fontSize": 9, "foregroundColor": hex_to_rgb("#202124")}
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,verticalAlignment,horizontalAlignment,wrapStrategy,textFormat)"
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id_int, "startRowIndex": row_start_0, "endRowIndex": row_end_0, "startColumnIndex": 0, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER"}}, "fields": "userEnteredFormat.horizontalAlignment"
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id_int, "startRowIndex": row_start_0, "endRowIndex": row_end_0, "startColumnIndex": 4, "endColumnIndex": 6},
                "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER"}}, "fields": "userEnteredFormat.horizontalAlignment"
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id_int, "startRowIndex": row_start_0, "endRowIndex": row_end_0, "startColumnIndex": 15, "endColumnIndex": 17},
                "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER"}}, "fields": "userEnteredFormat.horizontalAlignment"
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id_int, "startRowIndex": row_start_0, "endRowIndex": row_end_0, "startColumnIndex": 6, "endColumnIndex": 7},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": score_bg, "horizontalAlignment": "CENTER",
                        "textFormat": {"fontFamily": "Google Sans", "fontSize": 9, "bold": True, "foregroundColor": score_fg}
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)"
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id_int, "startRowIndex": row_start_0, "endRowIndex": row_end_0, "startColumnIndex": 16, "endColumnIndex": 17},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": hex_to_rgb("#E8F0FE"), "horizontalAlignment": "CENTER",
                        "textFormat": {"fontFamily": "Google Sans", "fontSize": 9, "foregroundColor": hex_to_rgb("#1A73E8")}
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)"
            }
        }
    ]

    spreadsheet.batch_update({"requests": requests})
    return target_row