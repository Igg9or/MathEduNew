document.addEventListener('DOMContentLoaded', function() {
    const lessonId = window.location.pathname.split('/').pop();
    let chart = null;
    let studentIds = [];
    let isUpdating = false;

    // Получаем ID всех учеников
    document.querySelectorAll('#studentsResults tr').forEach(row => {
        studentIds.push(row.dataset.studentId);
    });

    // Основная функция обновления данных
    async function updateAllData() {
        if (isUpdating) return;
        isUpdating = true;
        
        try {
            // Добавляем индикатор загрузки
            document.getElementById('refreshResults').disabled = true;
            document.querySelectorAll('#studentsResults tr').forEach(row => {
                row.classList.add('updating');
            });

            // Параллельные запросы
            const [progressData, analyticsData] = await Promise.all([
                fetchStudentProgress(),
                fetchLessonAnalytics()
            ]);

            // Обновляем интерфейс
            updateStudentResults(progressData);
            updateAnalytics(analyticsData);
            
        } catch (error) {
            console.error('Update error:', error);
            showErrorNotification('Ошибка обновления данных');
        } finally {
            // Убираем индикатор загрузки
            document.getElementById('refreshResults').disabled = false;
            document.querySelectorAll('#studentsResults tr').forEach(row => {
                row.classList.remove('updating');
            });
            isUpdating = false;
        }
    }

    // Запрос прогресса студентов
    async function fetchStudentProgress() {
        const response = await fetch(`/teacher/get_student_progress/${lessonId}`);
        if (!response.ok) throw new Error('Network error');
        return await response.json();
    }

    // Запрос аналитики урока
    async function fetchLessonAnalytics() {
        const response = await fetch(`/teacher/get_lesson_results/${lessonId}`);
        if (!response.ok) throw new Error('Network error');
        return await response.json();
    }

    // Обновление таблицы студентов
    function updateStudentResults(data) {
        data.forEach(student => {
            const row = document.querySelector(`tr[data-student-id="${student.student_id}"]`);
            if (!row) return;

            // Обновляем задания
            student.tasks.forEach((task, index) => {
                const tasksCount = student.tasks.length;
                const cell = row.cells[index + 1]; // ОК, НО ниже важное
                if (!cell) return;
                
                cell.innerHTML = task.answered 
                    ? (task.is_correct 
                        ? '<span class="correct" title="Правильно">✓</span>' 
                        : '<span class="incorrect" title="Ошибка">✗</span>')
                    : '<span class="pending" title="Не отвечено">—</span>';
            });

            // Обновляем прогресс
            // Обновляем прогресс
const progressBar = row.querySelector('.progress-bar');
const progressText = row.querySelector('.progress-container span');

if (progressBar && progressText) {
    const total = student.tasks.length;
    const correct = student.tasks.filter(t => t.is_correct).length;
    const percent = total ? Math.round((correct / total) * 100) : 0;

    progressBar.style.width = percent + '%';
    progressText.textContent = percent + '%';
}

        });
    }

    // Обновление аналитики
    function updateAnalytics(data) {
        if (!data.results) return;
        
        updateDifficultTasks(data.results);
        updateCommonErrors(data.results);
        renderPerformanceChart(data.results);
    }

    // Топ сложных заданий
    function updateDifficultTasks(results) {
        const tasksStats = calculateTasksStats(results);
        const container = document.querySelector('.progress-bars');
        if (!container) return;
        
        container.innerHTML = tasksStats
            .sort((a, b) => a.correctPercent - b.correctPercent)
            .slice(0, 3)
            .map(task => `
                <div class="task-progress">
                    <span>Задание ${task.taskNumber}</span>
                    <progress 
                        value="${task.correctPercent}" 
                        max="100"
                        class="${task.correctPercent < 50 ? 'danger' : ''}"
                    ></progress>
                    <span>${task.correctPercent}%</span>
                </div>
            `).join('');
    }

    // Типичные ошибки
    function updateCommonErrors(results) {
        const errors = findCommonErrors(results);
        const container = document.querySelector('.errors-list');
        if (!container) return;
        
        container.innerHTML = errors
            .slice(0, 5)
            .map(error => `
                <li>
                    <span>${error.type}</span>
                    <span class="error-count">${error.count} чел.</span>
                </li>
            `).join('');
    }

    // Расчет статистики по заданиям
    function calculateTasksStats(results) {
        const tasks = {};
        
        results.forEach(student => {
            student.tasks.forEach(task => {
                if (!tasks[task.task_id]) {
                    tasks[task.task_id] = {
                        correct: 0,
                        total: 0,
                        taskNumber: Object.keys(tasks).length + 1
                    };
                }
                
                tasks[task.task_id].total++;
                if (task.is_correct) tasks[task.task_id].correct++;
            });
        });
        
        return Object.values(tasks).map(task => ({
            ...task,
            correctPercent: Math.round((task.correct / task.total) * 100) || 0
        }));
    }

    // Поиск общих ошибок (упрощенная версия)
    function findCommonErrors(results) {
        const errors = {};
        
        results.forEach(student => {
            student.tasks.forEach(task => {
                if (!task.is_correct && task.answered) {
                    const errorType = analyzeError(task.answer);
                    errors[errorType] = (errors[errorType] || 0) + 1;
                }
            });
        });
        
        return Object.entries(errors)
            .map(([type, count]) => ({ type, count }))
            .sort((a, b) => b.count - a.count);
    }

    // Анализ ошибки (заглушка - в реальной системе нужен глубокий анализ)
    function analyzeError(answer) {
        // Здесь можно добавить сложную логику анализа ответов
        if (/делен|division/i.test(answer)) return "Ошибка в делении";
        if (/знак|sign/i.test(answer)) return "Ошибка в знаке";
        return "Неправильный ответ";
    }

    // Отрисовка графика
    function renderPerformanceChart(results) {
        const ctx = document.getElementById('performanceChart')?.getContext('2d');
        if (!ctx) return;
        
        const tasksStats = calculateTasksStats(results);
        const labels = tasksStats.map(task => `Задание ${task.taskNumber}`);
        const data = tasksStats.map(task => task.correctPercent);
        const colors = tasksStats.map(task => 
            task.correctPercent < 50 ? '#ff6b6b' :
            task.correctPercent < 80 ? '#ffd166' : '#06d6a0'
        );

        if (chart) chart.destroy();
        
        chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: '% правильных ответов',
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.parsed.y}% правильных ответов`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: (value) => `${value}%`
                        }
                    }
                }
            }
        });
    }

    // Уведомление об ошибке
    function showErrorNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'error-notification';
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }


    document.getElementById('generateClassHomeworkBtn')?.addEventListener('click', function() {
    this.disabled = true;
    this.textContent = 'Генерация...';

    // Собираем ID исключённых заданий (если чекбоксы есть)
    const excludedTasks = Array.from(document.querySelectorAll('.exclude-task:checked'))
        .map(cb => cb.value);

    fetch(`/api/generate_homework_class/${lessonId}`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exclude: excludedTasks })
    })
        .then(response => {
            if (response.ok) {
                return response.blob();
            }
            throw new Error('Ошибка генерации');
        })
        .then(blob => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Домашнее_задание_класс_${lessonId}.pdf`;
            a.click();
        })
        .catch(error => {
            showErrorNotification(error.message);
        })
        .finally(() => {
            this.disabled = false;
            this.textContent = '📘 Создать ДЗ для класса';
        });
});


    // Генерация отчета
    document.getElementById('generateReportBtn')?.addEventListener('click', function() {
        this.disabled = true;
        this.textContent = 'Генерация...';
        
        fetch(`/teacher/generate_lesson_report/${lessonId}`)
            .then(response => {
                if (response.ok) {
                    return response.blob();
                }
                throw new Error('Ошибка генерации');
            })
            .then(blob => {
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `Отчет_Урок_${lessonId}.pdf`;
                a.click();
            })
            .catch(error => {
                showErrorNotification(error.message);
            })
            .finally(() => {
                this.disabled = false;
                this.textContent = '📄 Сгенерировать отчет (PDF)';
            });
    });

    // Инициализация
    updateAllData();
    document.getElementById('refreshResults').addEventListener('click', updateAllData);
    document.getElementById('endLesson').addEventListener('click', confirmEndLesson);
    
    // Автообновление каждые 10 секунд
    const updateInterval = setInterval(updateAllData, 10000);

    // Подтверждение завершения урока
    function confirmEndLesson() {
        if (confirm('Завершить урок? Ученики больше не смогут отвечать.')) {
            clearInterval(updateInterval);
            fetch(`/teacher/end_lesson/${lessonId}`, { method: 'POST' })
                .then(() => window.location.href = '/teacher/dashboard')
                .catch(() => showErrorNotification('Ошибка завершения урока'));
        }
    }

    // Чистка при закрытии страницы
    window.addEventListener('beforeunload', () => {
        clearInterval(updateInterval);
    });

    // Генерация ДЗ для конкретного ученика
document.querySelectorAll('.btn-generate-homework').forEach(button => {
    button.addEventListener('click', async () => {
        const studentId = button.dataset.studentId;
        const lessonId = window.location.pathname.split('/').pop();

        button.disabled = true;
        button.textContent = '⏳ Генерация...';

        try {
            const response = await fetch(`/api/generate_homework/${lessonId}/${studentId}`, {
                method: 'POST'
            });

            const data = await response.json();

            if (data.url) {
                window.open(data.url, '_blank');
            } else {
                alert(data.text || 'Не удалось сгенерировать ДЗ');
            }
        } catch (e) {
            alert('Ошибка при генерации ДЗ');
            console.error(e);
        } finally {
            button.disabled = false;
            button.textContent = '📘 ДЗ';
        }
    });
});

});
