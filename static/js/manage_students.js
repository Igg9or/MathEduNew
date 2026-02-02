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
  const unseatedList = document.getElementById('unseatedList');

  let students = [];
  let seating = {};
  let draggedStudentId = null;

  /* =========================
     ОЦЕНКА
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

  function updateStudent(data) {
    return fetch('/teacher/update_student', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
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
     ТАБЛИЦА (VIEW / EDIT)
     ========================= */
  function renderStudentsTable() {
    studentsTable.innerHTML = '';

    students.forEach(st => {
      const tr = document.createElement('tr');

      if (!st._editing) {
        tr.innerHTML = `
          <td>${st.id}</td>
          <td>${st.full_name}</td>
          <td>${st.username}</td>
          <td>
            <select class="grade-select" data-id="${st.id}">
              <option value="">-</option>
              ${[5,4,3,2].map(g =>
                `<option value="${g}" ${st.grade==g?'selected':''}>${g}</option>`
              ).join('')}
            </select>
          </td>
          <td>
            <button class="btn btn-secondary btn-sm edit-student" data-id="${st.id}">
              ✏️
            </button>
            <button class="btn btn-danger btn-sm delete-student" data-id="${st.id}">
              🗑
            </button>
          </td>
        `;
      } else {
        tr.innerHTML = `
          <td>${st.id}</td>
          <td>
            <input class="edit-full-name" value="${st.full_name}">
          </td>
          <td>
            <input class="edit-username" value="${st.username}">
          </td>
          <td>
            <input class="edit-password" type="password" placeholder="Новый пароль">
          </td>
          <td>
            <button class="btn btn-success btn-sm save-student" data-id="${st.id}">
              💾
            </button>
            <button class="btn btn-light btn-sm cancel-edit" data-id="${st.id}">
              ✖
            </button>
          </td>
        `;
      }

      studentsTable.appendChild(tr);
    });
  }

  /* =========================
     НЕРAССАЖЕННЫЕ
     ========================= */
  function renderUnseated() {
    if (!unseatedList) return;
    unseatedList.innerHTML = '';

    students.forEach(st => {
      if (seating[String(st.id)]) return;

      const chip = document.createElement('div');
      chip.className = 'student-chip';
      chip.textContent = st.full_name;
      chip.draggable = true;

      chip.addEventListener('dragstart', () => {
        draggedStudentId = st.id;
      });

      unseatedList.appendChild(chip);
    });
  }

  /* =========================
     КЛАСС (без изменений)
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

          seat.addEventListener('dragover', e => e.preventDefault());

          seat.addEventListener('drop', async () => {
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

            draggedStudentId = null;
            renderStudentsTable();
            renderClassroom();
            renderUnseated();
          });

          inner.appendChild(seat);
        }

        deskEl.appendChild(inner);
        colEl.appendChild(deskEl);
      }
    });

    students.forEach(st => {
      const pos = seating[String(st.id)];
      if (!pos) return;

      const desk = Math.floor(pos.seat_col / 2);
      const side = pos.seat_col % 2;
      const col = pos.seat_row;

      const seat = document.querySelector(
        `.classroom-column[data-col="${col}"] .desk:nth-child(${desk + 2}) .seat:nth-child(${side + 1})`
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
     СОБЫТИЯ ТАБЛИЦЫ
     ========================= */
  studentsTable.addEventListener('click', e => {
    const id = e.target.dataset.id;
    const st = studentById(id);
    if (!st) return;

    if (e.target.classList.contains('edit-student')) {
      students.forEach(s => s._editing = false);
      st._editing = true;
      renderStudentsTable();
    }

    if (e.target.classList.contains('cancel-edit')) {
      st._editing = false;
      renderStudentsTable();
    }

    if (e.target.classList.contains('save-student')) {
      const row = e.target.closest('tr');
      const fullName = row.querySelector('.edit-full-name').value.trim();
      const username = row.querySelector('.edit-username').value.trim();
      const password = row.querySelector('.edit-password').value.trim();

      if (!fullName || !username) {
        alert('ФИО и логин обязательны');
        return;
      }

      updateStudent({
        student_id: id,
        full_name: fullName,
        username,
        password
      }).then(() => {
        st.full_name = fullName;
        st.username = username;
        st._editing = false;
        renderStudentsTable();
        renderClassroom();
      });
    }

    if (e.target.classList.contains('delete-student')) {
      if (!confirm('Удалить ученика?')) return;
      fetch(`/teacher/delete_student/${id}`, { method: 'DELETE' })
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

  /* =========================
     ЗАГРУЗКА
     ========================= */
  function loadStudents(classId) {
    fetch(`/teacher/get_students?class_id=${classId}`)
      .then(r => r.json())
      .then(async data => {
        students = (data.students || []).map(s => ({ ...s, _editing: false }));
        renderStudentsTable();
        currentClassSpan.textContent =
          classSelect.options[classSelect.selectedIndex].text;

        await loadSeatingFromServer(classId);
        renderClassroom();
        renderUnseated();
      });
  }

  showStudentsBtn.addEventListener('click', () => loadStudents(classSelect.value));
  rowsCountInput.addEventListener('change', renderClassroom);

  autoSeatBtn.addEventListener('click', async () => {
    const desksCount = Math.max(1, Math.min(10, parseInt(rowsCountInput.value || '7', 10)));
    seating = {};
    let i = 0;

    for (let desk = 0; desk < desksCount; desk++) {
      for (let col = 0; col < 3; col++) {
        for (let side = 0; side < 2; side++) {
          if (i >= students.length) break;
          seating[String(students[i].id)] = {
            seat_row: col,
            seat_col: desk * 2 + side
          };
          i++;
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
    renderUnseated();
  });

  clearSeatingBtn.addEventListener('click', async () => {
    seating = {};
    await saveSeatingToServer(classSelect.value);
    renderClassroom();
    renderUnseated();
  });

  if (classSelect.options.length > 0) {
    loadStudents(classSelect.value);
  }
});
