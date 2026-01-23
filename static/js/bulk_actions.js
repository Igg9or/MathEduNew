document.addEventListener('DOMContentLoaded', function() {
    const textbookId = document.querySelector('.textbook-tasks-container').dataset.textbookId;
    const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
    const selectAllBtn = document.getElementById('selectAllBtn');
    const checkboxes = document.querySelectorAll('.template-checkbox');
    
    // Обработчик выбора шаблонов
    function updateDeleteButton() {
        const selected = document.querySelectorAll('.template-checkbox:checked');
        deleteSelectedBtn.disabled = selected.length === 0;
        deleteSelectedBtn.textContent = selected.length > 0 ? 
            `Удалить выбранные (${selected.length})` : 'Удалить выбранные';
    }
    
    // Выбрать все/снять выделение
    selectAllBtn.addEventListener('click', function() {
        const allChecked = document.querySelectorAll('.template-checkbox:checked').length === checkboxes.length;
        checkboxes.forEach(checkbox => {
            checkbox.checked = !allChecked;
        });
        updateDeleteButton();
    });
    
    // Обработчики для чекбоксов
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateDeleteButton);
    });
    
    // Массовое удаление
    deleteSelectedBtn.addEventListener('click', function() {
        const selectedIds = Array.from(document.querySelectorAll('.template-checkbox:checked'))
            .map(checkbox => parseInt(checkbox.dataset.id));
        
        if (!selectedIds.length) return;
        
        if (confirm(`Вы уверены, что хотите удалить ${selectedIds.length} шаблонов?`)) {
            fetch('/teacher/bulk_delete_templates', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    textbook_id: textbookId,
                    template_ids: selectedIds
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(`Удалено ${data.deleted_count} шаблонов`);
                    window.location.reload();
                } else {
                    alert('Ошибка удаления: ' + (data.error || ''));
                }
            });
        }
    });
});