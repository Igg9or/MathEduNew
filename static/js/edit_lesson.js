document.addEventListener('DOMContentLoaded', function () {

  const lessonId = window.location.pathname.split('/').pop();
  const tasksContainer = document.getElementById('tasksContainer');
  const addTaskBtn = document.getElementById('addTaskBtn');
  const saveLessonBtn = document.getElementById('saveLessonBtn');
  const textbookSelect = document.getElementById('textbookSelect');
  const templateSearch = document.getElementById('templateSearch');
  const templatesList = document.getElementById('templatesList');
  const taskIndexList = document.getElementById('taskIndexList');
  const taskIndexCount = document.getElementById('taskIndexCount');

  const templatesCache = {};

  /* ================================
     ПРЕВЬЮ ЗАДАНИЯ (ГЛАВНОЕ)
  ================================= */

  function renderTaskPreview(taskCard) {
    const textarea = taskCard.querySelector('.task-question');
    const preview = taskCard.querySelector('.task-question-preview');
    if (!textarea || !preview) return;

    const html = (textarea.value || '').trim();
    preview.innerHTML = html || '<em style="color:#999">Нет текста задания</em>';

    if (window.MathJax?.typesetPromise) {
      MathJax.typesetPromise([preview]);
    }
  }

  function syncPreviewToTextarea() {
    document.querySelectorAll('.task-card').forEach(card => {
      const textarea = card.querySelector('.task-question');
      const preview = card.querySelector('.task-question-preview');
      if (!textarea || !preview) return;

      const html = (preview.innerHTML || '').trim();
      if (html) textarea.value = html;
    });
  }

  /* ================================
     ПРАВЫЙ САЙДБАР (ИНДЕКС)
  ================================= */

  function renderTaskIndex() {
  if (!taskIndexList) return;

  const cards = Array.from(document.querySelectorAll('.task-card'));
  taskIndexList.innerHTML = '';

  cards.forEach((card, idx) => {
    const number = idx + 1;
    const templateName = card.dataset.templateName || '—';

    const li = document.createElement('li');
    li.className = 'task-index-item';

    li.innerHTML = `
      <div class="task-index-row">
        <input 
          type="number"
          class="task-order-input"
          min="1"
          max="${cards.length}"
          value="${number}"
          data-task-id="${card.dataset.taskId || ''}"
        />
        <span class="task-index-label">
          № ${number} — ${templateName}
        </span>
      </div>
    `;

    // 👉 переход к заданию
    li.querySelector('.task-index-label').onclick = () => {
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    // 👉 изменение порядка
    li.querySelector('.task-order-input').addEventListener('change', (e) => {
      const newPos = parseInt(e.target.value, 10);
      reorderTask(card, newPos);
    });

    taskIndexList.appendChild(li);
  });

  if (taskIndexCount) taskIndexCount.textContent = cards.length;
}


  /* ================================
     ШАБЛОНЫ
  ================================= */

  textbookSelect?.addEventListener('change', loadTemplates);
  templateSearch?.addEventListener('input', filterTemplates);

  function loadTemplates() {
    const textbookId = textbookSelect.value;
    if (!textbookId) {
      templatesList.innerHTML = '<p>Выберите учебник</p>';
      return;
    }

    fetch(`/api/textbooks/${textbookId}/templates`)
      .then(r => r.json())
      .then(d => d.success && renderTemplates(d.templates));
  }

  function filterTemplates() {
    const q = templateSearch.value.toLowerCase();
    templatesList.querySelectorAll('.template-item').forEach(i => {
      i.style.display = i.textContent.toLowerCase().includes(q) ? 'block' : 'none';
    });
  }

  function renderTemplates(templates) {
    templatesList.innerHTML = templates.map(t => `
      <div class="template-item">
        <h4>${t.name}</h4>
        <p>${t.question_template}</p>
        <button class="btn btn-small btn-use-template" data-template-id="${t.id}">
          Добавить
        </button>
      </div>
    `).join('');
  }

  templatesList?.addEventListener('click', e => {
    if (!e.target.classList.contains('btn-use-template')) return;
    addTaskFromTemplate(e.target.dataset.templateId);
  });

  function addTaskFromTemplate(templateId) {
    if (templatesCache[templateId]) {
      processTemplate(templatesCache[templateId]);
      return;
    }

    fetch(`/api/templates/${templateId}`)
      .then(r => r.json())
      .then(d => {
        if (d.success) {
          templatesCache[templateId] = d.template;
          processTemplate(d.template);
        }
      });
  }

function processTemplate(template) {
  addTask('', '');
  const card = tasksContainer.lastElementChild;

  card.dataset.templateId = template.id;
  card.dataset.templateName = template.name;

  // 👇 добавляем имя шаблона в заголовок
  const header = card.querySelector('.task-header h3');
  if (header && template.name) {
    header.insertAdjacentHTML(
      'beforeend',
      `<span class="task-template-name"> — ${template.name}</span>`
    );
  }

  generateFromTemplate(card);
}


  function generateFromTemplate(taskCard) {
    const templateId = taskCard.dataset.templateId;
    if (!templateId) return;

    fetch(`/api/generate_from_template/${templateId}`)
      .then(r => r.json())
      .then(v => {
        const textarea = taskCard.querySelector('.task-question');
        textarea.value = v.question;
        renderTaskPreview(taskCard);
      });
  }

  /* ================================
     ДОБАВЛЕНИЕ / УДАЛЕНИЕ
  ================================= */

  function addTask(question = '', answer = '') {
    const card = document.createElement('div');
    card.className = 'task-card';
    card.innerHTML = `
      <div class="task-header">
        <h3>Задание <span class="task-number"></span></h3>
        <button class="btn btn-danger btn-remove-task">Удалить</button>
      </div>

      <div class="task-question-preview"></div>
      <textarea class="task-question hidden">${question}</textarea>

      <div class="answer-section">
        <label>Формула ответа:</label>
        <textarea class="task-answer">${answer}</textarea>
      </div>
    `;

    tasksContainer.appendChild(card);
    updateTaskNumbers();
    renderTaskPreview(card);
  }

  function updateTaskNumbers() {
    document.querySelectorAll('.task-card').forEach((c, i) => {
      c.querySelector('.task-number').textContent = i + 1;
    });
    renderTaskIndex();
  }

  tasksContainer?.addEventListener('click', async (e) => {
  const btn = e.target.closest('.btn-remove-task');
  if (!btn) return;

  const card = btn.closest('.task-card');
  if (!card) return;

  const taskId = card.dataset.taskId;

  // 🟢 Если задание ещё не сохранено в БД
  if (!taskId) {
    card.remove();
    updateTaskNumbers();
    return;
  }

  if (!confirm('Удалить это задание?')) return;

  btn.disabled = true;
  btn.textContent = 'Удаляю…';

  try {
    const resp = await fetch(`/teacher/delete_task/${taskId}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await resp.json();

    if (!resp.ok || !data.success) {
      throw new Error(data.error || 'Ошибка удаления');
    }

    // ✅ реально удалено в БД
    card.remove();
    updateTaskNumbers();

  } catch (err) {
    alert('Ошибка удаления: ' + err.message);
    btn.disabled = false;
    btn.textContent = 'Удалить';
  }
});

function reorderTask(taskCard, newPosition) {
  const cards = Array.from(document.querySelectorAll('.task-card'));
  const currentIndex = cards.indexOf(taskCard);

  if (currentIndex === -1) return;
  if (newPosition < 1 || newPosition > cards.length) return;

  const targetIndex = newPosition - 1;
  if (currentIndex === targetIndex) return;

  const container = tasksContainer;

  // удаляем и вставляем в нужное место
  container.removeChild(taskCard);

  if (targetIndex >= container.children.length) {
    container.appendChild(taskCard);
  } else {
    container.insertBefore(taskCard, container.children[targetIndex]);
  }

  updateTaskNumbers();   // обновит номера слева
}



  /* ================================
     СОХРАНЕНИЕ
  ================================= */

  saveLessonBtn?.addEventListener('click', () => {

    //syncPreviewToTextarea();

    const tasks = [];
    document.querySelectorAll('.task-card').forEach((card, index) => {
      tasks.push({
  id: card.dataset.taskId || null,
  question: card.querySelector('.task-question').value,
  answer: card.querySelector('.task-answer').value,
  template_id: card.dataset.templateId || null,
  position: index + 1
});

    });

    fetch(`/teacher/update_lesson/${lessonId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tasks })
    })
    .then(r => r.json())
    .then(d => d.success && alert('Изменения сохранены'));
  });

  addTaskBtn?.addEventListener('click', () => {
    addTask();
    updateTaskNumbers();
  });

  /* ================================
     ИНИЦИАЛИЗАЦИЯ
  ================================= */

  document.querySelectorAll('.task-card').forEach(card => {
    renderTaskPreview(card);
  });

  renderTaskIndex();
  document.querySelectorAll('.task-card').forEach(taskCard => {
  renderTeacherStudentView(taskCard);
});

});
