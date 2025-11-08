document.getElementById('duelForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const payload = {
        name: document.getElementById('duelName').value,
        subject: document.getElementById('duelSubject').value,
        teacher_id: parseInt(document.getElementById('teacherId').value)
    };

    const res = await fetch('/duel/api/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });

    const data = await res.json();
    document.getElementById('duelResult').innerText = JSON.stringify(data, null, 2);
});
