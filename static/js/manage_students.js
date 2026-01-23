document.addEventListener('DOMContentLoaded', function() {
    const classSelect = document.getElementById('classSelect');
    const showStudentsBtn = document.getElementById('showStudentsBtn');
    const studentsTable = document.getElementById('studentsTable').querySelector('tbody');
    const currentClassSpan = document.getElementById('currentClass');
    const addStudentBtn = document.getElementById('addStudentBtn');

    // Загрузка списка учеников
    function loadStudents(classId) {
        fetch(`/teacher/get_students?class_id=${classId}`)
            .then(response => response.json())
            .then(data => {
                studentsTable.innerHTML = '';
                data.students.forEach(student => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${student.id}</td>
                        <td>${student.full_name}</td>
                        <td>${student.username}</td>
                        <td>
                            <select class="grade-select" data-id="${student.id}">
                                <option value="">-</option>
                                ${[5, 4, 3, 2].map(g => `<option value="${g}" ${student.grade == g ? 'selected' : ''}>${g}</option>`).join('')}
                            </select>
                        </td>
                        <td>
                            <button class="btn btn-danger btn-sm delete-student" data-id="${student.id}">Удалить</button>
                        </td>
                    `;
                    studentsTable.appendChild(row);
                });
                
                // Установка текущего класса
                const selectedOption = classSelect.options[classSelect.selectedIndex];
                currentClassSpan.textContent = selectedOption.text;
            });
    }

    // Показать учеников выбранного класса
    showStudentsBtn.addEventListener('click', function() {
        loadStudents(classSelect.value);
    });

    // Добавление нового ученика
    addStudentBtn.addEventListener('click', function() {
        const name = document.getElementById('newStudentName').value.trim();
        const login = document.getElementById('newStudentLogin').value.trim();
        const password = document.getElementById('newStudentPassword').value.trim();
        const classId = classSelect.value;

        if (!name || !login || !password) {
            alert('Заполните все поля');
            return;
        }

        fetch('/teacher/add_student', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                full_name: name,
                username: login,
                password: password,
                class_id: classId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadStudents(classId);
                document.getElementById('newStudentName').value = '';
                document.getElementById('newStudentLogin').value = '';
                document.getElementById('newStudentPassword').value = '';
            } else {
                alert(data.error || 'Ошибка добавления');
            }
        });
    });

    // Удаление ученика
    studentsTable.addEventListener('click', function(e) {
        if (e.target.classList.contains('delete-student')) {
            if (confirm('Удалить этого ученика?')) {
                const studentId = e.target.dataset.id;
                fetch(`/teacher/delete_student/${studentId}`, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        loadStudents(classSelect.value);
                    } else {
                        alert(data.error || 'Ошибка удаления');
                    }
                });
            }
        }
    });

    studentsTable.addEventListener('change', function(e) {
    if (e.target.classList.contains('grade-select')) {
        const studentId = e.target.dataset.id;
        const grade = parseInt(e.target.value);

        if (![2, 3, 4, 5].includes(grade)) return;

        fetch('/teacher/set_grade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ student_id: studentId, grade: grade })
        })
        .then(res => res.json())
        .then(data => {
            if (!data.success) alert(data.error || 'Ошибка при сохранении оценки');
        });
    }
});

    // Загрузить учеников первого класса по умолчанию
    if (classSelect.options.length > 0) {
        loadStudents(classSelect.value);
    }
});