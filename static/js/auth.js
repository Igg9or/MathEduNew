window.addEventListener('load', () => {
    const overlay = document.getElementById('intro-overlay');
    const fade = document.querySelector('.intro-fade');
    const auth = document.querySelector('.auth-container');

    let closed = false;

    function closeIntro() {
        if (closed) return;
        closed = true;

        // Плавное затемнение (если элемент есть)
        if (fade) {
            fade.style.opacity = '1';
        }

        setTimeout(() => {
            if (overlay) overlay.remove();
            if (auth) auth.classList.add('visible');
        }, fade ? 1000 : 300); // Если нет fade, закрываем быстрее
    }

    // Автозакрытие через 5 секунд
    setTimeout(closeIntro, 5000);

    // Клик / тап
    if (overlay) {
        overlay.addEventListener('click', closeIntro);
    }

    // Любая клавиша
    document.addEventListener('keydown', closeIntro);
});