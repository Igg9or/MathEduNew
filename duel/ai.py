import openai, json

def evaluate_pair(question, answer_a, answer_b):
    """Сравнение двух гуманитарных ответов через AI"""
    prompt = f"""
Ты преподаватель гуманитарных наук.
Оцени два ответа на один вопрос по критериям:
1) Аргументация 2) Глубина 3) Логика 4) Язык 5) Креативность.
Выстави баллы (0–10) и выбери победителя.
Формат JSON:
{{"A_score":8,"B_score":9,"winner":"B","comment":"B глубже аргументировал"}}
Вопрос: {question}
Ответ A: {answer_a}
Ответ B: {answer_b}
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-5",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        text = response.choices[0].message["content"]
        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}
