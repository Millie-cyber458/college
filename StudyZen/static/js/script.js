document.addEventListener('DOMContentLoaded', () => {
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.nav-menu');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            navMenu.classList.toggle('is-open');
        });
    }

    const modal = document.getElementById('googleLoginModal');
    const openButtons = document.querySelectorAll('.login-open-btn');
    const closeButtons = document.querySelectorAll('.close-modal, [data-close-modal="true"]');

    const openModal = () => {
        if (modal) {
            modal.classList.remove('hidden');
        }
    };

    const closeModal = () => {
        if (modal) {
            modal.classList.add('hidden');
        }
    };

    openButtons.forEach((button) => {
        button.addEventListener('click', openModal);
    });

    closeButtons.forEach((button) => {
        button.addEventListener('click', closeModal);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal && !modal.classList.contains('hidden')) {
            closeModal();
        }
    });
});
