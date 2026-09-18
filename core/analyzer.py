import os
import json
import time
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class DynamicNode(BaseModel):
    node_title: str = Field(description="Название этапа, релевантное для данного архетипа звонка (например: 'Вход и пробой барьера', 'Квалификация ниши')")
    score: int = Field(description="Фактический балл по этому узлу")
    max_score: int = Field(description="Максимальный балл для этого узла")
    criteria: str = Field(description="Краткое описание того, что оценивалось в данном узле")
    positives: str = Field(description="Факты успехов менеджера на этом этапе (строго без цитат)")
    growth_areas: str = Field(description="Зоны роста / причины снижения балла (строго без цитат)")

class CallError(BaseModel):
    timestamp: str = Field(description="Таймкод ММ:СС")
    stage: str = Field(description="Этап диалога")
    description: str = Field(description="Суть ошибки без CAPS LOCK")
    quote: str = Field(description="Дословная цитата менеджера")
    correct_alternative_script: str = Field(description="Развернутая эталонная реплика в кавычках БЕЗ таймкода")
    support_growth_potential: str = Field(description="Слой 3: поддержка экспертности")
    sprint_target: str = Field(description="Target в инфинитиве (продавать, закрывать) без обращения на ты")
    chronic_tag: str = Field(description="Унифицированный тег ошибки")

class FeedbackRegen(BaseModel):
    sprint_target: str
    rop_1on1_script: str

class AuditResult(BaseModel):
    detected_call_archetype: str = Field(description="Определенный архетип звонка (например: 'Холодный прозвон / Вход в контакт', 'Квалификация', 'Демонстрация')")
    goal_achievement_index: int = Field(description="Интегральный индекс выполнения цели звонка от 0 до 100%")
    total_score: int = Field(description="Итоговый взвешенный балл из 100")
    call_duration: str = Field(description="Длительность звонка")
    stop_factor: str = Field(description="Наличие стоп-факторов (Нет / Описание)")
    score_justification: str = Field(description="Общий вердикт РОПа")
    main_victory: str = Field(description="Главная победа менеджера в этом звонке")
    all_positive_points: List[str] = Field(description="Полный реестр сильных сторон и успешных моментов за весь звонок")
    evaluated_nodes: List[DynamicNode] = Field(description="Динамический набор узлов (от 2 до 5), строго релевантных определенному архетипу звонка")
    all_errors: List[CallError]
    primary_error_index: int = 0
    rop_1on1_script: str

SYSTEM_INSTRUCTION = """
Ты — главный директор по продажам и эксперт по контролю качества (QA) коммерческого департамента BicoTender.
Твоя задача — прослушать аудиозапись звонка, проанализировать текстовые вводные РОПа и провести гибкий, контекстный аудит.

АЛГОРИТМ РАБОТЫ И АДАПТИВНЫЙ АУДИТ:
1. ОПРЕДЕЛЕНИЕ АРХЕТИПА ЗВОНКА:
   Учти выбранный РОПом тип контакта или определи его автоматически, если включено автоопределение. Возможные архетипы:
   - «Первый звонок в топку» (холодный поиск, пробой барьеров)
   - «Первый звонок в лид» (квалификация, оцифровка ниши)
   - «Первый звонок ОРВБ» (реактивация спящей базы)
   - «Демонстрация системы» (презентация функционала под боли)
   - «Отработка возражений / Торг» (работа с ценой и сомнениями)
   - «Закрытие / Соглашение» (фиксация следующего шага)
   - «Рабочий / Текущий созвонок (ОС, дожим, вопросы)» (получение обратной связи, обсуждение текущих вопросов, дожим)
2. ДИНАМИЧЕСКАЯ МАТРИЦА УЗЛОВ:
   Сформируй список `evaluated_nodes` строго под этот архетип (от 2 до 5 узлов). Не создавай искусственные штрафы за этапы, которых не должно быть по хронометражу.
3. ЧИСТОТА ДАННЫХ:
   - В полях `positives` и `growth_areas` пиши ТОЛЬКО текстовый анализ и факты. Без цитат и реплик.
   - Цитаты менеджера разбираются строго в блоке ошибок (`all_errors`).
   - Игнорируй панибратство. Скрипты РОПа формируй по методу бутерброда, строго без слова "НО".
"""

def analyze_audio_call(
    audio_path: str, manager_name: str, call_type: str, client_name: str = "",
    crm_url: str = "", custom_context: str = "", model_name: str = "gemini-3.6-flash", api_key: Optional[str] = None, max_retries: int = 5
) -> AuditResult:
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key: raise ValueError("Не указан GEMINI_API_KEY!")

    client = genai.Client(api_key=key)
    uploaded_audio = client.files.upload(file=audio_path)

    poll_start = time.time()
    while uploaded_audio.state.name == "PROCESSING":
        if time.time() - poll_start > 45:
            raise TimeoutError("Превышено время обработки аудио в Google Files API.")
        time.sleep(1)
        uploaded_audio = client.files.get(name=uploaded_audio.name)

    if uploaded_audio.state.name == "FAILED":
        raise RuntimeError("Ошибка обработки аудиофайла в Google.")

    context_note = f"\n[ВАЖНЫЙ КОНТЕКСТ И ЦЕЛЬ ЗВОНКА ОТ РОПа]: {custom_context}" if custom_context and custom_context.strip() else ""
    user_prompt = f"Аудит звонка: Менеджер: {manager_name}, Тип из интерфейса: {call_type}, Клиент: {client_name}, CRM: {crm_url}.{context_note}\nОпредели архетип звонка и сформируй релевантную динамическую матрицу узлов."

    last_exception = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=[uploaded_audio, user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=AuditResult,
                    temperature=0.1,
                ),
            )
            try:
                client.files.delete(name=uploaded_audio.name)
            except:
                pass
            return AuditResult.model_validate(json.loads(response.text))
            
        except Exception as exc:
            last_exception = exc
            err_msg = str(exc)
            if any(code in err_msg for code in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"]) and attempt < max_retries - 1:
                sleep_time = (2 ** attempt) + 1
                time.sleep(sleep_time)
                continue
            break

    try:
        client.files.delete(name=uploaded_audio.name)
    except:
        pass
    raise last_exception

def regenerate_feedback_for_error(
    manager_name: str, main_victory: str, selected_error: CallError,
    model_name: str = "gemini-3.6-flash", api_key: Optional[str] = None
) -> FeedbackRegen:
    key = api_key or os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=key)

    prompt = f"Менеджер: {manager_name}\nПобеда: {main_victory}\nОшибка: {selected_error.stage} - {selected_error.description}\nЦитата: «{selected_error.quote}»\nСформируй sprint_target (инфинитив, без ты) и rop_1on1_script (без слова НО)."
    
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=FeedbackRegen,
                    temperature=0.1,
                ),
            )
            return FeedbackRegen.model_validate(json.loads(response.text))
        except Exception as exc:
            if attempt == 2:
                raise exc
            time.sleep(2)