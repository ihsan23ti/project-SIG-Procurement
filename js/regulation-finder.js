
document.addEventListener("DOMContentLoaded", function () {
    // Periksa login
    if (!sessionStorage.getItem("isLoggedIn") ||
        sessionStorage.getItem("isLoggedIn") === "false") {
        window.location.href = "login.html";
        return;
    }

    // Ambil elemen halaman
    const searchInput = document.getElementById("searchInput");
    const clearBtn = document.getElementById("clearSearch");
    const resultsContainer = document.getElementById("resultsContainer");
    const resultCount = document.getElementById("resultCount");

    const username = sessionStorage.getItem("username") || "Admin";
    const displayUsername = document.getElementById("displayUsername");

    if (displayUsername) {
        displayUsername.textContent = username;
    }

    if (!searchInput || !clearBtn ||
        !resultsContainer || !resultCount) {
        console.error("Elemen pencarian tidak ditemukan.");
        return;
    }

    let timerPencarian;
    let nomorPermintaan = 0;

    function tampilkanPesan(pesan) {
        resultsContainer.replaceChildren();

        const elemen = document.createElement("div");
        elemen.className =
            "bg-white p-8 rounded-2xl border border-gray-200 text-center text-gray-600";
        elemen.textContent = pesan;

        resultsContainer.appendChild(elemen);
    }

    function tampilkanHasil(data, kataKunci) {
        resultsContainer.replaceChildren();

        if (data.pesan) {
            resultCount.textContent = "Folder PDF tidak ditemukan";
            tampilkanPesan(data.pesan);
            return;
        }

        const hasil = data.hasil || [];

        resultCount.textContent =
            `Ditemukan pada ${data.jumlah ?? hasil.length} halaman`;

        if (hasil.length === 0) {
            tampilkanPesan(
                `Kata "${kataKunci}" tidak ditemukan dalam dokumen PDF.`
            );
            return;
        }

        hasil.forEach(function (item) {
            const kartu = document.createElement("article");
            kartu.className =
                "result-card bg-white p-6 rounded-2xl border border-gray-200 mb-4";

            const namaFile = document.createElement("h2");
            namaFile.className =
                "text-lg font-bold text-sig-black mb-2 break-words";
            namaFile.textContent = item.file;

            const infoHalaman = document.createElement("p");
            infoHalaman.className = "text-sm text-gray-500 mb-3";
            infoHalaman.textContent = `Halaman ${item.halaman}`;

            const label = document.createElement("span");
            label.className =
                "inline-block px-3 py-1 bg-gray-100 text-gray-600 text-xs font-semibold rounded-full mb-3";
            label.textContent = "Dokumen PDF";

            const cuplikan = document.createElement("p");
            cuplikan.className =
                "text-gray-600 text-sm leading-relaxed bg-gray-50 p-4 rounded-xl break-words";
            cuplikan.textContent = item.cuplikan || "Cuplikan tidak tersedia.";

            const tombol = document.createElement("a");
            tombol.className =
                "inline-flex items-center gap-2 mt-4 px-5 py-2.5 bg-white text-sig-red border border-sig-red font-semibold text-sm rounded-xl hover:bg-sig-red hover:text-white transition-colors";

            // Buka PDF langsung pada halaman yang ditemukan
            tombol.href =
                "/data%20regulation%20finder/" +
                encodeURIComponent(item.file) +
                "#page=" + encodeURIComponent(item.halaman);

            tombol.target = "_blank";
            tombol.rel = "noopener noreferrer";
            tombol.textContent = "Buka Dokumen";

            kartu.append(
                label,
                namaFile,
                infoHalaman,
                cuplikan,
                tombol
            );

            resultsContainer.appendChild(kartu);
        });
    }

    async function cariDokumen(kataKunci) {
        const idPermintaan = ++nomorPermintaan;

        if (!kataKunci) {
            resultCount.textContent = "Masukkan kata kunci pencarian";
            tampilkanPesan(
                "Ketik kata atau frasa untuk mencari di dalam dokumen PDF."
            );
            return;
        }

        resultCount.textContent = "Sedang mencari di seluruh PDF...";
        tampilkanPesan("Sedang mencari. Mohon tunggu...");

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

            // Abaikan respons pencarian lama
            if (idPermintaan !== nomorPermintaan) {
                return;
            }

            if (!response.ok) {
                throw new Error(
                    data.error || "Pencarian gagal."
                );
            }

            tampilkanHasil(data, kataKunci);

        } catch (error) {
            if (idPermintaan !== nomorPermintaan) {
                return;
            }

            resultCount.textContent = "Pencarian gagal";
            tampilkanPesan(
                error.message +
                " Pastikan server Flask berjalan dan endpoint /api/search tersedia."
            );

            console.error("Kesalahan pencarian:", error);
        }
    }

    // Cari saat pengguna mengetik
    searchInput.addEventListener("input", function () {
        const kataKunci = searchInput.value.trim();

        clearBtn.classList.toggle("hidden", !searchInput.value);

        clearTimeout(timerPencarian);

        timerPencarian = setTimeout(function () {
            cariDokumen(kataKunci);
        }, 400);
    });

    // Kosongkan pencarian
    clearBtn.addEventListener("click", function () {
        searchInput.value = "";
        clearBtn.classList.add("hidden");

        clearTimeout(timerPencarian);
        cariDokumen("");
        searchInput.focus();
    });

    // Tampilan awal
    resultCount.textContent = "Siap mencari dokumen";
    tampilkanPesan(
        "Masukkan kata kunci untuk mencari isi seluruh dokumen PDF."
    );
});
