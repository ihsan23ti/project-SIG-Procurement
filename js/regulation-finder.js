// ==========================================
// REGULATION FINDER - SIG PROCUREMENT
// ==========================================

// Metadata Dokumen agar tampilan rapi, elegan, dan konsisten dengan Procurement Document
const DOKUMEN_METADATA = {
    "1.3 Revisi 01 Pedoman Pengadaan Barang dan Jasa 1 Juni 2026.pdf": {
        badge: "Pedoman Utama",
        judul: "Pedoman Pengadaan Barang dan/atau Jasa",
        deskripsi: "Kode Dokumen: M/SIG/PRO/002 | Revisi: 01 | 01 Juni 2026. Pedoman utama yang menjadi landasan seluruh proses pengadaan di lingkungan perusahaan PT Semen Indonesia (Persero) Tbk."
    },
    "2.1 Prosedur tahap 1-Permintaan Pemilihan Penyedia lewat PMO.pdf": {
        badge: "Prosedur (SOP)",
        judul: "Prosedur Permintaan Pemilihan Penyedia Lewat PMO",
        deskripsi: "Prosedur operasional standar (SOP) tata cara permintaan pemilihan penyedia barang/jasa melalui unit Project Management Office (PMO)."
    },
    "3.2 Revisi 02 Prosedur Persiapan dan Pelaksanaan Pemilihan Penyedia.pdf": {
        badge: "Prosedur (SOP)",
        judul: "Prosedur Persiapan & Pelaksanaan Pemilihan Penyedia",
        deskripsi: "Kode Dokumen: Revisi: 02. Prosedur operasional standar (SOP) teknis tahapan persiapan dan pelaksanaan tender/pemilihan penyedia."
    },
    "4. Prosedur tahap 4,5-Penandatanganan dan Pelaksanaan Kontrak.pdf": {
        badge: "Prosedur (SOP)",
        judul: "Prosedur Penandatanganan & Pelaksanaan Kontrak",
        deskripsi: "Prosedur operasional standar (SOP) tata cara penandatanganan perjanjian/kontrak serta pelaksanaan kontrak pengadaan."
    },
    "5. Prosedur tahap 6-Penyerahan dan Penerimaan Barang atau Jasa.pdf": {
        badge: "Prosedur (SOP)",
        judul: "Prosedur Penyerahan & Penerimaan Barang atau Jasa",
        deskripsi: "Prosedur operasional standar (SOP) tata cara serah terima hasil pengadaan, pemeriksaan mutu spesifikasi, dan penerimaan barang/jasa."
    }
};

function getMetadataDokumen(namaFile) {
    if (DOKUMEN_METADATA[namaFile]) {
        return DOKUMEN_METADATA[namaFile];
    }

    // Fallback dinamis jika file PDF baru ditambahkan ke folder
    const namaBersih = namaFile
        .replace(/\.pdf$/i, "")
        .replace(/^[0-9.]+\s*/, "")
        .trim();

    let badge = "Dokumen Regulasi";
    if (/pedoman/i.test(namaFile)) {
        badge = "Pedoman Utama";
    } else if (/prosedur/i.test(namaFile)) {
        badge = "Prosedur (SOP)";
    } else if (/panduan/i.test(namaFile)) {
        badge = "Panduan Sistem";
    }

    return {
        badge: badge,
        judul: namaBersih,
        deskripsi: "Dokumen regulasi dan pedoman pengadaan PT Semen Indonesia (Persero) Tbk."
    };
}

// ==========================================
// FUNGSI MODAL PREVIEW (SAMA PERSIS DENGAN PROCUREMENT DOCUMENT)
// ==========================================

function openPreview(url, title, downloadUrl) {
    if (url) {
        window.open(url, "_blank");
    }
}

function closePreview() {
    const previewModal = document.getElementById("previewModal");
    const pdfViewer = document.getElementById("pdfViewer");
    if (!previewModal || !pdfViewer) return;

    previewModal.classList.add("hidden");
    previewModal.classList.remove("flex", "modal-enter");
    pdfViewer.src = "";
}

// Daftarkan di scope global (window)
window.openPreview = openPreview;
window.closePreview = closePreview;

// Tutup modal jika klik backdrop atau tombol Escape
document.addEventListener("DOMContentLoaded", function () {
    const previewModal = document.getElementById("previewModal");
    if (previewModal) {
        previewModal.addEventListener("click", function (e) {
            if (e.target === previewModal) {
                closePreview();
            }
        });
    }

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && previewModal && !previewModal.classList.contains("hidden")) {
            closePreview();
        }
    });
});

// ==========================================
// LOGIKA UTAMA REGULATION FINDER
// ==========================================

document.addEventListener("DOMContentLoaded", function () {
    // ------------------------------------------
    // CEK LOGIN
    // ------------------------------------------
    if (sessionStorage.getItem("isLoggedIn") !== "true") {
        window.location.href = "login.html";
        return;
    }

    // ------------------------------------------
    // AMBIL ELEMEN HTML
    // ------------------------------------------
    const searchInput = document.getElementById("searchInput");
    const clearBtn = document.getElementById("clearSearch");
    const resultsContainer = document.getElementById("resultsContainer");
    const resultCount = document.getElementById("resultCount");
    const username = document.getElementById("displayUsername");

    if (username) {
        username.textContent = sessionStorage.getItem("username") || "Admin";
    }

    if (!searchInput || !clearBtn || !resultsContainer || !resultCount) {
        console.error("Elemen Regulation Finder tidak lengkap. Periksa ID di HTML.");
        return;
    }

    // ------------------------------------------
    // VARIABEL
    // ------------------------------------------
    let timerPencarian;
    let nomorPermintaan = 0;

    // ------------------------------------------
    // TAMPILKAN PESAN / STATUS
    // ------------------------------------------
    function tampilkanPesan(pesan) {
        resultsContainer.replaceChildren();

        const elemen = document.createElement("div");
        elemen.className = "bg-white p-6 rounded-[10px] border border-gray-200 text-gray-500 text-center text-sm";
        elemen.textContent = pesan;

        resultsContainer.appendChild(elemen);
    }

    // ------------------------------------------
    // BUAT KARTU DOKUMEN (MODEL PROCUREMENT DOCUMENT)
    // ------------------------------------------
    function buatKartuDokumen(namaFile, halaman = null, cuplikan = "") {
        const meta = getMetadataDokumen(namaFile);
        const judul = meta.judul;
        const badge = meta.badge;
        const deskripsi = meta.deskripsi;

        // Container kartu (sama persis dengan .result-card di procurement-document.html)
        const kartu = document.createElement("div");
        kartu.className = "result-card";

        // Konten Kiri (flex-1)
        const content = document.createElement("div");
        content.className = "flex-1";

        // Container Badge
        const badgeContainer = document.createElement("div");
        badgeContainer.className = "flex items-center flex-wrap gap-2 mb-3";

        // Badge Kategori
        const badgeEl = document.createElement("span");
        badgeEl.className = "inline-block px-3 py-1 bg-gray-100 text-gray-700 text-[11px] font-bold rounded-full";
        badgeEl.textContent = badge;
        badgeContainer.appendChild(badgeEl);

        // Badge Halaman (jika dari hasil pencarian)
        if (halaman) {
            const pageBadge = document.createElement("span");
            pageBadge.className = "inline-flex items-center gap-1 px-3 py-1 bg-red-50 text-[#D7192A] border border-red-200 text-[11px] font-bold rounded-full";
            pageBadge.innerHTML = '<i class="ph-bold ph-bookmark-simple"></i> Halaman ' + halaman;
            badgeContainer.appendChild(pageBadge);
        }

        content.appendChild(badgeContainer);

        // Judul Dokumen (h3 text-lg font-bold text-gray-900 mb-2)
        const judulEl = document.createElement("h3");
        judulEl.className = "text-lg font-bold text-gray-900 mb-2";
        judulEl.textContent = judul;
        content.appendChild(judulEl);

        // Deskripsi / Cuplikan
        if (cuplikan) {
            const descEl = document.createElement("p");
            descEl.className = "text-xs text-gray-400 mb-2 font-medium";
            descEl.textContent = deskripsi;
            content.appendChild(descEl);

            const cuplikanContainer = document.createElement("div");
            cuplikanContainer.className = "bg-gray-50 p-3.5 md:p-4 rounded-lg border border-gray-200 mt-2.5";

            const cuplikanHeader = document.createElement("div");
            cuplikanHeader.className = "flex items-center gap-1.5 text-xs font-semibold text-gray-500 mb-1.5";
            cuplikanHeader.innerHTML = '<i class="ph-bold ph-quotes text-[#D7192A]"></i> Ringkasan Regulasi:';
            cuplikanContainer.appendChild(cuplikanHeader);

            const cuplikanEl = document.createElement("p");
            cuplikanEl.className = "text-sm text-gray-700 leading-relaxed break-words font-normal";
            cuplikanEl.textContent = cuplikan;
            cuplikanContainer.appendChild(cuplikanEl);

            content.appendChild(cuplikanContainer);
        } else {
            const descEl = document.createElement("p");
            descEl.className = "text-sm text-gray-500 leading-relaxed";
            descEl.textContent = deskripsi;
            content.appendChild(descEl);
        }

        kartu.appendChild(content);

        // Tombol Buka Dokumen (desain persis procurement-document.html, dibuka di tab baru)
        const fileUrl = "/data%20regulation%20finder/" + encodeURIComponent(namaFile);
        const previewUrl = halaman ? fileUrl + "#page=" + halaman : fileUrl;

        const tombol = document.createElement("a");
        tombol.href = previewUrl;
        tombol.target = "_blank";
        tombol.rel = "noopener noreferrer";
        tombol.className = "border border-[#D7192A] text-[#D7192A] hover:bg-red-50 px-5 py-2.5 rounded-lg text-[13px] font-bold transition-colors flex items-center justify-center gap-2 shrink-0 no-underline";
        tombol.innerHTML = '<i class="ph ph-file-text text-lg"></i> Buka Dokumen';

        kartu.appendChild(tombol);

        return kartu;
    }

    // ------------------------------------------
    // MUAT SEMUA DOKUMEN SAAT PERTAMA DIBUKA
    // ------------------------------------------
    async function muatSemuaDokumen() {
        const id = ++nomorPermintaan;

        resultCount.textContent = "Memuat dokumen...";
        tampilkanPesan("Sedang memuat daftar dokumen regulasi...");

        try {
            const response = await fetch("/api/documents", {
                method: "GET",
                cache: "no-store"
            });

            const data = await response.json();

            if (id !== nomorPermintaan) {
                return;
            }

            if (!response.ok) {
                throw new Error(data.error || "Gagal mengambil daftar dokumen.");
            }

            const daftarDokumen = data.documents || [];

            resultsContainer.replaceChildren();

            if (daftarDokumen.length === 0) {
                resultCount.textContent = "Tidak ada dokumen (0)";
                tampilkanPesan("Belum ada file PDF yang ditemukan di folder 'data regulation finder'.");
                return;
            }

            const fragmen = document.createDocumentFragment();

            daftarDokumen.forEach(function (namaFile) {
                fragmen.appendChild(buatKartuDokumen(namaFile));
            });

            resultsContainer.appendChild(fragmen);
            resultCount.textContent = "Menampilkan semua dokumen (" + daftarDokumen.length + ")";

        } catch (error) {
            if (id !== nomorPermintaan) {
                return;
            }

            console.error("Gagal memuat daftar PDF:", error);
            resultCount.textContent = "Gagal memuat dokumen";
            tampilkanPesan(error.message + " Pastikan server Flask aktif.");
        }
    }

    // ------------------------------------------
    // CARI KATA DALAM ISI PDF
    // ------------------------------------------
    async function cariDokumen(kataKunci) {
        const id = ++nomorPermintaan;

        if (!kataKunci) {
            await muatSemuaDokumen();
            return;
        }

        resultCount.textContent = "Sedang mencari...";
        tampilkanPesan("Sedang mencari kata kunci dalam isi dokumen PDF...");

        try {
            const response = await fetch("/api/search", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    kata: kataKunci
                })
            });

            const data = await response.json();

            if (id !== nomorPermintaan) {
                return;
            }

            if (!response.ok) {
                throw new Error(data.error || "Pencarian dokumen gagal.");
            }

            const hasil = data.hasil || [];

            resultsContainer.replaceChildren();

            if (hasil.length === 0) {
                resultCount.textContent = "Tidak ada hasil (0)";
                tampilkanPesan('Kata kunci "' + kataKunci + '" tidak ditemukan dalam seluruh isi dokumen regulasi.');
                return;
            }

            const fragmen = document.createDocumentFragment();

            hasil.forEach(function (item) {
                fragmen.appendChild(
                    buatKartuDokumen(
                        item.file,
                        item.halaman,
                        item.cuplikan || ""
                    )
                );
            });

            resultsContainer.appendChild(fragmen);
            resultCount.textContent = "Ditemukan pada " + hasil.length + " halaman";

        } catch (error) {
            if (id !== nomorPermintaan) {
                return;
            }

            console.error("Pencarian PDF gagal:", error);
            resultCount.textContent = "Pencarian gagal";
            tampilkanPesan(error.message);
        }
    }

    // ------------------------------------------
    // EVENT PENCARIAN (DEBOUNCE)
    // ------------------------------------------
    searchInput.addEventListener("input", function () {
        const kata = searchInput.value.trim();

        clearBtn.classList.toggle("hidden", !kata);

        clearTimeout(timerPencarian);

        timerPencarian = setTimeout(function () {
            cariDokumen(kata);
        }, 350);
    });

    // ------------------------------------------
    // TOMBOL HAPUS PENCARIAN
    // ------------------------------------------
    clearBtn.addEventListener("click", function () {
        searchInput.value = "";
        clearBtn.classList.add("hidden");
        clearTimeout(timerPencarian);
        muatSemuaDokumen();
        searchInput.focus();
    });

    // ------------------------------------------
    // TAMPILKAN DOKUMEN PERTAMA KALI
    // ------------------------------------------
    muatSemuaDokumen();
});
