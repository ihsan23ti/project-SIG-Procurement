document.addEventListener("DOMContentLoaded", function() {
    const loginForm = document.getElementById('loginForm');

    loginForm.addEventListener('submit', function(event) {
        event.preventDefault(); // Mencegah halaman refresh otomatis
        
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        
        if (username !== '' && password !== '') {
            // Animasi atau proses sederhana saat tombol ditekan
            const btn = document.querySelector('.btn-login');
            btn.innerHTML = "Memproses...";
            
            setTimeout(() => {
                alert(`Login simulasi berhasil! \nSelamat datang, ${username}.`);
                btn.innerHTML = "Masuk";
                // Nanti bisa diganti dengan kode pindah halaman:
                // window.location.href = "dashboard.html";
            }, 1000); // Jeda 1 detik seolah-olah sedang loading
        }
    });
});