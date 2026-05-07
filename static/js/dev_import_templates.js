document.addEventListener('DOMContentLoaded', function () {
  const container = document.getElementById('templatesContainer');

  if (!container) return;

  /* ================================
     ФОТО: загрузка / замена / удаление
  ================================= */
  container.addEventListener('click', (e) => {
    const card = e.target.closest('.template-card');
    if (!card) return;
    const templateId = card.dataset.templateId;

    // Прикрепить / Заменить фото
    if (e.target.closest('.btn-attach-photo') || e.target.closest('.btn-replace-photo')) {
      const fileInput = card.querySelector('.template-photo-input');
      fileInput?.click();
    }

    // Удалить фото
    if (e.target.closest('.btn-remove-photo')) {
      if (!templateId) return;
      if (!confirm('Удалить фото из этого шаблона?')) return;

      const btn = e.target.closest('.btn-remove-photo');
      const originalText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Удаляю…';

      fetch(`/api/templates/${templateId}/photo`, { method: 'DELETE' })
        .then(r => r.json())
        .then(d => {
          if (d.success) {
            clearPhotoUI(card);
          } else {
            alert('Ошибка удаления фото: ' + (d.error || ''));
          }
        })
        .catch(() => alert('Ошибка сети при удалении фото'))
        .finally(() => {
          btn.disabled = false;
          btn.innerHTML = originalText;
        });
    }
  });

  // Обработка выбора файла
  container.addEventListener('change', (e) => {
    if (!e.target.classList.contains('template-photo-input')) return;
    const card = e.target.closest('.template-card');
    const templateId = card.dataset.templateId;
    const file = e.target.files[0];
    if (!file) return;

    if (!templateId) {
      alert('Ошибка: ID шаблона не найден');
      return;
    }

    const formData = new FormData();
    formData.append('photo', file);

    // Находим блок кнопок и показываем спиннер
    const actions = card.querySelector('.photo-actions');
    const oldHtml = actions.innerHTML;
    actions.innerHTML = '<span style="padding: 8px 14px; font-size: 13px; color: var(--text-muted);"><i class="fas fa-spinner fa-spin"></i> Загрузка...</span>';

    fetch(`/api/templates/${templateId}/photo`, {
      method: 'POST',
      body: formData
    })
      .then(r => r.json())
      .then(d => {
        if (d.success) {
          setPhotoUI(card, d.path);
          card.dataset.photoPath = d.path;
          // Скрываем текст задания — при фото остаётся только фотография
          const textBlock = card.querySelector('.template-text-block');
          if (textBlock) textBlock.style.display = 'none';
        } else {
          alert('Ошибка загрузки: ' + (d.error || 'Неизвестная ошибка'));
          actions.innerHTML = oldHtml;
        }
      })
      .catch(() => {
        alert('Ошибка сети при загрузке фото');
        actions.innerHTML = oldHtml;
      });
  });

  function clearPhotoUI(card) {
    card.dataset.photoPath = '';
    const photoDiv = card.querySelector('.template-photo');
    if (photoDiv) photoDiv.remove();

    const actions = card.querySelector('.photo-actions');
    actions.innerHTML = `
      <button type="button" class="btn-photo attach btn-attach-photo">
        <i class="fas fa-camera"></i> Загрузить фото
      </button>
      <input type="file" class="template-photo-input hidden" accept="image/*">
    `;

    const textBlock = card.querySelector('.template-text-block');
    if (textBlock) textBlock.style.display = '';
  }

  function setPhotoUI(card, path) {
    const body = card.querySelector('.template-body');

    // Удаляем старый фото-блок, если есть
    const oldPhoto = body.querySelector('.template-photo');
    if (oldPhoto) oldPhoto.remove();

    // Вставляем фото в начало body
    const photoDiv = document.createElement('div');
    photoDiv.className = 'template-photo';
    photoDiv.innerHTML = `<img src="${path}" alt="Фото задания" onclick="window.open('${path}','_blank')">`;
    if (body.children.length > 0) {
      body.insertBefore(photoDiv, body.children[0]);
    } else {
      body.appendChild(photoDiv);
    }

    const actions = card.querySelector('.photo-actions');
    actions.innerHTML = `
      <button type="button" class="btn-photo replace btn-replace-photo">
        <i class="fas fa-sync-alt"></i> Заменить фото
      </button>
      <button type="button" class="btn-photo remove btn-remove-photo">
        <i class="fas fa-trash"></i> Удалить фото
      </button>
      <input type="file" class="template-photo-input hidden" accept="image/*">
    `;
  }

  /* ================================
     ИНИЦИАЛИЗАЦИЯ MathJax
  ================================= */
  /* ================================
     КНОПКА "СОХРАНИТЬ ИЗМЕНЕНИЯ"
  ================================= */
  const btnSave = document.getElementById('btnSaveTemplates');
  if (btnSave) {
    btnSave.addEventListener('click', () => {
      btnSave.disabled = true;
      btnSave.innerHTML = '<i class="fas fa-check-circle"></i> Сохранено!';
      btnSave.style.background = 'var(--success)';

      setTimeout(() => {
        btnSave.disabled = false;
        btnSave.innerHTML = '<i class="fas fa-save"></i> Сохранить изменения';
        btnSave.style.background = 'var(--primary)';
      }, 2000);
    });
  }

  /* ================================
     ИНИЦИАЛИЗАЦИЯ MathJax
  ================================= */
  if (window.MathJax?.typesetPromise) {
    MathJax.typesetPromise([container]).catch((err) => {
      console.error('MathJax error:', err);
    });
  }
});
