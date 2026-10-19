// chatbot.js

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
        loadingDiv.innerText = 'AI sedang membaca mencari jawaban...';
        messagesContainer.appendChild(loadingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        try {
            // Memanggil API Flask milikmu sendiri
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pesan: userText })
            });

            const data = await response.json();
            document.getElementById(loadingId).remove(); 

            if (!response.ok) {
                addMessage("<b>Pesan Error dari Server:</b><br>" + (data.error || "Gagal menghubungi backend."), false, true);
                return;
            }

            if (data.jawaban) {
                // Konversi markdown sederhana dari Gemini ke HTML
                let aiResponse = data.jawaban.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
                addMessage(aiResponse, false);
            } else {
                addMessage("Maaf, tidak ada balasan dari server.", false, true);
            }
        } catch (error) {
            console.error("Error Fetch:", error);
            document.getElementById(loadingId).remove();
            addMessage("Koneksi gagal. Pastikan server Flask (main.py) sudah berjalan.", false, true);
        }
    }

    if (sendBtn && inputField) {
        sendBtn.addEventListener('click', sendMessage);
        inputField.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }
});