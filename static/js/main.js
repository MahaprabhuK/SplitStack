/**
 * SplitStack - Core JavaScript
 * Enhanced with jQuery 3.7.1
 */

// Verification check to confirm jQuery is loaded and available
if (typeof jQuery !== 'undefined') {
    console.log('SplitStack jQuery loaded');
}

$(document).ready(function ($) {
    // 1. Dynamic Greeting
    const $welcomeGreeting = $('#welcomeGreeting');
    if ($welcomeGreeting.length) {
        const hour = new Date().getHours();
        $welcomeGreeting.text(hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening');
    }

    // 2. Mobile Navigation Drawer
    const $sidebar = $('#sidebar');
    const $sidebarScrim = $('#sidebarScrim');
    const closeSidebar = () => {
        $sidebar.removeClass('open');
        $sidebarScrim.removeClass('open');
    };

    $('#navToggle').on('click', function (e) {
        e.stopPropagation();
        $sidebar.toggleClass('open');
        $sidebarScrim.toggleClass('open');
    });

    $('#sidebarClose, #sidebarScrim').on('click', closeSidebar);
    $sidebar.find('a').on('click', closeSidebar);

    // 3. Password Visibility Toggles
    $(document).on('click', '.btn-toggle-password, #togglePasswordBtn, #toggleRegPasswordBtn', function (e) {
        e.preventDefault();
        const $btn = $(this);
        const $wrap = $btn.closest('.password-input-wrap');
        const $input = $wrap.length ? $wrap.find('input') : $btn.siblings('input');
        const $icon = $btn.find('i');

        if ($input.length) {
            const isPassword = $input.attr('type') === 'password';
            $input.attr('type', isPassword ? 'text' : 'password');
            $icon.toggleClass('fa-eye fa-eye-slash');
        }
    });

    // 4. Alert Auto-Dismiss & Smooth Close Handling
    const $alerts = $('.alert');
    if ($alerts.length) {
        $alerts.each(function () {
            const $alert = $(this);
            const isDanger = $alert.hasClass('alert-danger') || $alert.hasClass('alert-error');
            const dismissDelay = isDanger ? 8000 : 4500;
            $alert.delay(dismissDelay).fadeOut(600, function () {
                $(this).remove();
            });
        });
    }

    $(document).on('click', '.alert-close', function (e) {
        e.preventDefault();
        $(this).closest('.alert').stop(true, true).fadeOut(300, function () {
            $(this).remove();
        });
    });

    // 5. Delete & Destructive Action Confirmation
    $(document).on('submit', 'form[data-confirm]', function (e) {
        const msg = $(this).data('confirm') || 'Are you sure you want to proceed with this action?';
        if (!confirm(msg)) {
            e.preventDefault();
            return false;
        }
    });

    $(document).on('click', '.btn-delete, .delete-btn, [data-confirm-delete]', function (e) {
        const msg = $(this).data('confirm-delete') || $(this).data('confirm') || 'Are you sure you want to delete this?';
        if (!confirm(msg)) {
            e.preventDefault();
            return false;
        }
    });

    // 6. Shopping Checklist Interactive Feedback
    $(document).on('click', '.btn-check-toggle', function () {
        const $btn = $(this);
        const $row = $btn.closest('.item-row');
        $row.toggleClass('item-purchased');
        $btn.toggleClass('checked');
        const $icon = $btn.find('i');
        if ($btn.hasClass('checked')) {
            $icon.removeClass('fa-circle text-muted').addClass('fa-circle-check text-emerald');
        } else {
            $icon.removeClass('fa-circle-check text-emerald').addClass('fa-circle text-muted');
        }
    });

    // 7. Theme Preference Management
    const $themeToggle = $('#themeToggle');
    if ($themeToggle.length) {
        const savedTheme = localStorage.getItem('splitstack-theme');
        if (savedTheme === 'light') {
            $('body').addClass('theme-light');
        }
        $themeToggle.on('click', function () {
            $('body').toggleClass('theme-light');
            const isLight = $('body').hasClass('theme-light');
            localStorage.setItem('splitstack-theme', isLight ? 'light' : 'dark');
        });
    }

    // 8. Global Workspace Search in Navigation
    $('#globalSearch').on('input', function () {
        const query = $(this).val().toLowerCase().trim();
        $('.sidebar .nav-links li').each(function () {
            const $item = $(this);
            if (!query) {
                $item.show();
            } else {
                const text = $item.text().toLowerCase();
                $item.toggle(text.indexOf(query) !== -1);
            }
        });
    });

    // 9. Quick Notification Scroll
    $('#notificationButton').on('click', function () {
        const $firstAlert = $('.alert').first();
        if ($firstAlert.length) {
            $('html, body').animate({
                scrollTop: Math.max(0, $firstAlert.offset().top - 80)
            }, 300);
        }
    });
});
