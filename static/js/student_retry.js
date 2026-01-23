document.querySelectorAll('.btn-check').forEach(btn => {
    btn.addEventListener('click', async () => {
        const card = btn.closest('.task-card');
        const userAnswer = card.querySelector('.answer-input').value.trim();
        const correctAnswer = card.dataset.correctAnswer.trim();
        const taskId = card.dataset.taskId;

        if (!userAnswer) return alert("Введите ответ");

        const feedbackCorrect = card.querySelector('.feedback-correct');
        const feedbackIncorrect = card.querySelector('.feedback-incorrect');

        if (userAnswer.toLowerCase() === correctAnswer.toLowerCase()) {
            feedbackCorrect.classList.remove('hidden');
            feedbackIncorrect.classList.add('hidden');
            card.querySelector('.answer-input').disabled = true;
            btn.disabled = true;

            await fetch('/api/mark_error_resolved', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_id: taskId })
            });
        } else {
            feedbackIncorrect.classList.remove('hidden');
            feedbackCorrect.classList.add('hidden');
        }
    });
});
