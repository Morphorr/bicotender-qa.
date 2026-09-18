import os
import re
import tempfile
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

load_dotenv()

from core.analyzer import analyze_audio_call, regenerate_feedback_for_error
from core.sheets_exporter import append_audit_to_sheet

def format_sentence_case(text: str) -> str:
    """Гарантирует, что каждое предложение начинается с большой буквы."""
    if not text:
        return ""
    val = str(text).strip()
    return re.sub(r'(^|[.!?]\s+)([a-zа-яё])', lambda p: p.group(1) + p.group(2).upper(), val)

st.set_page_config(
    page_title="BicoTender Sales Intelligence",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

OBSIDIAN_DARK_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #0B0F17 !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    color: #F8FAFC !important;
    -webkit-font-smoothing: antialiased;
}

[data-testid="stHeader"] {
    background: transparent !important;
}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 4rem !important;
    max-width: 1240px !important;
}

div[data-baseweb="input"],
div[data-baseweb="input"] > div,
div[data-baseweb="select"],
div[data-baseweb="select"] > div,
div[data-baseweb="base-input"] {
    background-color: #131B2A !important;
    border: 1px solid #283548 !important;
    border-radius: 8px !important;
    color: #FFFFFF !important;
}

input[type="text"],
input[type="password"],
div[data-baseweb="select"] span,
div[data-baseweb="select"] div {
    color: #FFFFFF !important;
    background-color: transparent !important;
    font-size: 1rem !important;
    font-weight: 500 !important;
}

input::placeholder {
    color: #64748B !important;
}

div[data-baseweb="input"]:focus-within,
div[data-baseweb="select"] > div:focus-within {
    border-color: #3B82F6 !important;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25) !important;
}

ul[data-baseweb="menu"] {
    background-color: #131B2A !important;
    border: 1px solid #283548 !important;
}
ul[data-baseweb="menu"] li {
    color: #F8FAFC !important;
}
ul[data-baseweb="menu"] li:hover {
    background-color: #1E293B !important;
}

label[data-testid="stWidgetLabel"] p {
    color: #94A3B8 !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    margin-bottom: 6px !important;
}

div[data-testid="stRadio"] label span {
    color: #F8FAFC !important;
    font-weight: 500 !important;
    font-size: 1rem !important;
}

[data-testid="stFileUploader"] section {
    background-color: #131B2A !important;
    border: 1.5px dashed #283548 !important;
    border-radius: 10px !important;
    padding: 20px !important;
}
[data-testid="stFileUploader"] section * {
    color: #CBD5E1 !important;
}

[data-testid="stExpander"] {
    background-color: #131B2A !important;
    border: 1px solid #1E293B !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
}
[data-testid="stExpander"] details summary {
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 1.05rem !important;
}

div.stButton > button:first-child {
    background-color: #2563EB !important;
    color: #FFFFFF !important;
    border: 1px solid #3B82F6 !important;
    border-radius: 8px !important;
    padding: 0.75rem 1.6rem !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25) !important;
    transition: all 0.15s ease !important;
}
div.stButton > button:first-child:hover {
    background-color: #1D4ED8 !important;
}

.dark-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 1.4rem;
    margin-bottom: 1.8rem;
    border-bottom: 1px solid #1E293B;
}
.dark-brand {
    font-size: 1.25rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: #FFFFFF;
    display: flex;
    align-items: center;
    gap: 8px;
}
.dark-badge {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    color: #94A3B8;
    background: #131B2A;
    padding: 4px 12px;
    border-radius: 6px;
    border: 1px solid #1E293B;
}

.meta-dark-strip {
    background: #131B2A;
    border: 1px solid #1E293B;
    border-radius: 10px;
    padding: 18px 24px;
    margin-bottom: 22px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
}
.meta-dark-item .label {
    font-size: 0.76rem;
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: #94A3B8;
    margin-bottom: 3px;
}
.meta-dark-item .val {
    font-size: 1.05rem;
    font-weight: 600;
    color: #FFFFFF;
}

.score-card-dark {
    background: #131B2A;
    border: 1px solid #1E293B;
    border-radius: 10px;
    padding: 22px 26px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 22px;
}
.score-number-dark {
    font-size: 3.4rem;
    font-weight: 800;
    line-height: 1;
    color: #FFFFFF;
}

.status-pill-dark {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 0.95rem;
    font-weight: 700;
    padding: 8px 16px;
    border-radius: 6px;
}
.pill-green-dark { background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); }
.pill-yellow-dark { background: rgba(245, 158, 11, 0.15); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.3); }
.pill-red-dark { background: rgba(239, 68, 68, 0.15); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.3); }
.pill-dot { width: 8px; height: 8px; border-radius: 50%; background-color: currentColor; }

.layer-card-dark {
    background: #131B2A;
    border: 1px solid #1E293B;
    border-radius: 10px;
    padding: 22px 26px;
    margin-bottom: 18px;
}
.layer-header-dark {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.layer-title-dark {
    font-size: 1.1rem;
    font-weight: 800;
    color: #FFFFFF !important;
    letter-spacing: -0.01em;
    display: flex;
    align-items: center;
    gap: 8px;
}
.layer-tag-dark {
    font-size: 0.82rem;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 4px;
}

.layer-win-dark { border-left: 5px solid #10B981; }
.layer-win-dark .layer-tag-dark { background: rgba(16, 185, 129, 0.2); color: #34D399; }

.layer-error-dark { border-left: 5px solid #EF4444; }
.layer-error-dark .layer-tag-dark { background: rgba(239, 68, 68, 0.2); color: #F87171; }

.layer-alt-dark { border-left: 5px solid #3B82F6; }
.layer-alt-dark .layer-tag-dark { background: rgba(59, 130, 246, 0.2); color: #60A5FA; }

.layer-grow-dark { border-left: 5px solid #A855F7; }
.layer-grow-dark .layer-tag-dark { background: rgba(168, 85, 247, 0.2); color: #C084FC; }

.dark-quote {
    background: #0B0F17;
    border-left: 3px solid #64748B;
    padding: 12px 16px;
    margin-top: 12px;
    font-size: 1rem;
    color: #E2E8F0;
    font-style: italic;
    border-radius: 0 6px 6px 0;
}

.target-card-dark {
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 22px 26px;
    margin-bottom: 24px;
}
.target-label-dark {
    font-size: 0.82rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #38BDF8;
    margin-bottom: 8px;
}
.target-text-dark {
    font-size: 1.15rem;
    font-weight: 600;
    color: #FFFFFF;
    line-height: 1.6;
}

.script-terminal-dark {
    background: #131B2A;
    border: 1px solid #283548;
    border-radius: 10px;
    padding: 26px;
    font-size: 1.05rem;
    line-height: 1.8;
    color: #F8FAFC;
    margin-bottom: 24px;
}
</style>
"""
st.markdown(OBSIDIAN_DARK_STYLE, unsafe_allow_html=True)

system_api_key = os.getenv("GEMINI_API_KEY", "").strip()
SECOND_API_KEY = "AQ.Ab8RN6LC-GQ3YpYy7urc2DgvTmSXVW25zkARPMb7hgXY2hhyUA"

with st.sidebar:
    st.caption("Параметры системы")
    with st.expander("Конфигурация ядра", expanded=False):
        key_source = st.selectbox(
            "Выбор API-ключа:",
            ["Основной (из .env)", "Резервный (второй ключ)", "Ввести вручную"],
            index=1, # По умолчанию выставим второй на всякий случай
            help="Выберите источник API-ключа для обхода лимитов"
        )
        
        if key_source == "Основной (из .env)":
            resolved_api_key = system_api_key
        elif key_source == "Резервный (второй ключ)":
            resolved_api_key = SECOND_API_KEY
        else:
            user_custom_key = st.text_input(
                "Свой API Key:",
                value="",
                type="password",
                placeholder="Вставьте ключ...",
            )
            resolved_api_key = user_custom_key.strip()

        model_choice = st.selectbox(
            "Модель аудита:",
            ["gemini-3.6-flash"],
            index=0,
            help="Используется актуальный флагман Google Gemini"
        )

st.markdown(
    """
    <div class="dark-header">
        <div class="dark-brand">
            BICOTENDER <span style="font-weight: 300; color: #475569;">|</span> SALES INTELLIGENCE
        </div>
        <div class="dark-badge">QA Console Dark</div>
    </div>
    """,
    unsafe_allow_html=True
)

if "input_manager" not in st.session_state:
    st.session_state["input_manager"] = "Гулевич Арсений"
if "input_custom_manager" not in st.session_state:
    st.session_state["input_custom_manager"] = ""
if "input_call_type" not in st.session_state:
    st.session_state["input_call_type"] = "Первичка / Холодный"
if "input_client_name" not in st.session_state:
    st.session_state["input_client_name"] = ""
if "input_crm_url" not in st.session_state:
    st.session_state["input_crm_url"] = ""
if "input_custom_context" not in st.session_state:
    st.session_state["input_custom_context"] = ""

has_audit = "audit_result" in st.session_state

with st.expander("Параметры сессии и загрузка аудио", expanded=not has_audit):
    uploaded_file = st.file_uploader(
        "Файл переговоров (WAV, MP3, M4A):",
        type=["mp3", "wav", "m4a", "ogg"],
        label_visibility="collapsed"
    )
    
    col_m, col_t = st.columns([1, 1])
    with col_m:
        managers_list = [
            "Гулевич Арсений",
            "Русина Елена",
            "Айрапетов Антон",
            "Никольская Ангелина",
            "Булатова Анастасия",
            "Лабынцева Кристина",
            "Артюшенко Юлия",
            "Климова Валерия",
            "Закутский Денис",
            "Шушан Млкеян",
            "Крутских Карина",
            "Другой сотрудник (ввести вручную)"
        ]
        m_idx = managers_list.index(st.session_state["input_manager"]) if st.session_state["input_manager"] in managers_list else 0
        selected_manager = st.selectbox("Сотрудник отдела продаж:", managers_list, index=m_idx)
        st.session_state["input_manager"] = selected_manager
        
        if selected_manager == "Другой сотрудник (ввести вручную)":
            manager_name = st.text_input("ФИО сотрудника:", value=st.session_state["input_custom_manager"])
            st.session_state["input_custom_manager"] = manager_name
        else:
            manager_name = selected_manager

    with col_t:
        st.markdown("<label style='color: #94A3B8; font-weight: 600; font-size: 0.95rem; margin-bottom: 6px; display: block;'>Тип контакта / Архетип:</label>", unsafe_allow_html=True)
        
        call_types = [
            "🤖 Автоопределение ИИ (Рекомендуется)",
            "Первый звонок в топку",
            "Первый звонок в лид",
            "Первый звонок ОРВБ",
            "Демонстрация системы",
            "Отработка возражений / Торг",
            "Закрытие / Соглашение",
            "Рабочий / Текущий созвонок (ОС, дожим, вопросы)"
        ]
        
        c_idx = call_types.index(st.session_state["input_call_type"]) if st.session_state["input_call_type"] in call_types else 0
        
        # Аккуратный выпадающий список вместо громоздкого радио-столбика
        call_type = st.selectbox(
            "Тип контакта:",
            call_types,
            index=c_idx,
            label_visibility="collapsed"
        )
        st.session_state["input_call_type"] = call_type
    
    col_c, col_u = st.columns([1, 1])
    with col_c:
        client_name = st.text_input("Компания / Отрасль клиента:", value=st.session_state["input_client_name"], placeholder="ООО Новые Технологии")
        st.session_state["input_client_name"] = client_name
    with col_u:
        crm_url = st.text_input("Ссылка на карточку в CRM:", value=st.session_state["input_crm_url"], placeholder="https://www.bicotender.ru/crm/...")
        st.session_state["input_crm_url"] = crm_url

    custom_context = st.text_area(
        "Контекст и особенности звонка (важные вводные для ИИ):",
        value=st.session_state["input_custom_context"],
        placeholder="Например: Это короткий звонок на 40 секунд, оцениваем только вход в контакт и реакцию на секретаря.",
        help="Опишите специфику звонка, чтобы ИИ адаптировал матрицу оценки под конкретную задачу."
    )
    st.session_state["input_custom_context"] = custom_context

    start_audit = st.button("Провести аналитический аудит", use_container_width=True)

if start_audit:
    file_buffer = uploaded_file.getbuffer() if uploaded_file else st.session_state.get("audio_bytes")
    file_name = uploaded_file.name if uploaded_file else st.session_state.get("audio_filename", "audio.wav")

    if not file_buffer:
        st.error("Прикрепите аудиозапись для проведения оценки.")
    elif not resolved_api_key:
        st.error("API-ключ не выбран или пустой. Проверьте настройки в боковой панели.")
    else:
        with st.status("Инициализация аудита...", expanded=True) as status:
            file_ext = file_name.split('.')[-1].lower()
            
            st.write("Сохранение исходного аудио...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                tmp.write(file_buffer)
                tmp_path = tmp.name

            compressed_path = tmp_path
            
            if PYDUB_AVAILABLE:
                st.write("Сжатие аудио для ускорения обработки (моно, 32 kbps)...")
                try:
                    audio = AudioSegment.from_file(tmp_path)
                    audio = audio.set_channels(1).set_frame_rate(16000)
                    compressed_path = tmp_path + "_compressed.mp3"
                    audio.export(compressed_path, format="mp3", bitrate="32k")
                    
                    orig_size = os.path.getsize(tmp_path) / (1024 * 1024)
                    new_size = os.path.getsize(compressed_path) / (1024 * 1024)
                    st.write(f"Размер уменьшен: с {orig_size:.1f} МБ до {new_size:.1f} МБ")
                except Exception as e:
                    st.write(f"⚠️ Сжатие пропущено (вероятно, не установлен FFmpeg): {e}")
                    compressed_path = tmp_path
            else:
                st.write("⚠️ Библиотека pydub не найдена, сжатие пропущено.")

            st.write("Отправка в Google Cloud и генерация аудита (пожалуйста, подождите)...")
            try:
                result = analyze_audio_call(
                    audio_path=compressed_path,
                    manager_name=manager_name,
                    call_type=call_type,
                    client_name=client_name,
                    crm_url=crm_url,
                    custom_context=custom_context,
                    model_name=model_choice,
                    api_key=resolved_api_key
                )
                
                st.write("Отрисовка матрицы результатов...")
                st.session_state["audit_result"] = result
                st.session_state["audio_bytes"] = bytes(file_buffer)
                st.session_state["audio_filename"] = file_name
                st.session_state["active_error_idx"] = (
                    result.primary_error_index 
                    if result.primary_error_index < len(result.all_errors) 
                    else 0
                )
                st.session_state["active_target"] = format_sentence_case(
                    result.all_errors[st.session_state["active_error_idx"]].sprint_target 
                    if result.all_errors else ""
                )
                st.session_state["active_script"] = format_sentence_case(result.rop_1on1_script)
                
                status.update(label="Аудит успешно завершен", state="complete", expanded=False)
                st.rerun()
            except Exception as e:
                status.update(label="Временная перегрузка серверов", state="error", expanded=True)
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                    st.warning("⚠️ Серверы Google сейчас сильно загружены. Попробуйте переключиться на другой API-ключ в боковой панели или повторите попытку через пару минут.")
                else:
                    st.error(f"Сбой выполнения аудита: {err_str}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                if compressed_path != tmp_path and os.path.exists(compressed_path):
                    os.remove(compressed_path)

if "audit_result" in st.session_state:
    res = st.session_state["audit_result"]
    score = int(getattr(res, "total_score", 0))
    m_name = st.session_state.get("input_custom_manager") if st.session_state.get("input_manager") == "Другой сотрудник (ввести вручную)" else st.session_state.get("input_manager")
    company_val = st.session_state.get("input_client_name") or "Не указана"
    crm_val = st.session_state.get("input_crm_url", "")
    call_type_val = st.session_state.get("input_call_type", "")
    call_dur = getattr(res, "call_duration", "—")
    archetype = getattr(res, "detected_call_archetype", "Общий звонок")

    col_btn_reset, _ = st.columns([2, 5])
    with col_btn_reset:
        if st.button("Новый звонок", use_container_width=True):
            for key in ["audit_result", "audio_bytes", "audio_filename", "active_error_idx", "active_target", "active_script"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    crm_link_html = f'<a href="{crm_val}" target="_blank" style="color: #60A5FA; text-decoration: underline;">Карточка CRM ↗</a>' if crm_val else '—'

    st.markdown(
        f"""
        <div class="meta-dark-strip">
            <div class="meta-dark-item">
                <span class="label">Архетип / Формат</span>
                <span class="val" style="color: #38BDF8;">{archetype}</span>
            </div>
            <div class="meta-dark-item">
                <span class="label">Клиент</span>
                <span class="val">{company_val}</span>
            </div>
            <div class="meta-dark-item">
                <span class="label">Сотрудник</span>
                <span class="val">{m_name}</span>
            </div>
            <div class="meta-dark-item">
                <span class="label">Длительность</span>
                <span class="val">{call_dur}</span>
            </div>
            <div class="meta-dark-item">
                <span class="label">CRM</span>
                <span class="val">{crm_link_html}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if score >= 70:
        pill_html = '<span class="status-pill-dark pill-green-dark"><span class="pill-dot"></span>Стабильная норма</span>'
    elif score >= 50:
        pill_html = '<span class="status-pill-dark pill-yellow-dark"><span class="pill-dot"></span>Фокус-контроль</span>'
    else:
        pill_html = '<span class="status-pill-dark pill-red-dark"><span class="pill-dot"></span>Зона риска / Стоп-фактор</span>'

    col_s1, col_s2 = st.columns([1, 2])
    with col_s1:
        st.markdown(
            f"""
            <div class="score-card-dark">
                <div>
                    <div style="font-size: 0.8rem; text-transform: uppercase; font-weight: 700; color: #94A3B8; letter-spacing: 0.05em; margin-bottom: 6px;">Результат аудита</div>
                    <div class="score-number-dark">{score}<span style="font-size: 1.4rem; font-weight: 400; color: #64748B;">/100</span></div>
                </div>
                <div>{pill_html}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col_s2:
        if "audio_bytes" in st.session_state:
            st.caption("Аудиозапись звонка:")
            st.audio(st.session_state["audio_bytes"])
        justification = format_sentence_case(getattr(res, "score_justification", "Оценка сформирована по адаптивным критериям."))
        st.markdown(f"<div style='font-size: 1rem; line-height: 1.6; color: #CBD5E1; padding-top: 4px;'><b style='color: #FFFFFF;'>Обоснование:</b> {justification}</div>", unsafe_allow_html=True)

    # Динамическая декомпозиция узлов
    st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)

    with st.expander("Динамическая матрица оценки (Адаптивные узлы)", expanded=True):
        nodes = getattr(res, "evaluated_nodes", [])
        if nodes:
            cols = st.columns(len(nodes)) if len(nodes) <= 5 else st.columns(5)
            for idx, n in enumerate(nodes):
                clean_positives = format_sentence_case(n.positives)
                clean_growth = format_sentence_case(n.growth_areas) if hasattr(n, 'growth_areas') else ""
                
                col_target = cols[idx % len(cols)]
                with col_target:
                    growth_block = f"<div style='margin-top: 8px; font-size: 0.82rem; color: #FCA5A5; line-height: 1.35;'><b style='color: #F87171;'>Зона роста:</b> {clean_growth}</div>" if clean_growth else ""
                    
                    st.markdown(
                        f"""
                        <div style="background: #0B0F17; border: 1px solid #1E293B; border-radius: 8px; padding: 14px; height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
                            <div>
                                <div style="font-size: 0.75rem; color: #38BDF8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px;">{n.node_title}</div>
                                <div style="font-size: 0.72rem; color: #64748B; margin-bottom: 6px; line-height: 1.2;">Критерий: {n.criteria}</div>
                                <div style="font-size: 1.4rem; font-weight: 800; color: #FFFFFF; margin: 6px 0;">{n.score}/{n.max_score}</div>
                                <div style="font-size: 0.85rem; color: #CBD5E1; line-height: 1.4; margin-top: 6px;"><b style='color: #34D399;'>Плюс:</b> {clean_positives}</div>
                                {growth_block}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
        else:
            st.info("Для данного типа звонка детальная декомпозиция по узлам не потребовалась.")

    # Сворачиваемый блок со списком всех сильных сторон диалога
    with st.expander("✨ Полный реестр сильных сторон и успешных моментов диалога", expanded=False):
        if hasattr(res, "all_positive_points") and res.all_positive_points:
            for pt in res.all_positive_points:
                st.markdown(f"- {format_sentence_case(pt)}")
        else:
            st.markdown(f"- {format_sentence_case(res.main_victory)}")

    if res.stop_factor != "Нет":
        st.error(f"Зафиксирован критический стоп-фактор: {res.stop_factor}")

    st.write("")
    st.markdown("<div style='font-size: 0.9rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: #94A3B8; margin-bottom: 14px;'>Матрица развивающей обратной связи (1-on-1)</div>", unsafe_allow_html=True)

    clean_victory = format_sentence_case(res.main_victory)
    st.markdown(
        f"""
        <div class="layer-card-dark layer-win-dark">
            <div class="layer-header-dark">
                <span class="layer-title-dark">01. Зафиксированная победа (Слой 1 — Факт)</span>
                <span class="layer-tag-dark">Сильная сторона</span>
            </div>
            <div style="font-size: 1.05rem; line-height: 1.65; color: #F8FAFC;">{clean_victory}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if res.all_errors:
        error_options = [
            f"[{getattr(err, 'timestamp', '00:00')}] {getattr(err, 'stage', 'Этап')}: {format_sentence_case(getattr(err, 'description', ''))[:90]}..." 
            for err in res.all_errors
        ]
        
        curr_idx = st.session_state.get("active_error_idx", 0)
        if curr_idx >= len(error_options):
            curr_idx = 0

        chosen_label = st.selectbox(
            "Фокусная ошибка для разбора:",
            options=error_options,
            index=curr_idx,
            label_visibility="collapsed"
        )
        
        selected_new_idx = error_options.index(chosen_label)

        if selected_new_idx != st.session_state.get("active_error_idx"):
            with st.status("Пересчет сценария РОПа...", expanded=True) as status:
                st.write("Генерация нового управленческого скрипта...")
                new_error_obj = res.all_errors[selected_new_idx]
                regen = regenerate_feedback_for_error(
                    manager_name=m_name,
                    main_victory=res.main_victory,
                    selected_error=new_error_obj,
                    model_name=model_choice,
                    api_key=resolved_api_key
                )
                st.session_state["active_error_idx"] = selected_new_idx
                st.session_state["active_target"] = format_sentence_case(regen.sprint_target)
                st.session_state["active_script"] = format_sentence_case(regen.rop_1on1_script)
                status.update(label="Сценарий обновлен", state="complete", expanded=False)
                st.rerun()

        active_err = res.all_errors[st.session_state["active_error_idx"]]
        err_time = getattr(active_err, "timestamp", "00:00")
        err_stg = getattr(active_err, "stage", "Этап")
        err_desc = format_sentence_case(getattr(active_err, "description", ""))
        err_qt = format_sentence_case(getattr(active_err, "quote", ""))
        err_alt = format_sentence_case(getattr(active_err, "correct_alternative_script", "—"))
        err_growth = format_sentence_case(getattr(active_err, "support_growth_potential", "—"))

        st.markdown(
            f"""
            <div class="layer-card-dark layer-error-dark">
                <div class="layer-header-dark">
                    <span class="layer-title-dark">02. Зона сбоя регламента (Слой 2 — Анализ)</span>
                    <span class="layer-tag-dark">Таймкод {err_time}</span>
                </div>
                <div style="font-size: 1.05rem; line-height: 1.65; color: #F8FAFC;">
                    <b style="color: #FCA5A5;">{err_stg}:</b> {err_desc}
                    <div class="dark-quote">«{err_qt}»</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        clean_alt = err_alt.replace("\n", "<br>")
        st.markdown(
            f"""
            <div class="layer-card-dark layer-alt-dark">
                <div class="layer-header-dark">
                    <span class="layer-title-dark">03. Эталонный сценарий разговора</span>
                    <span class="layer-tag-dark">Таймкод {err_time}</span>
                </div>
                <div style="font-size: 1.05rem; line-height: 1.65; color: #F8FAFC; font-weight: 500;">{clean_alt}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div class="layer-card-dark layer-grow-dark">
                <div class="layer-header-dark">
                    <span class="layer-title-dark">04. Экспертная опора (Слой 3 — Ресурс)</span>
                    <span class="layer-tag-dark">Потенциал</span>
                </div>
                <div style="font-size: 1.05rem; line-height: 1.65; color: #F8FAFC;">{err_growth}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    clean_target = format_sentence_case(st.session_state.get('active_target', ''))
    st.markdown(
        f"""
        <div class="target-card-dark">
            <div class="target-label-dark">Управленческий регламент спринта (Target)</div>
            <div class="target-text-dark">{clean_target}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    clean_script = format_sentence_case(st.session_state.get('active_script', '')).replace('\n', '<br>')
    st.markdown(
        f"""
        <div style="font-size: 0.9rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: #94A3B8; margin-bottom: 8px;">Скрипт разговора РОПа</div>
        <div class="script-terminal-dark">
            {clean_script}
        </div>
        """,
        unsafe_allow_html=True
    )

    col_date, col_export = st.columns([1, 2])
    with col_date:
        meet_date = st.date_input("Дата встречи 1-on-1:", value=datetime.now(), label_visibility="collapsed")
    with col_export:
        if st.button("Зафиксировать в реестре Google Таблицы", use_container_width=True):
            try:
                with st.status("Экспорт данных...", expanded=True) as status:
                    st.write("Запись строки аудита...")
                    append_audit_to_sheet(
                        audit=res,
                        manager_name=m_name,
                        company_name=company_val,
                        crm_url=crm_val,
                        meeting_date=meet_date.strftime("%d.%m.%Y"),
                        selected_error_idx=st.session_state.get("active_error_idx", 0)
                    )
                    status.update(label="Аудит успешно внесен в реестр", state="complete", expanded=False)
            except Exception as ex:
                st.error(f"Ошибка записи: {str(ex)}")
                # Генерация полного текста отчета для печати / выгрузки
    if "audit_result" in st.session_state:
        res = st.session_state["audit_result"]
        active_err = res.all_errors[st.session_state.get("active_error_idx", 0)] if res.all_errors else None
        
        report_lines = [
            "=" * 50,
            f"ОТЧЕТ АУДИТА ЗВОНКА | BICOTENDER SALES INTELLIGENCE",
            "=" * 50,
            f"Сотрудник: {m_name}",
            f"Клиент / Ниша: {company_val}",
            f"Архетип звонка: {archetype}",
            f"Длительность: {call_dur}",
            f"Итоговый балл: {score}/100",
            f"Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            "-" * 50,
            "1. ОБОСНОВАНИЕ И ВЕРДИКТ РОПА:",
            f"{res.score_justification}",
            "-" * 50,
            "2. ДИНАМИЧЕСКИЕ УЗЛЫ ОЦЕНКИ:",
        ]
        
        for n in getattr(res, "evaluated_nodes", []):
            report_lines.append(f"• [{n.node_title}] — {n.score}/{n.max_score}")
            report_lines.append(f"  Плюс: {n.positives}")
            if n.growth_areas:
                report_lines.append(f"  Зона роста: {n.growth_areas}")
        
        report_lines.extend([
            "-" * 50,
            "3. ГЛАВНАЯ ПОБЕДА (Слой 1):",
            f"{res.main_victory}",
            "-" * 50,
            "4. РАЗБОР КЛЮЧЕВОЙ ОШИБКИ (Слои 2-3):"
        ])
        
        if active_err:
            report_lines.extend([
                f"Таймкод: {active_err.timestamp} | Этап: {active_err.stage}",
                f"Суть: {active_err.description}",
                f"Цитата: «{active_err.quote}»",
                f"Эталонный скрипт: {active_err.correct_alternative_script}",
                f"Экспертная опора: {active_err.support_growth_potential}"
            ])
            
        report_lines.extend([
            "-" * 50,
            "5. РЕГЛАМЕНТ СПРИНТА (TARGET):",
            f"{st.session_state.get('active_target', '')}",
            "-" * 50,
            "6. СКРИПТ РАЗГОВОРА РОПА (1-on-1):",
            f"{st.session_state.get('active_script', '')}",
            "=" * 50
        ]
        )
        
        report_text = "\n".join(report_lines)

        # Кнопка скачивания файла для печати
        st.download_button(
            label="📄 Скачать полный отчет для печати (TXT)",
            data=report_text,
            file_name=f"Audit_{m_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True
        )