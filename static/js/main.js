/**
 * SplitStack - Core JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    const welcomeGreeting = document.getElementById('welcomeGreeting');
    if (welcomeGreeting) {
        const hour = new Date().getHours();
        welcomeGreeting.textContent = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
    }

    // Mobile navigation drawer
    const navToggle = document.getElementById('navToggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarScrim = document.getElementById('sidebarScrim');
    const sidebarClose = document.getElementById('sidebarClose');

    const closeSidebar = () => {
        sidebar?.classList.remove('open');
        sidebarScrim?.classList.remove('open');
    };
    if (navToggle && sidebar) {
        navToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebarScrim?.classList.toggle('open');
        });
    }
    sidebarClose?.addEventListener('click', closeSidebar);
    sidebarScrim?.addEventListener('click', closeSidebar);
    sidebar?.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeSidebar));

    // Password visibility toggles
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

    // Theme preference is local to the browser and does not affect financial data.
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        const savedTheme = localStorage.getItem('splitstack-theme');
        if (savedTheme === 'light') document.body.classList.add('theme-light');
        themeToggle.addEventListener('click', () => {
            document.body.classList.toggle('theme-light');
            localStorage.setItem('splitstack-theme', document.body.classList.contains('theme-light') ? 'light' : 'dark');
        });
    }

    // Search visible navigation labels without changing route behavior.
    const globalSearch = document.getElementById('globalSearch');
    globalSearch?.addEventListener('input', (event) => {
        const query = event.target.value.toLowerCase().trim();
        document.querySelectorAll('.sidebar .nav-links li').forEach((item) => {
            item.hidden = query && !item.textContent.toLowerCase().includes(query);
        });
    });

    // Notifications point to the page's existing flash messages when present.
    document.getElementById('notificationButton')?.addEventListener('click', () => {
        const firstAlert = document.querySelector('.alert');
        if (firstAlert) firstAlert.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });

    // Auto-dismiss flash alerts after 5 seconds.
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach((alert) => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });
});
