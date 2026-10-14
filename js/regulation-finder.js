// regulation-finder.js

const documentsData = [
    {
        id: 1,
        title: "1.3 Revisi 01 Pedoman Pengadaan Barang dan Jasa 1 Juni 2026",
        category: "Pedoman Utama",
        content: "Proses tender harus dilakukan secara transparan. Evaluasi penawaran vendor didasarkan pada aspek teknis dan komersial dengan bobot yang telah ditentukan sebelumnya dalam dokumen pengadaan.",
        fileUrl: "data regulation finder/1.3 Revisi 01 Pedoman Pengadaan Barang dan Jasa 1 Juni 2026.pdf"
    },
    {
        id: 2,
        title: "2.1 Prosedur tahap 1-Permintaan Pemilihan Penyedia lewat PMO",
        category: "Surat Keputusan",
        content: "Setiap vendor wajib terdaftar dalam sistem VMS (Vendor Management System) sebelum mengikuti proses pengadaan. Kualifikasi vendor ditinjau setiap tahun.",
        fileUrl: "data regulation finder/2.1 Prosedur tahap 1-Permintaan Pemilihan Penyedia lewat PMO.pdf"
    },
    {
        id: 3,
        title: "3.2 Revisi 02 Prosedur Persiapan dan Pelaksanaan Pemilihan Penyedia",
        category: "Prosedur (SOP)",
        content: "Metode penunjukan langsung hanya dapat dilakukan dalam keadaan darurat, krisis, atau jika barang/jasa spesifik hanya dimiliki oleh satu pemegang hak paten tunggal (sole agent).",
        fileUrl: "data regulation finder/3.2 Revisi 02 Prosedur Persiapan dan Pelaksanaan Pemilihan Penyedia.pdf"
    },
    {
        id: 4,
        title: "4. Prosedur tahap 4,5-Penandatanganan dan Pelaksanaan Kontrak",
        category: "Panduan Teknis",
        content: "Penyusunan Harga Perkiraan Sendiri (HPS) atau Owner Estimate (OE) harus melibatkan riset pasar terbaru, membandingkan minimal tiga referensi harga yang valid.",
        fileUrl: "data regulation finder/4. Prosedur tahap 4,5-Penandatanganan dan Pelaksanaan Kontrak.pdf"
    },
    {
        id: 5,
        title: "5. Prosedur tahap 6-Penyerahan dan Penerimaan Barang atau Jasa",
        category: "Instruksi & Formulir",
        content: "Dokumen Instruksi Kepada Peserta Pemilihan (IKPP) mengatur tahapan proses pemilihan penyedia mulai dari penjelasan dokumen pengadaan (aanwijzing), penyampaian dokumen penawaran administrasi, teknis, dan harga, hingga evaluasi. Terdapat preferensi harga bagi produk dalam negeri dengan nilai TKDN lebih besar atau sama dengan 25%. Evaluasi penawaran menggunakan Sistem Gugur. Negosiasi harga dilakukan jika penawaran maksimal 20% di atas HPS. Peserta wajib mematuhi aturan masa sanggah dan menyerahkan Jaminan Sanggahan, Jaminan Penawaran, Jaminan Uang Muka, Jaminan Pelaksanaan (5%), dan Jaminan Pemeliharaan (5%). Pembayaran dilakukan melalui TT (telegraphic transfer) paling lambat 90 hari kalender.",
        fileUrl: "data regulation finder/5. Prosedur tahap 6-Penyerahan dan Penerimaan Barang atau Jasa.pdf"
    },
];

document.addEventListener("DOMContentLoaded", function () {

    if (sessionStorage.getItem('isLoggedIn') === 'false' || !sessionStorage.getItem('isLoggedIn')) {
        window.location.href = "login.html";
        return;
    }

    const username = sessionStorage.getItem('username') || 'Admin';
    const displayUsernameEl = document.getElementById('displayUsername');
    if (displayUsernameEl) displayUsernameEl.innerText = username;

    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearSearch');
    const resultsContainer = document.getElementById('resultsContainer');
    const resultCount = document.getElementById('resultCount');

    if (resultsContainer) {
        renderResults(documentsData);
    }

    function highlightText(text, keyword) {
        if (!keyword) return text;
        const safeKeyword = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${safeKeyword})`, 'gi');
        return text.replace(regex, '<span class="highlight">$1</span>');
    }

    function getSnippet(text, keyword, maxLength = 150) {
        if (!keyword) {
            return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
        }

        const lowerText = text.toLowerCase();
        const lowerKeyword = keyword.toLowerCase();
        const matchIndex = lowerText.indexOf(lowerKeyword);

        if (matchIndex === -1) {
            return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
        }

        const start = Math.max(0, matchIndex - 50);
        const end = Math.min(text.length, matchIndex + keyword.length + 100);

        let snippet = text.substring(start, end);

        if (start > 0) snippet = '... ' + snippet;
        if (end < text.length) snippet = snippet + ' ...';

        return snippet;
    }

    function renderResults(data, keyword = '') {
        resultsContainer.innerHTML = '';

        if (data.length === 0) {
            resultsContainer.innerHTML = `
                <div class="bg-white p-8 rounded-2xl border border-gray-200 text-center flex flex-col items-center">
                    <i class="ph ph-file-dashed text-4xl text-gray-300 mb-3"></i>
                    <h3 class="text-gray-900 font-semibold text-lg">Tidak ada hasil ditemukan</h3>
                    <p class="text-gray-500 text-sm">Coba gunakan kata kunci atau istilah lain.</p>
                </div>
            `;
            resultCount.innerText = "0 hasil ditemukan";
            return;
        }

        data.forEach(item => {
            const highlightedTitle = highlightText(item.title, keyword);
            const contentSnippet = getSnippet(item.content, keyword);
            const highlightedContent = highlightText(contentSnippet, keyword);

            let finalUrl = item.fileUrl || '#';
            if (item.fileUrl && item.fileUrl !== '#' && keyword) {
                finalUrl = `${item.fileUrl}#search=${encodeURIComponent(keyword)}`;
            }

            const cardHtml = `
                <div class="result-card bg-white p-6 rounded-2xl border border-gray-200 flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
                    <div class="flex-1">
                        <span class="inline-block px-3 py-1 bg-gray-100 text-gray-600 text-xs font-semibold rounded-full mb-2 border border-gray-200">
                            ${item.category}
                        </span>
                        <h2 class="text-xl font-bold text-sig-black mb-2 leading-tight">${highlightedTitle}</h2>
                        <p class="text-gray-600 text-sm leading-relaxed">
                            ${highlightedContent}
                        </p>
                    </div>
                    <div class="mt-4 md:mt-0 md:ml-4 w-full md:w-auto flex-shrink-0">
                        <a href="${finalUrl}" target="_blank" class="w-full md:w-auto px-5 py-2.5 bg-white text-sig-red border border-sig-red font-semibold text-sm rounded-xl hover:bg-sig-red hover:text-white transition-colors flex items-center justify-center gap-2">
                            <i class="ph ph-file-text text-lg"></i> Buka Dokumen
                        </a>
                    </div>
                </div>
            `;
            resultsContainer.insertAdjacentHTML('beforeend', cardHtml);
        });

        if (keyword) {
            resultCount.innerHTML = `Menemukan <span class="font-bold text-sig-black">${data.length}</span> dokumen untuk kata kunci "<span class="text-sig-red font-semibold">${keyword}</span>"`;
        } else {
            resultCount.innerText = `Menampilkan semua dokumen (${data.length})`;
        }
    }

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const keyword = e.target.value.trim().toLowerCase();

            if (keyword.length > 0) {
                clearBtn.classList.remove('hidden');
            } else {
                clearBtn.classList.add('hidden');
            }

            const filteredData = documentsData.filter(item =>
                item.title.toLowerCase().includes(keyword) ||
                item.content.toLowerCase().includes(keyword)
            );

            renderResults(filteredData, keyword);
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            searchInput.value = '';
            clearBtn.classList.add('hidden');
            searchInput.focus();
            renderResults(documentsData);
        });
    }
});