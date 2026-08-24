/**
 * SplitStack - Core JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Mobile Navbar Toggle
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            navMenu.classList.toggle('open');
        });
    }

    // 2. Password Visibility Toggle for Login
    const togglePasswordBtn = document.getElementById('togglePasswordBtn');
    const passwordInput = document.getElementById('password');
    const togglePasswordIcon = document.getElementById('togglePasswordIcon');

    if (togglePasswordBtn && passwordInput && togglePasswordIcon) {
        togglePasswordBtn.addEventListener('click', () => {
            const isPassword = passwordInput.getAttribute('type') === 'password';
            passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
            togglePasswordIcon.classList.toggle('fa-eye', !isPassword);
            togglePasswordIcon.classList.toggle('fa-eye-slash', isPassword);
        });
    }

    // 3. Password Visibility Toggle for Register
    const toggleRegPasswordBtn = document.getElementById('toggleRegPasswordBtn');
    const regPasswordInput = document.getElementById('password');
    const toggleRegPasswordIcon = document.getElementById('toggleRegPasswordIcon');

    if (toggleRegPasswordBtn && regPasswordInput && toggleRegPasswordIcon) {
        toggleRegPasswordBtn.addEventListener('click', () => {
            const isPassword = regPasswordInput.getAttribute('type') === 'password';
            regPasswordInput.setAttribute('type', isPassword ? 'text' : 'password');
            toggleRegPasswordIcon.classList.toggle('fa-eye', !isPassword);
            toggleRegPasswordIcon.classList.toggle('fa-eye-slash', isPassword);
        });
    }

    // 4. Auto-dismiss Flash Alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach((alert) => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });
});
