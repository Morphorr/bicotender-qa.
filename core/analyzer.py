import os
import json
import base64
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import requests

load_dotenv()

class DynamicNode(BaseModel):
    node_title: str = Field(description="Название этапа, релевантное для данного архетипа звонка")
    score: int = Field(description="Фактический балл по этому узлу")
    max_score: int = Field(description="Максимальный балл для этого узла")
    criteria: str = Field(description="Краткое описание того, что оценивалось в данном узле")
    positives: str = Field(description="Факты успехов менеджера на этом этапе")
    growth_areas: str = Field(description="Зоны роста / причины снижения балла")

class CallError(BaseModel):
    timestamp: str = Field(description="Таймкод ММ:СС")
    stage: str = Field(description="Этап диалога")
    description: str = Field(description="Суть ошибки без CAPS LOCK")
    quote: str = Field(description="Дословная цитата менеджера")
    correct_alternative_script: str = Field(description="Развернутая эталонная реплика в кавычках БЕЗ таймкода")
    support_growth_potential: str = Field(description="Слой 3: поддержка экспертности")
    sprint_target: str = Field(description="Target в инфинитиве")
    chronic_tag: str = Field(description="Унифицированный тег ошибки")

class FeedbackRegen(BaseModel):
    sprint_target: str
    rop_1on1_script: str

class AuditResult(BaseModel):
    detected_call_archetype: str = Field(description="Определенный архетип звонка")
    goal_achievement_index: int = Field(description="Интегральный индекс выполнения цели звонка от 0 до 100%")
    total_score: int = Field(description="Итоговый взвешенный балл из 100")
    call_duration: str = Field(description="Длительность звонка")
    stop_factor: str = Field(description="Наличие стоп-факторов")
    score_justification: str = Field(description="Общий вердикт РОПа")
    main_victory: str = Field(description="Главная победа менеджера в этом звонке")
    all_positive_points: List[str] = Field(description="Полный реестр сильных сторон")
    evaluated_nodes: List[DynamicNode] = Field(description="Динамический набор узлов")
    all_errors: List[CallError]
    primary_error_index: int = 0
    rop_1on1_script: str

SYSTEM_INSTRUCTION = """
Ты — главный директор по продажам и эксперт по контролю качества (QA) коммерческого департамента BicoTender.
"""

AUDIT_SCHEMA_DICT = {
    "type": "OBJECT",
    "properties": {
        "detected_call_archetype": {"type": "STRING"},
        "goal_achievement_index": {"type": "INTEGER"},
        "total_score": {"type": "INTEGER"},
        "call_duration": {"type": "STRING"},
        "stop_factor": {"type": "STRING"},
        "score_justification": {"type": "STRING"},
        "main_victory": {"type": "STRING"},
        "all_positive_points": {"type": "ARRAY", "items": {"type": "STRING"}},
        "evaluated_nodes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "node_title": {"type": "STRING"},
                    "score": {"type": "INTEGER"},
                    "max_score": {"type": "INTEGER"},
                    "criteria": {"type": "STRING"},
                    "positives": {"type": "STRING"},
                    "growth_areas": {"type": "STRING"}
                }
            }
        },
        "all_errors": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "timestamp": {"type": "STRING"},
                    "stage": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "quote": {"type": "STRING"},
                    "correct_alternative_script": {"type": "STRING"},
                    "support_growth_potential": {"type": "STRING"},
                    "sprint_target": {"type": "STRING"},
                    "chronic_tag": {"type": "STRING"}
                }
            }
        },
        "primary_error_index": {"type": "INTEGER"},
        "rop_1on1_script": {"type": "STRING"}
    }
}

REGEN_SCHEMA_DICT = {
    "type": "OBJECT",
    "properties": {
        "sprint_target": {"type": "STRING"},
        "rop_1on1_script": {"type": "STRING"}
    }
}

def analyze_audio_call(
    audio_path: str, manager_name: str, call_type: str, 
    client_name: str = "", crm_url: str = "", custom_context: str = "", 
    model_name: str = "gemini-3.6-flash", api_key: Optional[str] = None, max_retries: int = 5
) -> AuditResult:
    token = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not token:
        raise ValueError("Не найден токен авторизации GEMINI_API_KEY!")

    clean_model = "gemini-1.5-flash"
    
    # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Передаем ключ прямо в URL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={token.strip()}"

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Аудиофайл не найден: {audio_path}")

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    mime_type = "audio/wav" if audio_path.lower().endswith(".wav") else "audio/m4a" if audio_path.lower().endswith(".m4a") else "audio/mp3"

    context_note = f"\n[КОНТЕКСТ ОТ РОПа]: {custom_context}" if custom_context else ""
    user_prompt = f"Аудит звонка: Менеджер: {manager_name}, Тип: {call_type}, Клиент: {client_name}.{context_note}"

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime_type, "data": audio_b64}},
                {"text": user_prompt}
            ]
        }],
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": AUDIT_SCHEMA_DICT
        }
    }

    # Убрали x-goog-api-key из заголовков, чтобы не путать сервера Google
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise RuntimeError(f"Ошибка API Gemini [{response.status_code}]: {response.text}")

    res_json = response.json()
    response_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
    return AuditResult.model_validate(json.loads(response_text))

def regenerate_feedback_for_error(
    manager_name: str, main_victory: str, selected_error: CallError,
    model_name: str = "gemini-3.6-flash", api_key: Optional[str] = None
) -> FeedbackRegen:
    token = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    clean_model = "gemini-1.5-flash"
    
    # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Передаем ключ прямо в URL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={token.strip()}"

    prompt = f"Менеджер: {manager_name}\nПобеда: {main_victory}\nОшибка: {selected_error.stage} - {selected_error.description}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "responseSchema": REGEN_SCHEMA_DICT
        }
    }
    
    # Убрали x-goog-api-key из заголовков
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise RuntimeError(f"Ошибка регенерации [{response.status_code}]: {response.text}")
        
    res_json = response.json()
    return FeedbackRegen.model_validate(json.loads(res_json["candidates"][0]["content"]["parts"][0]["text"]))