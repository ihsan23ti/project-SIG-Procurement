// chatbot.js

// 1. API KEY GEMINI KAMU
const API_KEY = "AQ.Ab8RN6JRt0GJreirZW6gfBfJ6VaF856bd4k31oTjV2pqvwY18g"; 

// 2. OTAK AI (KNOWLEDGE BASE DARI PDF PEDOMAN SIG)
const SYSTEM_PROMPT = `
Kamu adalah Asisten AI profesional untuk Portal Pengadaan PT Semen Indonesia (Persero) Tbk (SIG). 
Tugasmu adalah menjawab pertanyaan pengguna HANYA berdasarkan aturan pengadaan SIG berikut ini. 
Gunakan bahasa Indonesia yang ramah, profesional, dan mudah dipahami. Jika pertanyaan di luar konteks ini, tolak dengan sopan.

INFORMASI PEDOMAN PENGADAAN BARANG DAN JASA SIG:

1. TAHAPAN PENGADAAN (Ada 6 Tahap):
- Tahap Permintaan: Dilakukan oleh Fungsi Peminta. Untuk Capex atau Opex Non-Rutin > Rp20 Miliar, harus diserahkan ke Fungsi Pengadaan melalui PMO.
- Tahap Persiapan: Dilakukan oleh Fungsi Pengadaan & Panitia Pengadaan. Kegiatannya meliputi penyusunan HPS, penetapan metode, dan pembuatan IKPP.
- Tahap Pelaksanaan: Dilakukan oleh Panitia Pengadaan (Aanwijzing, evaluasi penawaran, negosiasi, LHPP).
- Tahap Finalisasi Kontrak: Oleh Fungsi Pelaksana. Bisa berupa Perjanjian atau Order Pembelian.
- Tahap Pelaksanaan Kontrak: Pengawasan pekerjaan, Change Order/Klaim, Amendemen, Novasi.
- Tahap Penyerahan: Pembuatan BAST (Berita Acara Serah Terima) Barang/Jasa dan Sertifikat Penyelesaian Pekerjaan (SPP).

2. METODE PENGADAAN:
- Pengadaan Langsung: Untuk barang/jasa yang harganya ditetapkan pemerintah, < Rp100 juta (PKP), atau melalui e-Catalog/PaDi UMKM.
- Penunjukan Langsung: Untuk kondisi darurat, HAKI/Paten tunggal (sole agent), repeat order, atau jika Tender Umum gagal 2x.
- Tender Terbatas: Mengundang rekanan yang sudah terklasifikasi (minimal 3 rekanan).
- Tender Umum: Diumumkan luas lewat media/website, dimulai dengan proses Prakualifikasi.

3. ATURAN JAMINAN:
- Jaminan Penawaran: 1% - 3% dari HPS.
- Jaminan Sanggahan: 1% dari total penawaran.
- Jaminan Uang Muka: Diberikan maksimal 30% dari nilai kontrak.
- Jaminan Pelaksanaan: 5% - 10% dari total nilai Kontrak.
- Jaminan Pemeliharaan (Retensi): 5% dari total nilai Kontrak.

4. ATURAN TKDN (Tingkat Komponen Dalam Negeri):
- Preferensi harga diberikan jika produk dalam negeri memiliki TKDN >= 25%.
- Evaluasi harga akhir menggunakan rumus HEA = (1 - KP) x HP (Harga Penawaran).

5. NEGOSIASI & EVALUASI:
- Negosiasi diutamakan menggunakan e-Reverse Auction (Metode English atau Japanese).
- Evaluasi Harga Satuan Timpang: Jika harga satuan penawaran melebihi 110% dari HPS, wajib diklarifikasi.
- Metode Evaluasi: Sistem Gugur, Sistem Nilai (Passing Grade / Merit Point), dan Total Cost of Ownership (TCO).

6. PERJANJIAN & SERAH TERIMA (BAST):
- Jenis Perjanjian: Pengadaan Barang/Jasa, Jasa Pekerjaan Konstruksi, Konsultansi Konstruksi, Konsultansi Non-Konstruksi.
- Terdapat Masa Pemberitahuan Cacat untuk Jasa Konstruksi sebelum Jaminan Pemeliharaan bisa dicairkan.
- Jika Barang ditolak saat inspeksi, Fungsi Pelaksana menerbitkan Nota Penolakan Barang.
`;

document.addEventListener("DOMContentLoaded", function() {
    const toggleBtn = document.getElementById('chatbot-toggle');
    const closeBtn = document.getElementById('chatbot-close');
    const chatWindow = document.getElementById('chatbot-window');
    const inputField = document.getElementById('chatbot-input');
    const sendBtn = document.getElementById('chatbot-send');
    const messagesContainer = document.getElementById('chatbot-messages');

    if (toggleBtn && closeBtn && chatWindow) {
        toggleBtn.addEventListener('click', () => {
            chatWindow.classList.remove('hidden');
            inputField.focus();
        });
        closeBtn.addEventListener('click', () => chatWindow.classList.add('hidden'));
    }

    function addMessage(text, isUser, isError = false) {
        const msgDiv = document.createElement('div');
        
        if (isUser) {
            msgDiv.className = 'p-4 max-w-[85%] text-base bg-sig-red text-white rounded-tl-2xl rounded-br-2xl rounded-bl-2xl self-end shadow-md';
        } else if (isError) {
            msgDiv.className = 'p-4 max-w-[85%] text-base bg-red-100 border border-red-400 text-red-800 rounded-tr-2xl rounded-br-2xl rounded-bl-2xl self-start shadow-sm font-mono text-xs';
        } else {
            msgDiv.className = 'p-4 max-w-[85%] text-base bg-white border border-gray-200 text-gray-800 rounded-tr-2xl rounded-br-2xl rounded-bl-2xl self-start shadow-sm leading-relaxed';
        }
        
        msgDiv.innerHTML = text; 
        messagesContainer.appendChild(msgDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    async function sendMessage() {
        const userText = inputField.value.trim();
        if (!userText) return;

        addMessage(userText, true);
        inputField.value = '';
        
        const loadingId = 'loading-' + Date.now();
        const loadingDiv = document.createElement('div');
        loadingDiv.id = loadingId;
        loadingDiv.className = 'p-4 max-w-[85%] text-sm bg-gray-100 text-gray-500 rounded-tr-2xl rounded-br-2xl rounded-bl-2xl self-start italic animate-pulse';
        loadingDiv.innerText = 'Mencari aturan di pedoman SIG...';
        messagesContainer.appendChild(loadingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        try {
            const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key=${API_KEY}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contents: [{ role: "user", parts: [{ text: SYSTEM_PROMPT + "\n\nPertanyaan: " + userText }] }]
                })
            });

            const data = await response.json();
            document.getElementById(loadingId).remove(); 

            // CATCH ERROR DARI GOOGLE LANGSUNG
            if (!response.ok) {
                let errorMsg = data.error ? data.error.message : JSON.stringify(data);
                addMessage("<b>Pesan Error dari Google:</b><br>" + errorMsg, false, true);
                return;
            }

            if (data.candidates && data.candidates.length > 0) {
                let aiResponse = data.candidates[0].content.parts[0].text;
                aiResponse = aiResponse.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
                addMessage(aiResponse, false);
            } else {
                addMessage("Maaf, format balasan AI tidak sesuai.", false, true);
            }
        } catch (error) {
            console.error("Error API:", error);
            document.getElementById(loadingId).remove();
            addMessage("Maaf, koneksi ke server AI gagal (CORS/Network Error). Buka tab Console (F12) untuk melihat detailnya.", false, true);
        }
    }

    if (sendBtn && inputField) {
        sendBtn.addEventListener('click', sendMessage);
        inputField.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }
});