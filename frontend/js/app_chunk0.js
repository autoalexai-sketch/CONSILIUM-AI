        // ==========================================
        // CONFIGURATION
        // ==========================================
        const CONFIG = {
            API_BASE_URL: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
                ? 'http://127.0.0.1:8000' 
                : 'https://api.consilium-ai.com',
            MAX_FILE_SIZE: 10 * 1024 * 1024,
            ALLOWED_FILE_TYPES: ['text/plain', 'application/pdf', 'image/jpeg', 'image/png', 'image/gif', 'audio/mpeg', 'audio/wav'],
            DEBOUNCE_DELAY: 300,
            MAX_CHAT_HISTORY: 50,
            TYPING_SPEED: 30,
        };
