document.addEventListener('DOMContentLoaded', function() {
    // Элементы интерфейса
    const gradeButtons = document.querySelectorAll('.btn-grade');
    const letterButtons = document.querySelector('.letter-buttons');
    const createBtn = document.getElementById('createNewLesson');
    const modal = document.getElementById('lessonModal');
    const closeBtn = document.querySelector('.close');
    const saveLessonBtn = document.getElementById('saveLesson');
    
    let selectedGrade = null;
    let selectedLetter = null;

    // 1. Выбор класса (5-11)
    gradeButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            gradeButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            selectedGrade = this.dataset.grade;
            letterButtons.classList.remove('hidden');
            createBtn.classList.add('hidden');
        });
    });

    // 2. Выбор буквы класса (А-Д)
    document.querySelectorAll('.btn-letter').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.btn-letter').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            selectedLetter = this.dataset.letter;
            createBtn.classList.remove('hidden');
            loadLessons(selectedGrade, selectedLetter);
        });
    });

    // 3. Открытие модального окна
    createBtn.addEventListener('click', function() {
        // Устанавливаем сегодняшнюю дату по умолчанию
        document.getElementById('lessonDate').value = new Date().toISOString().split('T')[0];
        modal.classList.remove('hidden');
    });

    // 4. Закрытие модального окна
    function closeModal() {
        modal.classList.add('hidden');
    }
    
    closeBtn.addEventListener('click', closeModal);
    window.addEventListener('click', function(event) {
        if (event.target === modal) {
            closeModal();
        }
    });

    // 5. Сохранение урока
    saveLessonBtn.addEventListener('click', async function() {
        const title = document.getElementById('lessonTitle').value.trim();
        const date = document.getElementById('lessonDate').value;
        
        if (!title) {
            alert('Введите название урока');
            return;
        }

        try {
            const response = await fetch('/teacher/create_lesson', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    grade: `${selectedGrade}${selectedLetter}`,
                    title: title,
                    date: date
                })
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Ошибка сервера');
            }

            if (data.success && data.lesson_id) {
                // Перенаправляем на страницу редактирования
                window.location.href = `/teacher/edit_lesson/${data.lesson_id}`;
            } else {
                throw new Error('Не удалось создать урок');
            }
        } catch (error) {
            console.error('Error:', error);
            alert(`Ошибка создания урока: ${error.message}`);
        }
    });

    // Функция для загрузки уроков класса
    async function loadLessons(grade, letter) {
        try {
            const response = await fetch(`/teacher/get_lessons?grade=${grade}${letter}`);
            const data = await response.json();
            
            if (response.status !== 200) {
                throw new Error(data.error || 'Ошибка загрузки уроков');
            }
            
            const container = document.querySelector('.lessons-container');
            container.innerHTML = '';
            
            if (!data.lessons || data.lessons.length === 0) {
                container.innerHTML = '<p>Нет созданных уроков</p>';
                return;
            }
            
            data.lessons.forEach(lesson => {
                const lessonElement = document.createElement('div');
                lessonElement.className = 'lesson-card';
                lessonElement.innerHTML = `
                    <div class="lesson-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2L1 12h3v9h6v-6h4v6h6v-9h3L12 2zm0 2.8L18 10v9h-2v-6H8v6H6v-9l6-7.2z"/>
                        </svg>
                    </div>
                    <div class="lesson-info">
                        <h4>${lesson.title}</h4>
                        <p>${lesson.date}</p>
                    </div>
                    <div class="lesson-actions">
                        <a href="/teacher/conduct_lesson/${lesson.id}" class="btn btn-small">Войти в урок</a>
                        <a href="/teacher/edit_lesson/${lesson.id}" class="btn btn-small btn-secondary">Редактировать</a>
                    </div>
                `;
                container.appendChild(lessonElement);
            });
            
            document.querySelector('.lessons-list').classList.remove('hidden');
        } catch (error) {
            console.error('Error loading lessons:', error);
            alert(`Ошибка загрузки уроков: ${error.message}`);
        }
    }
});