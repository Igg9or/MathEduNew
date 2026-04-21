import re
from math_engine import MathEngine
from sympy import simplify, parse_expr


def simplify_polynomial_answer(answer: str) -> str:
    # Удаляем a^0 → ''
    answer = re.sub(r'([a-zA-Z])\^0', '', answer)
    # a^1 → a
    answer = re.sub(r'([a-zA-Z])\^1', r'\1', answer)
    # 1a → a
    answer = re.sub(r'(?<!\d)1([a-zA-Z])', r'\1', answer)
    # // → /
    answer = re.sub(r'//', '/', answer)
    # Убираем пробелы
    answer = re.sub(r'\s+', '', answer)
    # 1a/b → a/b, a/1 → a
    answer = re.sub(r'^1([a-zA-Z].*)/(.+)$', r'\1/\2', answer)
    answer = re.sub(r'^(.+)/1$', r'\1', answer)
    return answer if answer else '1'


class TaskGenerator:
    @staticmethod
    def generate_task_variant(
        template,
        band: int | None = None,
        forced_choice_idx: int | None = None
    ):
        if not all(k in template for k in ('question_template', 'answer_template', 'parameters')):
            return None

        # -------------------------
        # 1. Генерация параметров
        # -------------------------
        params = {}
        if template.get('parameters'):
            params = MathEngine.generate_parameters(
                template['parameters'],
                template.get('conditions', ''),
                band=band,
                forced_choice_idx=forced_choice_idx
            )

        choice_idx = params.pop('__choice_idx', None)

        # expression-параметры
        for param, config in template.get('parameters', {}).items():
            if isinstance(config, dict) and config.get('type') == 'expression':
                try:
                    params[param] = eval(config['value'], {}, dict(params))
                except Exception as e:
                    print(f"Ошибка expression '{param}': {e}")
                    params[param] = "Ошибка"

        # -------------------------
        # 2. Формирование вопроса
        # -------------------------
        question = template['question_template']
        for param, value in params.items():
            question = re.sub(rf"\{{{param}\}}", str(value), question)

        question = re.sub(r'(?<!\d)1([a-zA-Z])', r'\1', question)

        # -------------------------
        # 3. Подстановка в ответ
        # -------------------------
        def eval_expr(match):
            expr = match.group(1)
            try:
                from math import gcd

                def lcm(a, b):
                    return abs(a * b) // gcd(a, b)

                safe_funcs = {
                    'round': round,
                    'abs': abs,
                    'min': min,
                    'max': max,
                    'gcd': gcd,
                    'lcm': lcm,
                    'int': int
                }

                local_vars = dict(params)

                # Если просто имя параметра
                if expr in local_vars:
                    return str(local_vars[expr])

                # Если выражение
                return str(eval(expr, safe_funcs, local_vars))
            except Exception as e:
                print(f"Ошибка eval '{expr}': {e}")
                return "Ошибка"

        answer_template = template['answer_template']
        answer = re.sub(r"\{([^{}]+)\}", eval_expr, answer_template)

        # -------------------------
        # 🚫 4. STRING → БЕЗ SYMPY
        # -------------------------
        answer_type = template.get('answer_type', 'numeric')
        if answer_type == 'string':
            return {
                'question': question,
                'correct_answer': answer,
                'params': params,
                'template_id': template.get('id'),
                'choice_idx': choice_idx
            }

        # -------------------------
        # 5. NUMERIC → SYMPY
        # -------------------------
        try:
            parsed = parse_expr(answer.replace('^', '**'))
            answer = str(simplify(parsed)).replace('**', '^')
        except Exception as e:
            print(f"[sympy error]: {e}")

        answer = simplify_polynomial_answer(answer)

        try:
            answer = str(
                simplify(parse_expr(answer.replace('^', '**')))
            ).replace('**', '^')
        except Exception as e:
            print(f"[sympy final error]: {e}")

        # -------------------------
        # 6. Форматирование чисел
        # -------------------------
        try:
            val = round(float(answer), 6)
            if val.is_integer():
                answer = str(int(val))
            else:
                answer = str(val)
        except Exception:
            pass

        return {
            'question': question,
            'correct_answer': answer,
            'params': params,
            'template_id': template.get('id'),
            'choice_idx': choice_idx
        }

    @staticmethod
    def extract_parameters(template_str):
        return list(set(re.findall(r'\{([A-Za-z]+)\}', template_str)))
