import random

WORDS = [
    "sun", "fox", "math", "star", "book",
    "tree", "sky", "note", "code", "line"
]

def generate_password():
    word = random.choice(WORDS)
    number = random.randint(100, 999)
    return f"{word}-{number}"
