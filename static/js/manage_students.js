document.addEventListener('DOMContentLoaded', function () {
  const classSelect = document.getElementById('classSelect');
  const showStudentsBtn = document.getElementById('showStudentsBtn');
  const studentsTable = document.getElementById('studentsTable').querySelector('tbody');
  const currentClassSpan = document.getElementById('currentClass');
  const addStudentBtn = document.getElementById('addStudentBtn');

  const classroom = document.getElementById('classroom');
  const rowsCountInput = document.getElementById('rowsCount');
  const autoSeatBtn = document.getElementById('autoSeatBtn');
  const clearSeatingBtn = document.getElementById('clearSeatingBtn');

  let students = [];
  let seating = {};
  let draggedStudentId = null;

  /* =========================
     ОЦЕНКА ПО ПАРТЕ
     ========================= */
  function computeGrade(deskIndex, seatSide) {
    const base = deskIndex % 2 === 0 ? 2 : 4;
    return seatSide === 0 ? base : base + 1;
  }

  function studentById(id) {
    return students.find(s => String(s.id) === String(id));
  }

  function setGrade(studentId, grade) {
    return fetch('/teacher/set_grade', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_id: studentId, grade })
    }).then(r => r.json());
  }

  function saveSeatingToServer(classId) {
    const seats = Object.entries(seating).map(([studentId, pos]) => ({
      student_id: studentId,
      seat_row: pos.seat_row,
      seat_col: pos.seat_col
    }));

    return fetch('/teacher/save_seating', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ class_id: classId, seats })
    }).then(r => r.json());
  }

  function loadSeatingFromServer(classId) {
    return fetch(`/teacher/get_seating?class_id=${classId}`)
      .then(r => r.json())
      .then(data => {
        seating = {};
        (data.seats || []).forEach(s => {
          seating[String(s.student_id)] = {
            seat_row: s.seat_row,
            seat_col: s.seat_col
          };
        });
      });
  }

  /* =========================
     ТАБЛИЦА УЧЕНИКОВ
     ========================= */
  function renderStudentsTable() {
    studentsTable.innerHTML = '';
    students.forEach(st => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${st.id}</td>
        <td>${st.full_name}</td>
        <td>${st.username}</td>
        <td>
          <select class="grade-select" data-id="${st.id}">
            <option value="">-</option>
            ${[5,4,3,2].map(g => `<option value="${g}" ${st.grade==g?'selected':''}>${g}</option>`).join('')}
          </select>
        </td>
        <td>
          <button class="btn btn-danger btn-sm delete-student" data-id="${st.id}">Удалить</button>
        </td>
      `;
      studentsTable.appendChild(tr);
    });
  }

  /* =========================
     КЛАСС (3 РЯДА)
     ========================= */
  function renderClassroom() {
    if (!classroom) return;

    const desksCount = Math.max(1, Math.min(10, parseInt(rowsCountInput.value || '7', 10)));

    classroom.querySelectorAll('.desk').forEach(d => d.remove());

    document.querySelectorAll('.classroom-column').forEach(colEl => {
      const colIndex = parseInt(colEl.dataset.col, 10);

      for (let desk = 0; desk < desksCount; desk++) {
        const deskEl = document.createElement('div');
        deskEl.className = 'desk';

        const inner = document.createElement('div');
        inner.className = 'desk-inner';

        for (let side = 0; side < 2; side++) {
          const seat = document.createElement('div');
          seat.className = 'seat';
          seat.dataset.col = colIndex;
          seat.dataset.desk = desk;
          seat.dataset.side = side;

          seat.addEventListener('dragover', e => {
            e.preventDefault();
            seat.classList.add('drag-over');
          });

          seat.addEventListener('dragleave', () => {
            seat.classList.remove('drag-over');
          });

          seat.addEventListener('drop', async e => {
            e.preventDefault();
            seat.classList.remove('drag-over');
            if (!draggedStudentId) return;

            seating[String(draggedStudentId)] = {
              seat_row: colIndex,
              seat_col: desk * 2 + side
            };

            const grade = computeGrade(desk, side);
            const st = studentById(draggedStudentId);
            if (st) st.grade = grade;

            await setGrade(draggedStudentId, grade);
            await saveSeatingToServer(classSelect.value);

            renderStudentsTable();
            renderClassroom();
            draggedStudentId = null;
          });

          inner.appendChild(seat);
        }

        deskEl.appendChild(inner);
        colEl.appendChild(deskEl);
      }
    });

    // размещение учеников
    students.forEach(st => {
      const pos = seating[String(st.id)];
      if (!pos) return;

      const desk = Math.floor(pos.seat_col / 2);
      const side = pos.seat_col % 2;
      const col = pos.seat_row;

      const seat = document.querySelector(
        `.seat[data-col="${col}"][data-desk="${desk}"][data-side="${side}"]`
      );
      if (!seat) return;

      const chip = document.createElement('div');
      chip.className = `student-chip grade-${st.grade}`;
      chip.textContent = `${st.full_name} (${st.grade})`;
      chip.draggable = true;

      chip.addEventListener('dragstart', () => {
        draggedStudentId = st.id;
      });

      seat.appendChild(chip);
    });
  }

  /* =========================
     ЗАГРУЗКА КЛАССА
     ========================= */
  function loadStudents(classId) {
    fetch(`/teacher/get_students?class_id=${classId}`)
      .then(r => r.json())
      .then(async data => {
        students = data.students || [];
        renderStudentsTable();

        currentClassSpan.textContent =
          classSelect.options[classSelect.selectedIndex].text;

        await loadSeatingFromServer(classId);
        renderClassroom();
      });
  }

  /* =========================
     КНОПКИ
     ========================= */
  showStudentsBtn.addEventListener('click', () => {
    loadStudents(classSelect.value);
  });

  rowsCountInput.addEventListener('change', renderClassroom);

  autoSeatBtn.addEventListener('click', async () => {
    const desksCount = Math.max(1, Math.min(10, parseInt(rowsCountInput.value || '7', 10)));

    const sorted = [...students].sort((a, b) =>
      (a.full_name || '').localeCompare(b.full_name || '', 'ru')
    );

    seating = {};
    let index = 0;

    for (let desk = 0; desk < desksCount; desk++) {
      for (let col = 0; col < 3; col++) {
        for (let side = 0; side < 2; side++) {
          if (index >= sorted.length) break;

          const st = sorted[index++];
          seating[String(st.id)] = {
            seat_row: col,
            seat_col: desk * 2 + side
          };
        }
      }
    }

    for (const st of students) {
      const pos = seating[String(st.id)];
      if (!pos) continue;

      const desk = Math.floor(pos.seat_col / 2);
      const side = pos.seat_col % 2;

      const grade = computeGrade(desk, side);
      st.grade = grade;
      await setGrade(st.id, grade);
    }

    await saveSeatingToServer(classSelect.value);
    renderStudentsTable();
    renderClassroom();
  });

  clearSeatingBtn.addEventListener('click', async () => {
    seating = {};
    await saveSeatingToServer(classSelect.value);
    renderClassroom();
  });

  /* =========================
     ДОБАВЛЕНИЕ / УДАЛЕНИЕ
     ========================= */
  addStudentBtn.addEventListener('click', () => {
    const name = document.getElementById('newStudentName').value.trim();
    const login = document.getElementById('newStudentLogin').value.trim();
    const password = document.getElementById('newStudentPassword').value.trim();

    if (!name || !login || !password) {
      alert('Заполните все поля');
      return;
    }

    fetch('/teacher/add_student', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        full_name: name,
        username: login,
        password,
        class_id: classSelect.value
      })
    }).then(() => loadStudents(classSelect.value));
  });

  studentsTable.addEventListener('click', e => {
    if (e.target.classList.contains('delete-student')) {
      if (!confirm('Удалить ученика?')) return;
      fetch(`/teacher/delete_student/${e.target.dataset.id}`, { method: 'DELETE' })
        .then(() => loadStudents(classSelect.value));
    }
  });

  studentsTable.addEventListener('change', e => {
    if (!e.target.classList.contains('grade-select')) return;
    const studentId = e.target.dataset.id;
    const grade = parseInt(e.target.value);
    if (![2,3,4,5].includes(grade)) return;

    setGrade(studentId, grade).then(() => {
      const st = studentById(studentId);
      if (st) st.grade = grade;
      renderClassroom();
    });
  });

  if (classSelect.options.length > 0) {
    loadStudents(classSelect.value);
  }
});
