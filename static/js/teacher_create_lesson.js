document.addEventListener('DOMContentLoaded', function() {
    // Элементы
    const tasksContainer = document.getElementById('tasksContainer');
    const addTaskBtn = document.getElementById('addTaskBtn');
    const saveLessonBtn = document.getElementById('saveLessonBtn');
    const previewLessonBtn = document.getElementById('previewLessonBtn');
    const generateWithAIBtn = document.getElementById('generateWithAI');
    const aiPrompt = document.getElementById('aiPrompt');
    const aiResults = document.getElementById('aiResults');
    const aiTasksList = document.getElementById('aiTasksList');
    const addAiTasksBtn = document.getElementById('addAiTasks');
    const taskTemplate = document.getElementById('taskTemplate');

    // Добавление нового задания
    function addTask(taskText = '') {
        const taskClone = taskTemplate.content.cloneNode(true);
        const taskElement = taskClone.querySelector('.task-card');
        const taskNumber = tasksContainer.children.length + 1;
        
        taskClone.querySelector('.task-number').textContent = taskNumber;
        if (taskText) {
            taskClone.querySelector('.task-text').value = taskText;
        }
        
        // Кнопка удаления
        taskClone.querySelector('.btn-remove-task').addEventListener('click', function() {
            tasksContainer.removeChild(taskElement);
            updateTaskNumbers();
        });
        
        // Превью примеров
        taskClone.querySelector('.btn-preview-task').addEventListener('click', function() {
            const previewDiv = taskElement.querySelector('.task-preview');
            previewDiv.classList.toggle('hidden');
            
            if (!previewDiv.classList.contains('hidden')) {
                generateExamples(taskElement);
            }
        });
        
        tasksContainer.appendChild(taskClone);
    }

    // Обновление нумерации заданий
    function updateTaskNumbers() {
        Array.from(tasksContainer.children).forEach((task, index) => {
            task.querySelector('.task-number').textContent = index + 1;
        });
    }

    // Генерация примеров для задания
    function generateExamples(taskElement) {
        const taskText = taskElement.querySelector('.task-text').value;
        const examplesDiv = taskElement.querySelector('.preview-examples');
        examplesDiv.innerHTML = '';
        
        if (!taskText) return;
        
        // Находим параметры {A}, {B}...
        const params = [...new Set(taskText.match(/\{([A-Z])\}/g))].map(p => p.replace(/\{|\}/g, ''));
        
        // Генерируем 3 примера
        for (let i = 0; i < 3; i++) {
            const example = { ...taskText };
            const values = {};
            
            // Заполняем параметры случайными значениями
            params.forEach(param => {
                values[param] = getRandomInt(1, 10);
                example = example.replace(new RegExp(`\\{${param}\\}`, 'g'), values[param]);
            });
            
            const exampleDiv = document.createElement('div');
            exampleDiv.className = 'example';
            exampleDiv.textContent = example;
            examplesDiv.appendChild(exampleDiv);
        }
    }

    // Генерация через DeepSeek
    generateWithAIBtn.addEventListener('click', async function() {
        if (!aiPrompt.value.trim()) {
            alert('Введите описание заданий');
            return;
        }
        
        generateWithAIBtn.disabled = true;
        generateWithAIBtn.textContent = 'Генерация...';
        
        try {
            const response = await fetch('/teacher/generate_with_ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: aiPrompt.value })
            });
            
            const data = await response.json();
            displayAITasks(data.tasks);
        } catch (error) {
            console.error('AI generation error:', error);
            alert('Ошибка генерации');
        } finally {
            generateWithAIBtn.disabled = false;
            generateWithAIBtn.textContent = 'Сгенерировать задания';
        }
    });

    // Отображение результатов ИИ
    function displayAITasks(tasks) {
        aiTasksList.innerHTML = '';
        tasks.forEach(task => {
            const taskDiv = document.createElement('div');
            taskDiv.className = 'ai-task';
            taskDiv.innerHTML = `
                <input type="checkbox" checked>
                <div class="ai-task-text">${task}</div>
            `;
            aiTasksList.appendChild(taskDiv);
        });
        aiResults.classList.remove('hidden');
    }

    // Добавление выбранных заданий от ИИ
    addAiTasksBtn.addEventListener('click', function() {
        document.querySelectorAll('.ai-task input:checked').forEach(checkbox => {
            const taskText = checkbox.nextElementSibling.textContent;
            addTask(taskText);
        });
        aiResults.classList.add('hidden');
    });

    // Сохранение урока
    saveLessonBtn.addEventListener('click', function() {
        const tasks = [];
        document.querySelectorAll('.task-card').forEach(task => {
            tasks.push({
                text: task.querySelector('.task-text').value,
                params: [...new Set(task.querySelector('.task-text').value.match(/\{([A-Z])\}/g))]
                    .map(p => p.replace(/\{|\}/g, ''))
            });
        });
        
        if (tasks.length === 0) {
            alert('Добавьте хотя бы одно задание');
            return;
        }
        
        fetch('/teacher/save_lesson', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                class_name: '{{ class_name }}',
                tasks: tasks
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = '/teacher/dashboard';
            } else {
                alert('Ошибка сохранения: ' + (data.error || ''));
            }
        });
    });

    // Вспомогательные функции
    function getRandomInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    // Инициализация
    addTaskBtn.addEventListener('click', () => addTask());
    addTask(); // Добавляем первое задание по умолчанию
});