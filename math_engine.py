# math_engine.py
import random
import sympy
from sympy.parsing.sympy_parser import parse_expr
from sympy import symbols, simplify
import math
from math import gcd

def lcm(a, b):
    return abs(a * b) // gcd(a, b)


class MathEngine:
    @staticmethod
    def _band_slice(n: int, band: int | None):
        """
        Возвращает диапазон индексов [start, end) для выбранной оценки.
        2 → первые 25%, 3 → 25-50%, 4 → 50-75%, 5 → 75-100%.
        Если band не задан или некорректен, возвращаем весь диапазон.
        """
        if not band or band not in (2, 3, 4, 5) or n <= 1:
            return 0, n

        q1 = math.ceil(n * 0.25)
        q2 = math.ceil(n * 0.50)
        q3 = math.ceil(n * 0.75)
        cuts = [0, q1, q2, q3, n]
        mapping = {
            2: (cuts[0], cuts[1]),
            3: (cuts[1], cuts[2]),
            4: (cuts[2], cuts[3]),
            5: (cuts[3], cuts[4])
        }
        start, end = mapping[band]
        # гарантируем, что диапазон не пустой
        if start >= end:
            start = max(0, min(n - 1, start))
            end = min(n, start + 1)
        return start, end

    @staticmethod
    def generate_parameters(template_params, conditions='', band: int | None = None):
        params = {}
        # 1. Собираем все ключи типа choice для согласованного выбора
        choice_keys = [param for param, config in template_params.items()
                       if isinstance(config, dict) and config.get('type') == 'choice']
        choice_len = None
        if len(choice_keys) >= 2:
            lengths = [len(template_params[k]['values']) for k in choice_keys]
            if len(set(lengths)) == 1:
                choice_len = lengths[0]

        for _ in range(100):  # Максимум 100 попыток
            generated = {}
            valid = True

            # Генерация согласованных choice-параметров по индексу
            if choice_len:
                start, end = MathEngine._band_slice(choice_len, band)
                idx = random.randrange(start, end)
                for k in choice_keys:
                    generated[k] = template_params[k]['values'][idx]

            # Генерация остальных параметров
            for param, config in template_params.items():
                if param == 'conditions' or (choice_len and param in choice_keys):
                    continue

                if config['type'] == 'int':
                    value = random.randint(config['min'], config['max'])
                    # Применяем ограничения
                    if 'constraints' in config:
                        for constraint in config['constraints']:
                            if constraint['type'] == 'multiple_of':
                                remainder = value % constraint['value']
                                if remainder != 0:
                                    value += (constraint['value'] - remainder)
                                    if value > config['max']:
                                        value -= constraint['value']
                    generated[param] = value

                elif config['type'] == 'float':
                    min_v = config.get('min', 0)
                    max_v = config.get('max', 1)
                    step = config.get('constraints', [{}])[0].get('value', 0.01)
                    # step ищем первый multiple_of или default=0.01
                    for c in config.get('constraints', []):
                        if c.get('type') == 'multiple_of':
                            step = c.get('value', 0.01)
                    steps = int(round((max_v - min_v) / step))
                    value = min_v + step * random.randint(0, steps)
                    value = round(value, str(step)[::-1].find('.'))
                    generated[param] = value

                elif config['type'] == 'choice':
                    # Одиночные choice (не согласованные)
                    generated[param] = random.choice(config['values'])

            # Проверка условий
            if valid and conditions:
                try:
                    if not eval(conditions, {}, generated):
                        valid = False
                except:
                    valid = False

            if valid:
                return generated

        # Если не удалось сгенерировать - возвращаем последний вариант
        return generated


    
    
    @staticmethod
    def evaluate_expression(expr, params):
        try:
            # Заменяем параметры в выражении
            for param, value in params.items():
                expr = expr.replace(f'{{{{{param}}}}}', str(value))

            # Добавляем безопасные функции
            safe_funcs = {
                'gcd': math.gcd,
                'lcm': lcm,
                'abs': abs,
                'round': round,
                'int': int
            }

            # Пробуем напрямую вычислить выражение
            try:
                result = eval(expr, {"__builtins__": {}}, {**params, **safe_funcs})
                return str(result)
            except:
                pass  # fallback на sympy

            # Если eval не сработал — используем sympy
            parsed = parse_expr(expr, evaluate=True)

            if any(symbol in str(parsed) for symbol in ['x', 'y', 'z']):
                simplified = sympy.simplify(parsed)
                return str(simplified).replace('*', '')

            return str(float(parsed.evalf()))

        except Exception as e:
            print(f"Error evaluating expression: {expr} with params {params}. Error: {e}")
            return None
    
            # Заменяем параметры в выражении
            for param, value in params.items():
                expr = expr.replace(f'{{{param}}}', str(value))
            
            # Проверяем, является ли выражение дробью
            if '/' in expr and len(expr.split('/')) == 2:
                numerator, denominator = expr.split('/')
                try:
                    numerator_val = float(numerator)
                    denominator_val = float(denominator)
                    if denominator_val != 0:
                        return str(numerator_val / denominator_val)
                except:
                    pass  # Продолжаем обычную обработку
            
            # Остальная логика вычислений (как было раньше)
            parsed = parse_expr(expr, evaluate=True)
            
            if any(symbol in str(parsed) for symbol in ['x', 'y', 'z']):
                simplified = sympy.simplify(parsed)
                return str(simplified).replace('*', '')
            
            return str(float(parsed.evalf()))
            
        except Exception as e:
            print(f"Error evaluating expression: {expr} with params {params}. Error: {e}")
            return None
