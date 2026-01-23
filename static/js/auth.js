window.addEventListener('load', () => {
    const overlay = document.getElementById('intro-overlay');
    const fade = document.querySelector('.intro-fade');
    const auth = document.querySelector('.auth-container');

    let closed = false;

    function closeIntro() {
        if (closed) return;
        closed = true;

        // Плавное затемнение
        fade.style.opacity = '1';

        setTimeout(() => {
            overlay.remove();
            auth.classList.add('visible');
        }, 1000);
    }

    // ⏱ Автозакрытие через 5 секунд
    setTimeout(closeIntro, 5000);

    // 🖱 Клик / тап
    overlay.addEventListener('click', closeIntro);

    // ⌨ Любая клавиша
    document.addEventListener('keydown', closeIntro);
});
