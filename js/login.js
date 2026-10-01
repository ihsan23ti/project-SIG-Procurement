document.addEventListener("DOMContentLoaded", function() {
    // Jika sudah login, langsung ke dashboard
    if (sessionStorage.getItem('isLoggedIn') === 'true') {
        window.location.href = "index.html";
        return;
    }

    const loginForm = document.getElementById('loginForm');

    loginForm.addEventListener('submit', function(event) {
        event.preventDefault(); // Mencegah halaman refresh otomatis
        
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value.trim();
        
        if (username !== '' && password !== '') {
            // Animasi loading saat tombol ditekan
            const btn = document.querySelector('.btn-login');
            btn.innerHTML = "Memproses...";
            btn.disabled = true;
            
            setTimeout(() => {
                // Simpan sesi login
                sessionStorage.setItem('isLoggedIn', 'true');
                sessionStorage.setItem('username', username);

                // Redirect ke dashboard
                window.location.href = "index.html";
            }, 1000); // Jeda 1 detik untuk efek loading
        }
    });
});