(function() {
    console.log('[DUEL] Script executing...');
    const cfg = window.duelConfig || {};
    const lessonId = cfg.lessonId;
    const matchId = cfg.matchId;
    const userId = cfg.userId;
    const timeSeconds = cfg.timeSeconds || 0;

    let timerInterval = null;
    let timeLeft = timeSeconds;
    let roundEnded = false;

    console.log('[DUEL] Config loaded:', cfg, 'timeSeconds:', timeSeconds, 'matchId:', matchId);

    // ========================
    // INIT
    // ========================
    document.addEventListener('DOMContentLoaded', function() {
        console.log('[DUEL] DOM ready, matchId:', matchId, 'timeSeconds:', timeSeconds);
        if (!matchId) {
            console.warn('[DUEL] No matchId, aborting init');
            return;
        }

        // Вешаем обработчики на кнопки проверки
        document.querySelectorAll('.btn-check').forEach(button => {
            button.addEventListener('click', function() {
                checkDuelAnswer(this.closest('.task-card'));
            });
        });

        startTimer();
        pollOpponentScore();
        pollMatchStatus();
    });

    // ========================
    // ПРОВЕРКА ОТВЕТА (без мгновенного показа результата)
    // ========================
    async function checkDuelAnswer(taskCard) {
        if (roundEnded) return;

        const taskId = taskCard.dataset.taskId;
        let userAnswer = taskCard.querySelector('.answer-input').value.trim();
        const correctAnswer = taskCard.dataset.correctAnswer;
        const answerType = taskCard.dataset.answerType || 'numeric';

        if (!userAnswer) {
            alert("Введите ответ!");
            return;
        }

        // Блокируем повторный ввод
        const input = taskCard.querySelector('.answer-input');
        const btn = taskCard.querySelector('.btn-check');
        if (input.disabled) return;
        input.disabled = true;
        btn.disabled = true;

        // Автозамена sqrt
        userAnswer = userAnswer.replace(/([0-9]*\.?[0-9]*|)\s*√\s*(\(?[a-zA-Z0-9+*/\s-]+\)?)/g, function(_, coeff, radicand) {
            const coefficient = coeff.trim() === '' ? '' : coeff.trim() + '*';
            return coefficient + 'sqrt(' + radicand.trim() + ')';
        });

        // 1) Автоматическая проверка
        const normalizedUser = userAnswer.trim().replace(/\s+/g, "").toLowerCase();
        const normalizedCorrect = correctAnswer.trim().replace(/\s+/g, "").toLowerCase();

        let isCorrect = false;

        if (normalizedUser === normalizedCorrect) {
            isCorrect = true;
        } else {
            // 2) API check_answer
            try {
                const response = await fetch('/api/check_answer', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        answer: userAnswer,
                        correct_answer: correctAnswer,
                        answer_type: answerType
                    })
                });
                const result = await response.json();
                if (result.is_correct) {
                    isCorrect = true;
                } else {
                    // 3) ИИ fallback
                    const questionText = extractQuestionForAI(taskCard);
                    if (!_isLinkOnlyQuestion(questionText)) {
                        isCorrect = await fallbackToAI(taskCard, userAnswer);
                    }
                }
            } catch (e) {
                console.error('Ошибка проверки:', e);
            }
        }

        // Показываем только "Ответ сохранён" (результат скрыт до конца раунда)
        showSavedStatus(taskCard);

        // Получаем ИИ-решение если ответ неправильный
        let aiSolution = '';
        if (!isCorrect) {
            try {
                aiSolution = await fetchAIExplanation(taskCard, userAnswer);
            } catch (e) {
                console.error('Ошибка получения ИИ-решения:', e);
            }
        }

        // Отправляем в дуэль API
        try {
            await fetch(`/api/duel/match/${matchId}/answer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: taskId,
                    answer: userAnswer,
                    is_correct: isCorrect,
                    ai_solution: aiSolution
                })
            });
        } catch (e) {
            console.error('Ошибка отправки в дуэль:', e);
        }

        // Обновляем свой счёт
        updateMyScore();
    }

    function showSavedStatus(taskCard) {
        const feedback = taskCard.querySelector('.task-feedback');
        const savedFb = taskCard.querySelector('.feedback-saved');
        feedback.classList.remove('hidden');
        savedFb.classList.remove('hidden');
    }

    async function fetchAIExplanation(taskCard, studentAnswer) {
        const questionText = extractQuestionForAI(taskCard);
        const correctAnswer = taskCard.dataset.correctAnswer;
        try {
            const response = await fetch('/api/ai_full_solution', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: taskCard.dataset.taskId,
                    user_id: userId,
                    question: questionText,
                    correct_answer: correctAnswer,
                    student_answer: studentAnswer,
                    grade: taskCard.dataset.grade || 5
                })
            });
            const data = await response.json();
            return data.solution || '';
        } catch (e) {
            console.error('AI explanation error:', e);
            return '';
        }
    }

    async function fallbackToAI(taskCard, studentAnswer) {
        const questionText = extractQuestionForAI(taskCard);
        const correctAnswer = taskCard.dataset.correctAnswer;
        try {
            const response = await fetch('/api/ai_full_solution', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: taskCard.dataset.taskId,
                    user_id: userId,
                    question: questionText,
                    correct_answer: correctAnswer,
                    student_answer: studentAnswer,
                    grade: taskCard.dataset.grade || 5
                })
            });
            const data = await response.json();
            return data.ai_verdict?.is_student_correct === true;
        } catch (e) {
            console.error('AI fallback error:', e);
            return false;
        }
    }

    function extractQuestionForAI(taskCard) {
        const qNode = taskCard.querySelector('.task-question');
        if (!qNode) return '';
        let raw = qNode.dataset ? qNode.dataset.questionRaw : '';
        if (raw) {
            try { raw = JSON.parse(raw); } catch { /* already string */ }
        } else {
            raw = qNode.innerHTML || '';
        }
        return raw.trim();
    }

    function _isLinkOnlyQuestion(text) {
        if (!text) return false;
        const q = text.trim();
        return q.startsWith('http') || q.startsWith('<a href=') || (q.includes('http') && q.includes('<a'));
    }

    // ========================
    // ПОКАЗ РЕЗУЛЬТАТОВ ПОСЛЕ РАУНДА
    // ========================
    async function showRoundResults() {
        // Блокируем все поля
        document.querySelectorAll('.answer-input').forEach(el => el.disabled = true);
        document.querySelectorAll('.btn-check').forEach(el => el.disabled = true);

        try {
            const res = await fetch(`/api/duel/match/${matchId}/my_answers`);
            const data = await res.json();
            if (!data.answers) return;

            const answerMap = {};
            data.answers.forEach(a => { answerMap[a.task_id] = a; });

            document.querySelectorAll('.task-card').forEach(card => {
                const taskId = parseInt(card.dataset.taskId);
                const ans = answerMap[taskId];
                if (!ans) return;

                const feedback = card.querySelector('.task-feedback');
                const savedFb = card.querySelector('.feedback-saved');
                const correctFb = card.querySelector('.feedback-correct');
                const incorrectFb = card.querySelector('.feedback-incorrect');
                const aiFb = card.querySelector('.feedback-ai');
                const status = card.querySelector('.task-status');

                feedback.classList.remove('hidden');
                savedFb.classList.add('hidden');

                if (ans.is_correct) {
                    correctFb.classList.remove('hidden');
                    incorrectFb.classList.add('hidden');
                    status.style.backgroundColor = 'var(--success)';
                    card.classList.add('correct');
                } else {
                    correctFb.classList.add('hidden');
                    incorrectFb.classList.remove('hidden');
                    incorrectFb.querySelector('.correct-answer').textContent = ans.correct_answer || card.dataset.correctAnswer || '';
                    status.style.backgroundColor = 'var(--error)';
                    card.classList.add('incorrect');

                    if (ans.ai_solution) {
                        aiFb.classList.remove('hidden');
                        aiFb.querySelector('.ai-solution-text').innerHTML = ans.ai_solution;
                        if (window.MathJax) {
                            window.MathJax.typesetPromise([aiFb.querySelector('.ai-solution-text')]);
                        }
                    }
                }
            });
        } catch (e) {
            console.error('Ошибка загрузки результатов:', e);
        }
    }

    // ========================
    // ТАЙМЕР
    // ========================
    function startTimer() {
        const timerEl = document.getElementById('duelTimer');
        if (!timerEl || timeSeconds <= 0) return;

        timeLeft = timeSeconds;
        updateTimerDisplay();

        timerInterval = setInterval(() => {
            timeLeft--;
            updateTimerDisplay();
            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                onTimeUp();
            }
        }, 1000);
    }

    function updateTimerDisplay() {
        const timerEl = document.getElementById('duelTimer');
        if (!timerEl) return;
        const m = Math.floor(timeLeft / 60);
        const s = timeLeft % 60;
        timerEl.textContent = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        timerEl.classList.remove('warning', 'danger');
        if (timeLeft <= 30) timerEl.classList.add('danger');
        else if (timeLeft <= 60) timerEl.classList.add('warning');
    }

    async function onTimeUp() {
        if (roundEnded) return;
        roundEnded = true;
        try {
            await fetch(`/api/duel/match/${matchId}/complete`, { method: 'POST' });
        } catch (e) { console.error(e); }

        await showRoundResults();

        const overlay = document.getElementById('roundOverOverlay');
        const resultEl = document.getElementById('overlayResult');
        const scoresEl = document.getElementById('overlayScores');

        const res = await fetch(`/api/duel/${lessonId}/my_match`);
        const data = await res.json();
        const m = data.match;
        let myScore = 0, oppScore = 0;
        if (m) {
            myScore = m.player1_id === userId ? (m.player1_score || 0) : (m.player2_score || 0);
            oppScore = m.player1_id === userId ? (m.player2_score || 0) : (m.player1_score || 0);
        }

        if (myScore > oppScore) {
            resultEl.textContent = '🎉 Вы победили!';
            resultEl.className = 'round-result win';
        } else if (oppScore > myScore) {
            resultEl.textContent = '😞 Вы проиграли';
            resultEl.className = 'round-result lose';
        } else {
            resultEl.textContent = '🤝 Ничья';
            resultEl.className = 'round-result';
        }
        scoresEl.innerHTML = `Вы: <strong>${myScore}</strong> — Противник: <strong>${oppScore}</strong>`;
        overlay.classList.add('show');
    }

    // ========================
    // ОБНОВЛЕНИЕ СЧЁТА
    // ========================
    async function updateMyScore() {
        try {
            const res = await fetch(`/api/duel/${lessonId}/my_match`);
            const data = await res.json();
            if (data.match) {
                const m = data.match;
                const myScoreEl = document.getElementById('myScore');
                const opponentScoreEl = document.getElementById('opponentScore');
                if (myScoreEl) myScoreEl.textContent = m.player1_id === userId ? (m.player1_score || 0) : (m.player2_score || 0);
                if (opponentScoreEl) opponentScoreEl.textContent = m.player1_id === userId ? (m.player2_score || 0) : (m.player1_score || 0);
            }
        } catch (e) { console.error(e); }
    }

    async function pollOpponentScore() {
        if (roundEnded) return;
        await updateMyScore();
        setTimeout(pollOpponentScore, 5000);
    }

    async function pollMatchStatus() {
        if (roundEnded) return;
        try {
            const res = await fetch(`/api/duel/${lessonId}/my_match`);
            const data = await res.json();
            if (data.match && data.match.status === 'completed') {
                roundEnded = true;
                await showRoundResults();
                // overlay показываем с небольшой задержкой чтобы результаты успели отрисоваться
                setTimeout(onTimeUpOverlay, 500);
            }
        } catch (e) { /* ignore */ }
        setTimeout(pollMatchStatus, 5000);
    }

    async function onTimeUpOverlay() {
        const overlay = document.getElementById('roundOverOverlay');
        const resultEl = document.getElementById('overlayResult');
        const scoresEl = document.getElementById('overlayScores');

        const res = await fetch(`/api/duel/${lessonId}/my_match`);
        const data = await res.json();
        const m = data.match;
        let myScore = 0, oppScore = 0;
        if (m) {
            myScore = m.player1_id === userId ? (m.player1_score || 0) : (m.player2_score || 0);
            oppScore = m.player1_id === userId ? (m.player2_score || 0) : (m.player1_score || 0);
        }

        if (myScore > oppScore) {
            resultEl.textContent = '🎉 Вы победили!';
            resultEl.className = 'round-result win';
        } else if (oppScore > myScore) {
            resultEl.textContent = '😞 Вы проиграли';
            resultEl.className = 'round-result lose';
        } else {
            resultEl.textContent = '🤝 Ничья';
            resultEl.className = 'round-result';
        }
        scoresEl.innerHTML = `Вы: <strong>${myScore}</strong> — Противник: <strong>${oppScore}</strong>`;
        overlay.classList.add('show');
    }

    // ========================
    // СЕТКА ТУРНИРА
    // ========================
    window.showBracket = async function() {
        const modal = document.getElementById('bracketModal');
        const content = document.getElementById('bracketContent');
        try {
            const res = await fetch(`/api/duel/${lessonId}/bracket`);
            const data = await res.json();
            let html = '';
            if (data.rounds && data.matches) {
                data.rounds.forEach(r => {
                    html += `<div style="margin-bottom: 20px;">`;
                    html += `<h4 style="margin-bottom: 10px; color: var(--primary);">${r.round_name}</h4>`;
                    const roundMatches = data.matches.filter(m => m.round_id === r.id);
                    if (roundMatches.length === 0) {
                        html += `<p style="color: var(--text-muted); font-size: 14px;">Матчи ещё не созданы</p>`;
                    } else {
                        roundMatches.forEach(m => {
                            const p1 = m.player1_name || '—';
                            const p2 = m.player2_name || '—';
                            const winner = m.winner_name ? `🏆 ${m.winner_name}` : '—';
                            const score1 = m.player1_score || 0;
                            const score2 = m.player2_score || 0;
                            html += `
                                <div style="background: var(--bg); padding: 12px; border-radius: 8px; margin-bottom: 8px; font-size: 14px;">
                                    <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                        <span>${p1}</span>
                                        <strong>${score1} : ${score2}</strong>
                                        <span>${p2}</span>
                                    </div>
                                    <div style="color: var(--success); font-size: 13px;">Победитель: ${winner}</div>
                                </div>
                            `;
                        });
                    }
                    html += `</div>`;
                });
            } else {
                html = '<p>Сетка пока недоступна</p>';
            }
            content.innerHTML = html;
            modal.classList.remove('hidden');
        } catch (e) {
            console.error(e);
            content.innerHTML = '<p>Ошибка загрузки сетки</p>';
            modal.classList.remove('hidden');
        }
    };

    window.hideBracket = function() {
        document.getElementById('bracketModal').classList.add('hidden');
    };
})();
