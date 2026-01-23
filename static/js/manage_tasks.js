document.addEventListener('DOMContentLoaded', function() {
    const addTextbookBtn = document.getElementById('addTextbookBtn');
    const addTextbookForm = document.getElementById('addTextbookForm');
    const saveTextbookBtn = document.getElementById('saveTextbookBtn');
    const cancelTextbookBtn = document.getElementById('cancelTextbookBtn');
    
    // Показать/скрыть форму добавления
    addTextbookBtn.addEventListener('click', function() {
        addTextbookForm.classList.remove('hidden');
        addTextbookBtn.classList.add('hidden');
    });
    
    cancelTextbookBtn.addEventListener('click', function() {
        addTextbookForm.classList.add('hidden');
        addTextbookBtn.classList.remove('hidden');
    });
    
    // Сохранение нового учебника
    saveTextbookBtn.addEventListener('click', function() {
        const title = document.getElementById('textbookTitle').value.trim();
        const description = document.getElementById('textbookDescription').value.trim();
        const grade = document.getElementById('textbookGrade').value;
        
        if (!title) {
            alert('Введите название учебника');
            return;
        }
        
        fetch('/teacher/add_textbook', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title: title,
                description: description,
                grade: grade
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.reload();
            } else {
                alert(data.error || 'Ошибка при сохранении учебника');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Ошибка при сохранении учебника');
        });
    });
});