        // ==========================================
        // CONFIGURATION
        // ==========================================
        const CONFIG = {
            API_BASE_URL: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
                ? 'http://127.0.0.1:8000' 
                : 'https://api.consilium-ai.com',
            MAX_FILE_SIZE: 10 * 1024 * 1024,
            ALLOWED_FILE_TYPES: ['text/plain', 'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'image/png', 'image/jpeg', 'image/gif', 'audio/mpeg', 'audio/wav', 'audio/mp4'],
            MAX_STORAGE_SIZE: 4.5 * 1024 * 1024,
            DEBOUNCE_DELAY: 300,
            CHAT_ID_PREFIX: 'chat_',
            REQUEST_TIMEOUT: 300000,    // 300 s — для auth / misc запросов
            CHAT_TIMEOUT: 0,            // 0 = без таймаута для /chat (Ollama медленная)
            DEMO_MODE: false
        };

        // ==========================================
        // STATE MANAGEMENT
        // ==========================================
        const state = {
            currentUserId: null,
            currentChatId: null,
            isRegisterMode: false,
            selectedFiles: [],
            isRecording: false,
            mediaRecorder: null,
            currentTheme: 'light',
            currentLanguage: 'pl',
            nightShift: false,
            fontSize: 16,
            currentModel: 'gpt-4',
            credits: 0,
            isSidebarOpen: false,
            abortController: null,
            chatHistory: new Map(),
            pendingSave: null,
            isDemoMode: false,
			// --- НОВЫЕ ПЕРЕМЕННЫЕ ДЛЯ PROTOCOL v3.0 ---
            councilSocket: null,      // Хранит объект WebSocket
            lastSentMsgId: null       // Связывает шаги протокола с конкретным запросом
        };

        // ==========================================
        // DEMO MODE AI RESPONSES
        // ==========================================
        const DemoAI = {
            responses: {
                pl: [
                    "Cześć! Jestem w trybie demo, więc moje odpowiedzi są symulowane. W pełnej wersji połączę się z prawdziwym modelem AI.",
                    "To ciekawe pytanie! W trybie demo mogę pokazać jak działa interfejs, ale nie mam dostępu do prawdziwej bazy wiedzy.",
                    "Rozumiem Twoje pytanie. Wersja demo służy do testowania interfejsu. Połącz się z serwerem, aby uzyskać pełną funkcjonalność.",
                    "Jako asystent demo mogę potwierdzić, że Twoja wiadomość została odebrana poprawnie. System działa!",
                    "To jest symulowana odpowiedź. W rzeczywistej aplikacji tutaj pojawiłaby się inteligentna odpowiedź od AI."
                ],
                en: [
                    "Hi! I'm in demo mode, so my responses are simulated. In the full version, I'll connect to a real AI model.",
                    "Interesting question! In demo mode I can show how the interface works, but I don't have access to real knowledge base.",
                    "I understand your question. The demo version is for testing the interface. Connect to the server for full functionality.",
                    "As a demo assistant, I can confirm that your message was received correctly. The system works!",
                    "This is a simulated response. In the actual application, an intelligent AI response would appear here."
                ],
                ru: [
                    "Привет! Я в демо-режиме, поэтому мои ответы симулированы. В полной версии я подключусь к реальной модели ИИ.",
                    "Интересный вопрос! В демо-режиме я могу показать, как работает интерфейс, но у меня нет доступа к реальной базе знаний.",
                    "Я понимаю ваш вопрос. Демо-версия для тестирования интерфейса. Подключитесь к серверу для полной функциональности.",
                    "Как демо-ассистент, я могу подтвердить, что ваше сообщение получено правильно. Система работает!",
                    "Это симулированный ответ. В реальном приложении здесь появился бы интеллектуальный ответ от ИИ."
                ],
                ua: [
                    "Привіт! Я в демо-режимі, тому мої відповіді симульовані. У повній версії я підключусь до реальної моделі ШІ.",
                    "Цікаве питання! У демо-режимі я можу показати, як працює інтерфейс, але я не маю доступу до реальної бази знань.",
                    "Я розумію ваше питання. Демо-версія для тестування інтерфейсу. Підключіться до сервера для повної функціональності.",
                    "Як демо-асистент, я можу підтвердити, що ваше повідомлення отримано правильно. Система працює!",
                    "Це симульована відповідь. У реальному додатку тут з'явилася б інтелектуальна відповідь від ШІ."
                ]
            },
            
            getResponse: (input) => {
                const langResponses = DemoAI.responses[state.currentLanguage] || DemoAI.responses.pl;
                // Simple hash to get consistent but varied responses
                const hash = input.split('').reduce((a, b) => a + b.charCodeAt(0), 0);
                return langResponses[hash % langResponses.length];
            },
            
            processFile: (filename) => {
                const responses = {
                    pl: `Odebrałem plik "${filename}". W trybie demo nie mogę analizować zawartości plików, ale interfejs działa poprawnie!`,
                    en: `Received file "${filename}". In demo mode I cannot analyze file contents, but the interface works correctly!`,
                    ru: `Получен файл "${filename}". В демо-режиме я не могу анализировать содержимое файлов, но интерфейс работает корректно!`,
                    ua: `Отримано файл "${filename}". У демо-режимі я не можу аналізувати вміст файлів, але інтерфейс працює коректно!`
                };
                return responses[state.currentLanguage] || responses.pl;
            }
        };

        // ==========================================
        // SECURITY UTILITIES
        // ==========================================
        const SecurityUtils = {
            escapeHtml: (unsafe) => {
                if (typeof unsafe !== 'string') return '';
                const div = document.createElement('div');
                div.textContent = unsafe;
                return div.innerHTML;
            },

            validateEmail: (email) => {
                const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                return re.test(String(email).toLowerCase().trim());
            },

            validatePassword: (password) => {
                return password && password.length >= 6 && password.trim().length >= 6;
            },

            generateCSRFToken: () => {
                const array = new Uint8Array(32);
                crypto.getRandomValues(array);
                return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
            },

            getCSRFToken: () => {
                let token = sessionStorage.getItem('csrf_token');
                if (!token) {
                    token = SecurityUtils.generateCSRFToken();
                    sessionStorage.setItem('csrf_token', token);
                }
                return token;
            },

            generateChatId: () => {
                return CONFIG.CHAT_ID_PREFIX + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            }
        };

        // ==========================================
        // LOCALIZATION
        // ==========================================
        const i18n = {
            pl: {
                authSubtitle: 'Zaloguj się, aby kontynuować',
                email: 'Email',
                password: 'Hasło',
                confirmPassword: 'Potwierdź hasło',
                login: 'Zaloguj się',
                register: 'Zarejestruj się',
                noAccount: 'Nie masz konta? Zarejestruj się',
                hasAccount: 'Masz już konto? Zaloguj się',
                online: 'Online',
                offline: 'Offline (Demo)',
                credits: 'kredytów',
                newChat: 'Nowy czat',
                clearHistory: 'Wyczyść historię',
                welcome: 'Jak mogę Ci pomóc?',
                welcomeDesc: 'Zadaj pytanie, prześlij plik lub wklej tekst do analizy. Jestem tutaj, aby pomóc Ci w każdym zadaniu.',
                suggestion1: 'Napisz profesjonalny email',
                suggestion2: 'Wyjaśnij złożony temat',
                suggestion3: 'Przeanalizuj kod',
                suggestion4: 'Zaplanuj projekt',
                messagePlaceholder: 'Napisz wiadomość...',
                disclaimer: 'Consilium AI może popełniać błędy. Sprawdź ważne informacje.',
                settings: 'Ustawienia',
                language: 'Język',
                theme: 'Motyw',
                light: 'Jasny',
                dark: 'Ciemny',
                sepia: 'Sepia',
                midnight: 'Nocny',
                nightShift: 'Tryb nocny',
                nightShiftDesc: 'Cieplejsze barwy dla oczu',
                fontSize: 'Rozmiar czcionki',
                model: 'Model AI',
                exportChat: 'Eksportuj czat',
                buyCredits: 'Kup kredyty',
                popular: 'Popularne',
                selectOption: 'Wybierz opcję',
                confirmClearHistory: 'Czy na pewno chcesz wyczyścić całą historię?',
                confirmDeleteChat: 'Czy na pewno chcesz usunąć ten czat?',
                emptyFields: 'Wypełnij wszystkie pola!',
                invalidEmail: 'Nieprawidłowy format email',
                passwordTooShort: 'Hasło musi mieć min. 6 znaków',
                passwordsMismatch: 'Hasła nie są identyczne',
                serverError: 'Błąd serwera. Spróbuj ponownie.',
                connectionError: 'Brak połączenia z serwerem. Spróbuj ponownie później lub użyj trybu demo.',
                copied: 'Skopiowano!',
                fileTooLarge: 'Plik jest za duży (max 10MB)',
                invalidFileType: 'Nieprawidłowy typ pliku',
                storageFull: 'Pamięć lokalna jest pełna. Usuń stare czaty.',
                confirmPurchase: 'Zakup potwierdzony!',
                purchaseError: 'Błąd zakupu. Spróbuj ponownie.',
                assistant: 'Asystent',
                you: 'Ty',
                chatHistory: 'Historia czatów',
                close: 'Zamknij',
                send: 'Wyślij',
                attachFile: 'Załącz plik',
                voiceInput: 'Wprowadzanie głosowe',
                thinking: 'Myślę...',
                error: 'Błąd',
                retry: 'Spróbuj ponownie',
                demoMode: 'Tryb Demo',
                demoModeDesc: 'Praca offline - dane zapisywane lokalnie',
                serverUnavailable: 'Serwer niedostępny. Sprawdź czy backend jest uruchomiony na http://127.0.0.1:8000'
            },
            en: {
                authSubtitle: 'Sign in to continue',
                email: 'Email',
                password: 'Password',
                confirmPassword: 'Confirm Password',
                login: 'Sign In',
                register: 'Sign Up',
                noAccount: "Don't have an account? Sign Up",
                hasAccount: 'Already have an account? Sign In',
                online: 'Online',
                offline: 'Offline (Demo)',
                credits: 'credits',
                newChat: 'New Chat',
                clearHistory: 'Clear History',
                welcome: 'How can I help you?',
                welcomeDesc: 'Ask a question, upload a file, or paste text for analysis. I am here to help you with any task.',
                suggestion1: 'Write a professional email',
                suggestion2: 'Explain a complex topic',
                suggestion3: 'Analyze code',
                suggestion4: 'Plan a project',
                messagePlaceholder: 'Type a message...',
                disclaimer: 'Consilium AI can make mistakes. Verify important information.',
                settings: 'Settings',
                language: 'Language',
                theme: 'Theme',
                light: 'Light',
                dark: 'Dark',
                sepia: 'Sepia',
                midnight: 'Midnight',
                nightShift: 'Night Shift',
                nightShiftDesc: 'Warmer colors for your eyes',
                fontSize: 'Font Size',
                model: 'AI Model',
                exportChat: 'Export Chat',
                buyCredits: 'Buy Credits',
                popular: 'Popular',
                selectOption: 'Select option',
                confirmClearHistory: 'Are you sure you want to clear all history?',
                confirmDeleteChat: 'Are you sure you want to delete this chat?',
                emptyFields: 'Please fill all fields!',
                invalidEmail: 'Invalid email format',
                passwordTooShort: 'Password must be at least 6 characters',
                passwordsMismatch: 'Passwords do not match',
                serverError: 'Server error. Please try again.',
                connectionError: 'Cannot connect to server. Try again later or use demo mode.',
                copied: 'Copied!',
                fileTooLarge: 'File too large (max 10MB)',
                invalidFileType: 'Invalid file type',
                storageFull: 'Local storage is full. Delete old chats.',
                confirmPurchase: 'Purchase confirmed!',
                purchaseError: 'Purchase error. Please try again.',
                assistant: 'Assistant',
                you: 'You',
                chatHistory: 'Chat History',
                close: 'Close',
                send: 'Send',
                attachFile: 'Attach file',
                voiceInput: 'Voice input',
                thinking: 'Thinking...',
                error: 'Error',
                retry: 'Retry',
                demoMode: 'Demo Mode',
                demoModeDesc: 'Working offline - data saved locally',
                serverUnavailable: 'Server unavailable. Check if backend is running at http://127.0.0.1:8000'
            },
            ru: {
                authSubtitle: 'Войдите, чтобы продолжить',
                email: 'Email',
                password: 'Пароль',
                confirmPassword: 'Подтвердите пароль',
                login: 'Войти',
                register: 'Зарегистрироваться',
                noAccount: 'Нет аккаунта? Зарегистрируйтесь',
                hasAccount: 'Уже есть аккаунт? Войдите',
                online: 'Онлайн',
                offline: 'Оффлайн (Демо)',
                credits: 'кредитов',
                newChat: 'Новый чат',
                clearHistory: 'Очистить историю',
                welcome: 'Чем могу помочь?',
                welcomeDesc: 'Задайте вопрос, загрузите файл или вставьте текст для анализа. Я здесь, чтобы помочь вам с любой задачей.',
                suggestion1: 'Написать профессиональное письмо',
                suggestion2: 'Объяснить сложную тему',
                suggestion3: 'Проанализировать код',
                suggestion4: 'Спланировать проект',
                messagePlaceholder: 'Введите сообщение...',
                disclaimer: 'Consilium AI может совершать ошибки. Проверяйте важную информацию.',
                settings: 'Настройки',
                language: 'Язык',
                theme: 'Тема',
                light: 'Светлая',
                dark: 'Тёмная',
                sepia: 'Сепия',
                midnight: 'Полночь',
                nightShift: 'Ночной режим',
                nightShiftDesc: 'Тёплые цвета для глаз',
                fontSize: 'Размер шрифта',
                model: 'Модель ИИ',
                exportChat: 'Экспорт чата',
                buyCredits: 'Купить кредиты',
                popular: 'Популярное',
                selectOption: 'Выберите опцию',
                confirmClearHistory: 'Вы уверены, что хотите очистить всю историю?',
                confirmDeleteChat: 'Вы уверены, что хотите удалить этот чат?',
                emptyFields: 'Заполните все поля!',
                invalidEmail: 'Неверный формат email',
                passwordTooShort: 'Пароль должен быть минимум 6 символов',
                passwordsMismatch: 'Пароли не совпадают',
                serverError: 'Ошибка сервера. Попробуйте снова.',
                connectionError: 'Нет соединения с сервером. Попробуйте позже или используйте демо-режим.',
                copied: 'Скопировано!',
                fileTooLarge: 'Файл слишком большой (макс. 10МБ)',
                invalidFileType: 'Неверный тип файла',
                storageFull: 'Локальное хранилище заполнено. Удалите старые чаты.',
                confirmPurchase: 'Покупка подтверждена!',
                purchaseError: 'Ошибка покупки. Попробуйте снова.',
                assistant: 'Ассистент',
                you: 'Вы',
                chatHistory: 'История чатов',
                close: 'Закрыть',
                send: 'Отправить',
                attachFile: 'Прикрепить файл',
                voiceInput: 'Голосовой ввод',
                thinking: 'Думаю...',
                error: 'Ошибка',
                retry: 'Повторить',
                demoMode: 'Демо-режим',
                demoModeDesc: 'Работа оффлайн - данные сохраняются локально',
                serverUnavailable: 'Сервер недоступен. Проверьте, запущен ли бэкенд на http://127.0.0.1:8000'
            },
            ua: {
                authSubtitle: 'Увійдіть, щоб продовжити',
                email: 'Email',
                password: 'Пароль',
                confirmPassword: 'Підтвердіть пароль',
                login: 'Увійти',
                register: 'Зареєструватися',
                noAccount: 'Немає акаунту? Зареєструйтеся',
                hasAccount: 'Вже є акаунт? Увійдіть',
                online: 'Онлайн',
                offline: 'Офлайн (Демо)',
                credits: 'кредитів',
                newChat: 'Новий чат',
                clearHistory: 'Очистити історію',
                welcome: 'Чим можу допомогти?',
                welcomeDesc: 'Задайте питання, завантажте файл або вставте текст для аналізу. Я тут, щоб допомогти вам з будь-яким завданням.',
                suggestion1: 'Написати професійний лист',
                suggestion2: 'Пояснити складну тему',
                suggestion3: 'Проаналізувати код',
                suggestion4: 'Спланувати проект',
                messagePlaceholder: 'Введіть повідомлення...',
                disclaimer: 'Consilium AI може помилятися. Перевіряйте важливу інформацію.',
                settings: 'Налаштування',
                language: 'Мова',
                theme: 'Тема',
                light: 'Світла',
                dark: 'Темна',
                sepia: 'Сепія',
                midnight: 'Північ',
                nightShift: 'Нічний режим',
                nightShiftDesc: 'Теплі кольори для очей',
                fontSize: 'Розмір шрифту',
                model: 'Модель ШІ',
                exportChat: 'Експорт чату',
                buyCredits: 'Купити кредити',
                popular: 'Популярне',
                selectOption: 'Виберіть опцію',
                confirmClearHistory: 'Ви впевнені, що хочете очистити всю історію?',
                confirmDeleteChat: 'Ви впевнені, що хочете видалити цей чат?',
                emptyFields: 'Заповніть всі поля!',
                invalidEmail: 'Невірний формат email',
                passwordTooShort: 'Пароль має бути мінімум 6 символів',
                passwordsMismatch: 'Паролі не співпадають',
                serverError: 'Помилка сервера. Спробуйте знову.',
                connectionError: 'Немає з\'єднання з сервером. Спробуйте пізніше або використайте демо-режим.',
                copied: 'Скопійовано!',
                fileTooLarge: 'Файл занадто великий (макс. 10МБ)',
                invalidFileType: 'Невірний тип файлу',
                storageFull: 'Локальне сховище заповнене. Видаліть старі чати.',
                confirmPurchase: 'Покупку підтверджено!',
                purchaseError: 'Помилка покупки. Спробуйте знову.',
                assistant: 'Асистент',
                you: 'Ви',
                chatHistory: 'Історія чатів',
                close: 'Закрити',
                send: 'Надіслати',
                attachFile: 'Прикріпити файл',
                voiceInput: 'Голосове введення',
                thinking: 'Думаю...',
                error: 'Помилка',
                retry: 'Повторити',
                demoMode: 'Демо-режим',
                demoModeDesc: 'Робота офлайн - дані зберігаються локально',
                serverUnavailable: 'Сервер недоступний. Перевірте, чи запущено бекенд на http://127.0.0.1:8000'
            }
        };

        // ==========================================
        // DOM ELEMENTS CACHE
        // ==========================================
        const elements = {};

        // ==========================================
        // EVENT MANAGER
        // ==========================================
        const EventManager = {
            listeners: new Map(),
            
            add: (element, event, handler, options = {}) => {
                if (!element) return;
                element.addEventListener(event, handler, options);
                const key = element;
                if (!EventManager.listeners.has(key)) {
                    EventManager.listeners.set(key, []);
                }
                EventManager.listeners.get(key).push({ event, handler, options });
            },
            
            remove: (element, event, handler) => {
                if (!element) return;
                element.removeEventListener(event, handler);
                const key = element;
                if (EventManager.listeners.has(key)) {
                    const filtered = EventManager.listeners.get(key).filter(l => l.event !== event || l.handler !== handler);
                    EventManager.listeners.set(key, filtered);
                }
            },
            
            removeAll: (element) => {
                if (!element || !EventManager.listeners.has(element)) return;
                EventManager.listeners.get(element).forEach(({ event, handler, options }) => {
                    element.removeEventListener(event, handler, options);
                });
                EventManager.listeners.delete(element);
            }
        };

        // ==========================================
        // INITIALIZATION
        // ==========================================
        document.addEventListener('DOMContentLoaded', () => {
            cacheElements();
            initializeEventListeners();
            loadSettings();
            checkAuth();
            setupDragAndDrop();
        });

        function cacheElements() {
            const ids = [
                'authModal', 'authForm', 'authEmail', 'authPassword', 'authConfirmPassword', 
                'confirmPassField', 'authSubmitBtn', 'toggleAuthMode', 'emailError', 'passwordError', 'confirmPasswordError',
                'menuBtn', 'sidebar', 'sidebarOverlay', 'newChatBtn', 'chatHistoryList', 'clearHistoryBtn',
                'chatBox', 'emptyState', 'messageInput', 'sendBtn', 'attachBtn', 'fileInput', 'voiceBtn',
                'filePreview', 'creditsDisplay', 'creditsAmount', 'buyCreditsBtn', 'settingsBtn', 'logoutBtn',
                'settingsPanel', 'closeSettings', 'settingsOverlay', 'languageSelect', 'nightShiftToggle',
                'fontSizeSlider', 'modelSelect', 'exportBtn', 'creditsModal', 'closeCreditsModal',
                'confirmPurchaseBtn', 'toast', 'toastIcon', 'toastMessage', 'demoBadge', 'connectionStatus',
                'serverErrorAlert', 'serverErrorText', 'demoModeBtn'
            ];
            
            ids.forEach(id => {
                elements[id] = document.getElementById(id);
            });
            
            elements.themeBtns = document.querySelectorAll('.theme-btn');
            elements.suggestionBtns = document.querySelectorAll('.suggestion-btn');
            elements.creditOptions = document.querySelectorAll('.credit-option');
        }

        function initializeEventListeners() {
            // Auth
            EventManager.add(elements.authForm, 'submit', handleAuth);
            EventManager.add(elements.toggleAuthMode, 'click', toggleAuthMode);
            EventManager.add(elements.authEmail, 'input', debounce(validateEmailInput, CONFIG.DEBOUNCE_DELAY));
            EventManager.add(elements.authPassword, 'input', debounce(validatePasswordInput, CONFIG.DEBOUNCE_DELAY));
            EventManager.add(elements.authConfirmPassword, 'input', debounce(validateConfirmPasswordInput, CONFIG.DEBOUNCE_DELAY));
            EventManager.add(elements.demoModeBtn, 'click', enableDemoMode);

            // Navigation
            EventManager.add(elements.menuBtn, 'click', toggleSidebar);
            EventManager.add(elements.sidebarOverlay, 'click', closeSidebar);
            EventManager.add(elements.newChatBtn, 'click', startNewChat);
            EventManager.add(elements.clearHistoryBtn, 'click', clearAllHistory);

            // Chat
            EventManager.add(elements.sendBtn, 'click', sendQuery);
            EventManager.add(elements.messageInput, 'keydown', handleInputKeydown);
            EventManager.add(elements.messageInput, 'input', autoResizeTextarea);
            EventManager.add(elements.attachBtn, 'click', () => elements.fileInput.click());
            EventManager.add(elements.fileInput, 'change', handleFileSelect);
            EventManager.add(elements.voiceBtn, 'click', toggleVoiceRecording);

            // Header
            EventManager.add(elements.buyCreditsBtn, 'click', () => openModal(elements.creditsModal));
            EventManager.add(elements.closeCreditsModal, 'click', () => closeModal(elements.creditsModal));
            EventManager.add(elements.settingsBtn, 'click', openSettings);
            EventManager.add(elements.closeSettings, 'click', closeSettings);
            EventManager.add(elements.settingsOverlay, 'click', closeSettings);
            EventManager.add(elements.logoutBtn, 'click', logout);

            // Settings
            EventManager.add(elements.languageSelect, 'change', changeLanguage);
            EventManager.add(elements.nightShiftToggle, 'click', toggleNightShift);
            EventManager.add(elements.fontSizeSlider, 'input', changeFontSize);
            EventManager.add(elements.modelSelect, 'change', changeModel);
            EventManager.add(elements.exportBtn, 'click', exportChat);

            elements.themeBtns.forEach(btn => {
                EventManager.add(btn, 'click', () => changeTheme(btn.dataset.theme));
            });

            elements.suggestionBtns.forEach(btn => {
                EventManager.add(btn, 'click', () => {
                    elements.messageInput.value = btn.dataset.prompt;
                    autoResizeTextarea();
                    elements.messageInput.focus();
                });
            });

            elements.creditOptions.forEach(btn => {
                EventManager.add(btn, 'click', selectCreditOption);
            });

            EventManager.add(elements.confirmPurchaseBtn, 'click', buyCredits);

            // Global keyboard shortcuts
            EventManager.add(document, 'keydown', handleGlobalKeydown);

            // Visibility change for saving state
            EventManager.add(document, 'visibilitychange', handleVisibilityChange);

            // Before unload
            EventManager.add(window, 'beforeunload', handleBeforeUnload);
        }

        // ==========================================
        // DEMO MODE
        // ==========================================
        function enableDemoMode() {
            state.isDemoMode = true;
            state.currentUserId = 'demo_user_' + Date.now();
            state.credits = Infinity;
            
            elements.demoBadge.classList.remove('hidden');
            elements.connectionStatus.textContent = i18n[state.currentLanguage].offline;
            elements.connectionStatus.classList.add('text-yellow-500');
            elements.creditsAmount.textContent = '∞';
            
            closeModal(elements.authModal);
            loadChatHistory();
            showToast(i18n[state.currentLanguage].demoMode + ' - ' + i18n[state.currentLanguage].demoModeDesc, 'success');
        }

        // ==========================================
        // AUTHENTICATION
        // ==========================================
        async function handleAuth(e) {
            e.preventDefault();
            
            // Hide previous error
            elements.serverErrorAlert.classList.add('hidden');
            
            const email = elements.authEmail.value.trim();
            const password = elements.authPassword.value;
            const confirmPassword = elements.authConfirmPassword.value;

            // Validation
            if (!email || !password || (state.isRegisterMode && !confirmPassword)) {
                showToast(i18n[state.currentLanguage].emptyFields, 'error');
                return;
            }

            if (!SecurityUtils.validateEmail(email)) {
                showToast(i18n[state.currentLanguage].invalidEmail, 'error');
                elements.authEmail.focus();
                return;
            }

            if (!SecurityUtils.validatePassword(password)) {
                showToast(i18n[state.currentLanguage].passwordTooShort, 'error');
                elements.authPassword.focus();
                return;
            }

            if (state.isRegisterMode && password !== confirmPassword) {
                showToast(i18n[state.currentLanguage].passwordsMismatch, 'error');
                elements.authConfirmPassword.focus();
                return;
            }

            const endpoint = state.isRegisterMode ? '/register' : '/login';
            const csrfToken = SecurityUtils.getCSRFToken();

            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT);
                
                const response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    },
                    credentials: 'include',
                    body: JSON.stringify({ email, password }),
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);

                if (response.ok) {
                    const data = await response.json();
                    state.currentUserId = String(data.user_id);
                    state.isDemoMode = false;
                    localStorage.setItem('consilium_user_id', state.currentUserId);
                    localStorage.setItem('consilium_token', data.token);
                    elements.demoBadge.classList.add('hidden');
                    elements.connectionStatus.textContent = i18n[state.currentLanguage].online;
                    elements.connectionStatus.classList.remove('text-yellow-500');
                    closeModal(elements.authModal);
                    loadChatHistory();
                    refreshCredits();
                    showToast(i18n[state.currentLanguage].login, 'success');
                } else {
                    const errorData = await response.json().catch(() => ({}));
                    const errorMsg = errorData.message || i18n[state.currentLanguage].serverError;
                    elements.serverErrorText.textContent = errorMsg;
                    elements.serverErrorAlert.classList.remove('hidden');
                    showToast(errorMsg, 'error');
                }
            } catch (error) {
                console.error('Auth error:', error);
                let errorMsg = i18n[state.currentLanguage].connectionError;
                
                if (error.name === 'AbortError') {
                    errorMsg = 'Przekroczono czas oczekiwania na serwer';
                } else if (error.message && error.message.includes('Failed to fetch')) {
                    errorMsg = i18n[state.currentLanguage].serverUnavailable;
                }
                
                elements.serverErrorText.textContent = errorMsg;
                elements.serverErrorAlert.classList.remove('hidden');
                showToast(errorMsg, 'error');
            }
        }

        function toggleAuthMode() {
            state.isRegisterMode = !state.isRegisterMode;
            elements.confirmPassField.classList.toggle('hidden', !state.isRegisterMode);
            elements.authSubmitBtn.innerHTML = `<span>${i18n[state.currentLanguage][state.isRegisterMode ? 'register' : 'login']}</span>`;
            elements.toggleAuthMode.textContent = i18n[state.currentLanguage][state.isRegisterMode ? 'hasAccount' : 'noAccount'];
            elements.authForm.reset();
            clearValidationErrors();
            elements.serverErrorAlert.classList.add('hidden');
        }

        function validateEmailInput() {
            const email = elements.authEmail.value.trim();
            const isValid = SecurityUtils.validateEmail(email);
            elements.emailError.classList.toggle('hidden', isValid || !email);
            return isValid;
        }

        function validatePasswordInput() {
            const password = elements.authPassword.value;
            const isValid = SecurityUtils.validatePassword(password);
            elements.passwordError.classList.toggle('hidden', isValid || !password);
            return isValid;
        }

        function validateConfirmPasswordInput() {
            const password = elements.authPassword.value;
            const confirmPassword = elements.authConfirmPassword.value;
            const isValid = password === confirmPassword;
            elements.confirmPasswordError.classList.toggle('hidden', isValid || !confirmPassword);
            return isValid;
        }

        function clearValidationErrors() {
            elements.emailError.classList.add('hidden');
            elements.passwordError.classList.add('hidden');
            elements.confirmPasswordError.classList.add('hidden');
        }

        function checkAuth() {
            const userId = localStorage.getItem('consilium_user_id');
            const token = localStorage.getItem('consilium_token');
            
            if (userId && token && !userId.startsWith('demo_')) {
                // Verify token is still valid
                verifyToken(token).then(valid => {
                    if (valid) {
                        state.currentUserId = userId;
                        closeModal(elements.authModal);
                        loadChatHistory();
                        refreshCredits();
                    } else {
                        logout();
                    }
                }).catch(() => {
                    // If verification fails, show auth modal but keep data
                    openModal(elements.authModal);
                });
            } else if (userId && userId.startsWith('demo_')) {
                // Restore demo mode
                enableDemoMode();
            } else {
                openModal(elements.authModal);
            }
        }

        async function verifyToken(token) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000);
                
                const response = await fetch(`${CONFIG.API_BASE_URL}/verify`, {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'X-CSRF-Token': SecurityUtils.getCSRFToken()
                    },
                    credentials: 'include',
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                return response.ok;
            } catch (error) {
                return false;
            }
        }

        function logout() {
            // Cleanup
            state.currentUserId = null;
            state.currentChatId = null;
            state.selectedFiles = [];
            state.chatHistory.clear();
            state.isDemoMode = false;
            
            // Clear storage
            localStorage.removeItem('consilium_user_id');
            localStorage.removeItem('consilium_token');
            localStorage.removeItem('consilium_histories');
            sessionStorage.removeItem('csrf_token');
            
            // Clear UI
            elements.chatBox.innerHTML = '';
            elements.chatHistoryList.innerHTML = '';
            elements.filePreview.innerHTML = '';
            elements.filePreview.classList.add('hidden');
            elements.messageInput.value = '';
            elements.demoBadge.classList.add('hidden');
            
            showEmptyState();
            openModal(elements.authModal);
        }

        // ==========================================
        // CHAT MANAGEMENT
        // ==========================================
        function startNewChat() {
            if (state.currentChatId && elements.chatBox.children.length > 0) {
                saveCurrentChat();
            }
            
            state.currentChatId = SecurityUtils.generateChatId();
            elements.chatBox.innerHTML = '';
            showChatInterface();
            closeSidebar();
            elements.messageInput.focus();
        }

        function showEmptyState() {
            elements.emptyState.classList.remove('hidden');
            elements.chatBox.classList.add('hidden');
            state.currentChatId = null;
        }

        function showChatInterface() {
            elements.emptyState.classList.add('hidden');
            elements.chatBox.classList.remove('hidden');
        }

        // ==========================================
        // LIVE PROTOCOL UI (v3.0 Superpowers)
        // ==========================================
        function renderLiveProtocol(msgId) {
            const protocolHtml = `
                <div id="protocol-container-${msgId}" class="protocol-card mb-6 mt-2">
                    <div class="flex justify-between items-center mb-4 opacity-50">
                        <span class="text-[9px] uppercase tracking-[0.3em] font-mono">Cognitive Protocol v3.0</span>
                        <span class="text-[9px] animate-pulse text-indigo-400">● ACI_ACTIVE</span>
                    </div>
                    <div class="protocol-steps-wrapper space-y-3">
                        <div id="step-classifier-${msgId}" class="protocol-step">
                            <i class="fas fa-bullseye mt-1 text-[10px]"></i>
                            <div><div class="step-label">Discovery</div><div class="step-info">Анализ интента...</div></div>
                        </div>
                        <div id="step-scout-${msgId}" class="protocol-step">
                            <i class="fas fa-search mt-1 text-[10px]"></i>
                            <div><div class="step-label">Evidence</div><div class="step-info">Ожидание...</div></div>
                        </div>
                        <div id="step-analyst-${msgId}" class="protocol-step">
                            <i class="fas fa-chart-line mt-1 text-[10px]"></i>
                            <div><div class="step-label">Analysis</div><div class="step-info">Ожидание...</div></div>
                        </div>
                        <div id="step-architect-${msgId}" class="protocol-step">
                            <i class="fas fa-drafting-compass mt-1 text-[10px]"></i>
                            <div><div class="step-label">Architecture</div><div class="step-info">Ожидание...</div></div>
                        </div>
                        <div id="step-devil-${msgId}" class="protocol-step">
                            <i class="fas fa-biohazard mt-1 text-[10px]"></i>
                            <div><div class="step-label">Verification</div><div class="step-info">Ожидание...</div></div>
                        </div>
                        <div id="step-chairman-${msgId}" class="protocol-step">
                            <i class="fas fa-gavel mt-1 text-[10px]"></i>
                            <div><div class="step-label">Final Verdict</div><div class="step-info">Ожидание...</div></div>
                        </div>
                    </div>
                </div>
            `;
            elements.chatBox.insertAdjacentHTML('beforeend', protocolHtml);
            scrollToBottom();
        }

        // ==========================================
        // MESSAGE HANDLING
        // ==========================================
        function appendMessage(role, text, isError = false) {
            if (!text) return;
            
            const msgDiv = document.createElement('div');
            msgDiv.className = `flex gap-4 ${role === 'user' ? 'flex-row-reverse' : ''} message-anim`;
            
            const avatar = role === 'user' 
                ? `<div class="w-8 h-8 rounded-full bg-accent-theme flex items-center justify-center text-white text-sm font-bold shrink-0" aria-hidden="true">${i18n[state.currentLanguage].you.charAt(0)}</div>`
                : `<div class="w-8 h-8 rounded-full bg-theme-tertiary flex items-center justify-center accent-theme shrink-0" aria-hidden="true"><i class="fas fa-robot"></i></div>`;
            
            const safeText = SecurityUtils.escapeHtml(text);
            const formattedText = formatMessageText(safeText);

            // Кнопки действий — только для ответов ИИ
            const actionBtns = role === 'assistant' ? `
                <div class="msg-action-row flex items-center gap-0.5 mt-2">
                    <button class="action-btn copy-btn p-1.5 rounded hover:bg-theme-tertiary transition-colors text-theme-tertiary hover:text-theme-primary" title="Копировать">
                        <i class="far fa-copy text-xs" aria-hidden="true"></i>
                    </button>
                    <button class="action-btn share-btn p-1.5 rounded hover:bg-theme-tertiary transition-colors text-theme-tertiary hover:text-theme-primary" title="Поделиться">
                        <i class="fas fa-share-alt text-xs" aria-hidden="true"></i>
                    </button>
                    <span class="w-px h-3 bg-theme-tertiary mx-0.5 opacity-40"></span>
                    <button class="action-btn like-btn p-1.5 rounded hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors text-theme-tertiary" title="Нравится">
                        <i class="far fa-thumbs-up text-xs" aria-hidden="true"></i>
                    </button>
                    <button class="action-btn dislike-btn p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors text-theme-tertiary" title="Не нравится">
                        <i class="far fa-thumbs-down text-xs" aria-hidden="true"></i>
                    </button>
                </div>
            ` : '';
            
            const content = role === 'user'
                // Пользователь: лёгкий голубоватый фон, пузырь справа
                ? `<div class="flex-1 max-w-3xl text-right">
                       <div class="inline-block text-left px-4 py-3 rounded-2xl rounded-br-md text-theme-primary text-sm leading-relaxed"
                            style="background: rgba(59,130,246,0.10); border: 1px solid rgba(59,130,246,0.18);">
                           <div class="content markdown-content">${formattedText}</div>
                       </div>
                       <div class="flex justify-end items-center gap-0.5 mt-1">
                           <span class="text-xs text-theme-tertiary mr-1">${new Date().toLocaleTimeString()}</span>
                           <button class="action-btn user-copy-btn p-1.5 rounded hover:bg-theme-tertiary transition-colors text-theme-tertiary hover:text-theme-primary" title="Копировать">
                               <i class="far fa-copy text-xs" aria-hidden="true"></i>
                           </button>
                           <button class="action-btn user-edit-btn p-1.5 rounded hover:bg-theme-tertiary transition-colors text-theme-tertiary hover:text-theme-primary" title="Редактировать">
                               <i class="far fa-edit text-xs" aria-hidden="true"></i>
                           </button>
                           <button class="action-btn user-retry-btn p-1.5 rounded hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors text-theme-tertiary hover:text-blue-500" title="Повторить">
                               <i class="fas fa-redo text-xs" aria-hidden="true"></i>
                           </button>
                       </div>
                   </div>`
                // ИИ: плоский текст, без пузыря
                : `<div class="flex-1 max-w-3xl ${isError ? 'opacity-80' : ''}">
                       <div class="content text-sm leading-relaxed markdown-content text-theme-primary
                                   ${isError ? 'text-red-500 dark:text-red-400' : ''}
                                   py-1">
                           ${formattedText}
                       </div>
                       <div class="flex items-center gap-1 mt-0.5">
                           <span class="text-xs text-theme-tertiary">${new Date().toLocaleTimeString()}</span>
                           ${actionBtns}
                       </div>
                   </div>`;
            
            msgDiv.innerHTML = avatar + content;
            
            if (role === 'assistant') {
                EventManager.add(msgDiv.querySelector('.copy-btn'),    'click', () => copyToClipboard(text));
                EventManager.add(msgDiv.querySelector('.share-btn'),   'click', () => shareMessage(text));
                EventManager.add(msgDiv.querySelector('.like-btn'),    'click', (e) => toggleReaction(e.currentTarget, 'like'));
                EventManager.add(msgDiv.querySelector('.dislike-btn'), 'click', (e) => toggleReaction(e.currentTarget, 'dislike'));
            }
            if (role === 'user') {
                EventManager.add(msgDiv.querySelector('.user-copy-btn'),  'click', () => copyToClipboard(text));
                EventManager.add(msgDiv.querySelector('.user-edit-btn'),  'click', () => editMessage(text));
                EventManager.add(msgDiv.querySelector('.user-retry-btn'), 'click', () => retryMessage(text));
            }
            
            elements.chatBox.appendChild(msgDiv);
            scrollToBottom();
        }

        function formatMessageText(text) {
            return text
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/`(.*?)`/g, '<code>$1</code>')
                .replace(/\n/g, '<br>');
        }

        // ── Карточка «Протокол совета» ──────────────────────────────────────
        function appendCouncilCard(councilUsed, costUsd, deliberation) {
            if (!councilUsed || councilUsed.length === 0) return;
            deliberation = deliberation || {};
 
            const meta = {
                scout:       { icon: 'fa-search',               label: 'Scout',       role: 'Сбор фактов',            color: '#3b82f6',
                               defaultThought: 'Проанализировал доступные источники, извлёк ключевые факты по теме запроса.' },
                analyst:     { icon: 'fa-chart-bar',            label: 'Analyst',     role: 'Структурный анализ',      color: '#8b5cf6',
                               defaultThought: 'Систематизировал данные, выявил паттерны и логические зависимости.' },
                architect:   { icon: 'fa-drafting-compass',     label: 'Architect',   role: 'Проектирование',          color: '#f59e0b',
                               defaultThought: 'Спроектировал структуру решения, оценил варианты реализации.' },
                devil:       { icon: 'fa-exclamation-triangle', label: "Devil's",     role: 'Поиск рисков',            color: '#ef4444',
                               defaultThought: 'Проверил допущения совета, выявил потенциальные риски и слабые места.' },
                chairman:    { icon: 'fa-gavel',                label: 'Chairman',    role: 'Финальное решение',       color: '#10b981',
                               defaultThought: 'Синтезировал мнения директоров и принял взвешенное финальное решение.' },
                synthesizer: { icon: 'fa-brain',                label: 'Synthesizer', role: 'Мета-анализ',             color: '#6366f1',
                               defaultThought: 'Провёл мета-анализ согласованности совета, оценил когерентность решения.' },
                operator:    { icon: 'fa-tools',                label: 'Operator',    role: 'План действий',           color: '#f97316',
                               defaultThought: 'Разработал детальный план исполнения с чёткими шагами.' },
                translator:  { icon: 'fa-globe',                label: 'Translator',  role: 'Адаптация',               color: '#06b6d4',
                               defaultThought: 'Адаптировал ответ под язык и контекст пользователя.' },
            };
 
            // Строки трейса директоров
            const rowsHtml = councilUsed.map((id, i) => {
                const m = meta[id] || { icon: 'fa-user', label: id, role: '', color: '#94a3b8', defaultThought: '' };
                const isLast = i === councilUsed.length - 1;
 
                // Берём реальный превью из deliberation, если есть
                const dData    = deliberation[id] || {};
                const preview  = dData.preview
                    ? dData.preview.replace(/\[/g, '').replace(/\]/g, '').replace(/\.\.\.$/, '').trim()
                    : m.defaultThought;
                const tokens   = dData.tokens ? `${dData.tokens} tok` : '';
                const provider = dData.model || '';
 
                return `
                <div class="council-trace-row ${!isLast ? 'border-b border-theme/30' : ''} py-2.5">
                    <div class="flex items-start gap-3">
                        <!-- Иконка директора -->
                        <div class="flex flex-col items-center shrink-0">
                            <div class="w-6 h-6 rounded-full flex items-center justify-center"
                                 style="background:${m.color}15; border:1px solid ${m.color}35">
                                <i class="fas ${m.icon} text-[9px]" style="color:${m.color}"></i>
                            </div>
                            ${!isLast ? `<div class="w-px mt-1 flex-1" style="background:${m.color}25; min-height:14px"></div>` : ''}
                        </div>
                        <!-- Контент -->
                        <div class="flex-1 min-w-0">
                            <!-- Имя + роль + мета -->
                            <div class="flex items-center gap-2 mb-1">
                                <span class="text-xs font-bold" style="color:${m.color}">${m.label}</span>
                                <span class="text-[10px] text-theme-tertiary">·</span>
                                <span class="text-[10px] text-theme-tertiary">${m.role}</span>
                                ${tokens ? `<span class="text-[10px] text-theme-tertiary ml-auto opacity-50">${tokens}</span>` : ''}
                            </div>
                            <!-- Текст рассуждения -->
                            <p class="text-xs text-theme-secondary leading-relaxed line-clamp-2">${preview}</p>
                        </div>
                        <!-- Статус -->
                        <div class="shrink-0 flex items-center gap-1 mt-0.5">
                            <i class="fas fa-check-circle text-[9px] text-green-500"></i>
                        </div>
                    </div>
                </div>`;
            }).join('');
 
            const costLabel = costUsd > 0
                ? `<span class="text-[10px] text-theme-tertiary opacity-50">· $${costUsd.toFixed(4)}</span>`
                : '';
 
            const cardDiv = document.createElement('div');
            cardDiv.className = 'flex gap-4 message-anim mb-1';
            cardDiv.innerHTML = `
                <div class="w-8 h-8 shrink-0"></div>
                <div class="flex-1 max-w-3xl">
                    <details class="council-trace-details group">
                        <summary class="council-summary flex items-center gap-1.5 cursor-pointer select-none
                                        text-theme-tertiary hover:text-theme-secondary transition-colors py-1">
                            <i class="fas fa-chevron-right council-chevron text-[8px]"></i>
                            <i class="fas fa-users text-[9px]"></i>
                            <span class="text-[11px] font-medium">Протокол совета · ${councilUsed.length} директора</span>
                            ${costLabel}
                        </summary>
                        <!-- Развёрнутый трейс -->
                        <div class="mt-2 px-3 py-1 rounded-xl border border-theme/60 bg-theme-secondary/20 council-trace-open">
                            ${rowsHtml}
                        </div>
                    </details>
                </div>
            `;
 
            elements.chatBox.appendChild(cardDiv);
            scrollToBottom();
        }

        // ── Поделиться ──────────────────────────────────────────────────────
        function shareMessage(text) {
            const snippet = text.length > 280 ? text.substring(0, 280) + '…' : text;
            if (navigator.share) {
                navigator.share({ title: 'Consilium AI', text: snippet }).catch(() => {});
            } else {
                copyToClipboard(text);
                showToast('Текст скопирован для отправки', 'success');
            }
        }

        // ── Реакции (нравится / не нравится) ────────────────────────────────
        function toggleReaction(btn, type) {
            const msgDiv = btn.closest('.flex.gap-4');
            const wasActive = btn.classList.contains('reaction-active');

            // Снимаем все реакции в этом сообщении
            if (msgDiv) {
                msgDiv.querySelectorAll('.like-btn, .dislike-btn').forEach(b => {
                    b.classList.remove('reaction-active');
                    const ico = b.querySelector('i');
                    if (ico) { ico.classList.replace('fas', 'far'); }
                });
            }

            if (!wasActive) {
                btn.classList.add('reaction-active');
                const ico = btn.querySelector('i');
                if (ico) { ico.classList.replace('far', 'fas'); }
                showToast(type === 'like' ? '👍 Спасибо за оценку!' : '👎 Учтём — постараемся лучше!', 'success');
            }
        }

        // ── Редактировать сообщение пользователя ────────────────────────────
        function editMessage(text) {
            elements.messageInput.value = text;
            autoResizeTextarea();
            elements.messageInput.focus();
            // Перемещаем курсор в конец
            const len = elements.messageInput.value.length;
            elements.messageInput.setSelectionRange(len, len);
        }

        // ── Повторить сообщение пользователя ────────────────────────────────
        async function retryMessage(text) {
            elements.messageInput.value = text;
            autoResizeTextarea();
            await sendQuery();
        }
        function createCouncilMessage() {
            const id = 'loading-' + Date.now();
            const msgDiv = document.createElement('div');
            msgDiv.id = id;
            msgDiv.className = 'flex gap-4 message-anim';
 
            msgDiv.innerHTML = `
                <div class="w-8 h-8 rounded-full bg-theme-tertiary flex items-center justify-center
                             accent-theme shrink-0" aria-hidden="true">
                    <i class="fas fa-robot"></i>
                </div>
 
                <div class="flex-1 max-w-3xl">
                    <div class="px-4 pt-3 pb-3 rounded-xl bg-theme-secondary border border-theme">
 
                        <!-- Заголовок -->
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center gap-2">
                                <span class="w-1.5 h-1.5 rounded-full bg-accent-theme animate-pulse"></span>
                                <span class="council-phase-text text-xs font-semibold text-theme-secondary">
                                    Совет собирается...
                                </span>
                            </div>
                            <button class="council-stop-btn text-[10px] text-theme-tertiary hover:text-red-500
                                           border border-theme/60 hover:border-red-300/60 px-2 py-0.5 rounded-md
                                           transition-all flex items-center gap-1">
                                <i class="fas fa-stop text-[8px]"></i> Стоп
                            </button>
                        </div>
 
                        <!-- Вертикальный список директоров -->
                        <div class="space-y-0 mb-3">
 
                            <div class="director-row flex items-center gap-2.5 py-1.5
                                        opacity-35 transition-all duration-500" data-director="scout">
                                <div class="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                                     style="background:#3b82f615; border:1px solid #3b82f635">
                                    <i class="fas fa-search text-[8px]" style="color:#3b82f6"></i>
                                </div>
                                <span class="text-[11px] font-bold shrink-0 w-[68px]" style="color:#3b82f6">Scout</span>
                                <div class="director-bar-wrap flex-1 h-0.5 bg-theme-tertiary/50 rounded-full overflow-hidden">
                                    <div class="director-bar h-full rounded-full transition-all duration-700"
                                         style="width:0%; background:#3b82f6"></div>
                                </div>
                                <div class="director-status-text text-[10px] text-theme-tertiary truncate w-40 shrink-0 text-right">
                                    ожидает...
                                </div>
                            </div>
 
                            <div class="director-row flex items-center gap-2.5 py-1.5
                                        opacity-35 transition-all duration-500" data-director="analyst">
                                <div class="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                                     style="background:#8b5cf615; border:1px solid #8b5cf635">
                                    <i class="fas fa-chart-bar text-[8px]" style="color:#8b5cf6"></i>
                                </div>
                                <span class="text-[11px] font-bold shrink-0 w-[68px]" style="color:#8b5cf6">Analyst</span>
                                <div class="director-bar-wrap flex-1 h-0.5 bg-theme-tertiary/50 rounded-full overflow-hidden">
                                    <div class="director-bar h-full rounded-full transition-all duration-700"
                                         style="width:0%; background:#8b5cf6"></div>
                                </div>
                                <div class="director-status-text text-[10px] text-theme-tertiary truncate w-40 shrink-0 text-right">
                                    ожидает...
                                </div>
                            </div>
 
                            <div class="director-row flex items-center gap-2.5 py-1.5
                                        opacity-35 transition-all duration-500" data-director="architect">
                                <div class="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                                     style="background:#f59e0b15; border:1px solid #f59e0b35">
                                    <i class="fas fa-drafting-compass text-[8px]" style="color:#f59e0b"></i>
                                </div>
                                <span class="text-[11px] font-bold shrink-0 w-[68px]" style="color:#f59e0b">Architect</span>
                                <div class="director-bar-wrap flex-1 h-0.5 bg-theme-tertiary/50 rounded-full overflow-hidden">
                                    <div class="director-bar h-full rounded-full transition-all duration-700"
                                         style="width:0%; background:#f59e0b"></div>
                                </div>
                                <div class="director-status-text text-[10px] text-theme-tertiary truncate w-40 shrink-0 text-right">
                                    ожидает...
                                </div>
                            </div>
 
                            <div class="director-row flex items-center gap-2.5 py-1.5
                                        opacity-35 transition-all duration-500" data-director="devil">
                                <div class="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                                     style="background:#ef444415; border:1px solid #ef444435">
                                    <i class="fas fa-exclamation-triangle text-[8px]" style="color:#ef4444"></i>
                                </div>
                                <span class="text-[11px] font-bold shrink-0 w-[68px]" style="color:#ef4444">Devil's</span>
                                <div class="director-bar-wrap flex-1 h-0.5 bg-theme-tertiary/50 rounded-full overflow-hidden">
                                    <div class="director-bar h-full rounded-full transition-all duration-700"
                                         style="width:0%; background:#ef4444"></div>
                                </div>
                                <div class="director-status-text text-[10px] text-theme-tertiary truncate w-40 shrink-0 text-right">
                                    ожидает...
                                </div>
                            </div>
 
                            <div class="director-row flex items-center gap-2.5 py-1.5
                                        opacity-35 transition-all duration-500" data-director="chairman">
                                <div class="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                                     style="background:#10b98115; border:1px solid #10b98135">
                                    <i class="fas fa-gavel text-[8px]" style="color:#10b981"></i>
                                </div>
                                <span class="text-[11px] font-bold shrink-0 w-[68px]" style="color:#10b981">Chairman</span>
                                <div class="director-bar-wrap flex-1 h-0.5 bg-theme-tertiary/50 rounded-full overflow-hidden">
                                    <div class="director-bar h-full rounded-full transition-all duration-700"
                                         style="width:0%; background:#10b981"></div>
                                </div>
                                <div class="director-status-text text-[10px] text-theme-tertiary truncate w-40 shrink-0 text-right">
                                    ожидает...
                                </div>
                            </div>
 
                        </div>
 
                        <!-- Глобальный прогресс-бар + процент -->
                        <div class="flex items-center gap-2 mt-1">
                            <div class="flex-1 h-1 bg-theme-tertiary/50 rounded-full overflow-hidden">
                                <div class="council-progress h-full rounded-full transition-all duration-1000"
                                     style="width:3%; background: var(--accent-primary)"></div>
                            </div>
                            <span class="council-percent text-[10px] text-theme-tertiary w-7 text-right shrink-0">3%</span>
                        </div>
 
                    </div>
                </div>
            `;
 
            msgDiv.querySelector('.council-stop-btn').addEventListener('click', stopGeneration);
            elements.chatBox.appendChild(msgDiv);
            scrollToBottom();
            animateCouncilPhases(id);
            return id;
        }

        function removeLoadingMessage(id) {
            clearInterval(window._councilTimer);
            const el = document.getElementById(id);
            if (el) el.remove();
        }

// ═══ [4] animateCouncilPhases — бегущий текст по директорам ══════════════
 
        function animateCouncilPhases(loaderId) {
 
            // Бегущие тексты для каждого директора — несколько строк, меняются каждые 3.5с
            const TEXTS = {
                scout: [
                    'Сканирует источники...',
                    'Ищет релевантные факты...',
                    'Проверяет актуальность данных...',
                    'Извлекает ключевую информацию...',
                    'Верифицирует достоверность...',
                ],
                analyst: [
                    'Строит структуру анализа...',
                    'Выявляет паттерны и связи...',
                    'Оценивает логику данных...',
                    'Ищет противоречия...',
                    'Формирует аналитическую картину...',
                ],
                architect: [
                    'Проектирует архитектуру решения...',
                    'Рассматривает варианты подхода...',
                    'Оценивает ограничения...',
                    'Строит модель решения...',
                    'Проверяет масштабируемость...',
                ],
                devil: [
                    'Ищет слабые места...',
                    'Проверяет скрытые допущения...',
                    'Моделирует сценарии отказа...',
                    'Оценивает критические риски...',
                    'Формулирует возражения...',
                ],
                chairman: [
                    'Синтезирует мнения совета...',
                    'Взвешивает аргументы...',
                    'Формирует финальную позицию...',
                    'Готовит итоговое решение...',
                    'Финализирует рекомендацию...',
                ],
            };
 
            // Последовательность фаз: директор → глобальный прогресс
            const PHASES = [
                { director: 'scout',    progress: 16, headerText: 'Scout собирает факты...' },
                { director: 'analyst',  progress: 35, headerText: 'Analyst анализирует данные...' },
                { director: 'architect',progress: 54, headerText: 'Architect проектирует решение...' },
                { director: 'devil',    progress: 73, headerText: "Devil's Advocate проверяет риски..." },
                { director: 'chairman', progress: 91, headerText: 'Chairman принимает решение...' },
            ];
 
            let phaseIdx    = 0;   // текущая фаза
            let textIdx     = 0;   // текущий текст внутри фазы
            let tickCount   = 0;   // общий счётчик тиков
 
            // Хранение состояния директоров: 'pending' | 'active' | 'done'
            const dirState = { scout:'pending', analyst:'pending', architect:'pending', devil:'pending', chairman:'pending' };
 
            function updateDirectorRow(el, dirId, state) {
                const row     = el.querySelector(`[data-director="${dirId}"]`);
                if (!row) return;
                const bar     = row.querySelector('.director-bar');
                const txt     = row.querySelector('.director-status-text');
                const spinner = row.querySelector('.director-spinner-icon');
 
                if (state === 'active') {
                    row.classList.remove('opacity-35');
                    row.classList.add('opacity-100', 'director-row-active');
                    if (bar) bar.style.width = '65%';
                    // Спиннер в статус-тексте
                    if (txt) {
                        const texts = TEXTS[dirId] || ['обрабатывает...'];
                        const t = texts[textIdx % texts.length];
                        txt.innerHTML = `<span class="director-inline-spinner"></span>${t}`;
                    }
                } else if (state === 'done') {
                    row.classList.remove('opacity-35', 'director-row-active');
                    row.classList.add('opacity-100');
                    if (bar) bar.style.width = '100%';
                    if (txt) txt.innerHTML = `<span class="text-green-500">✓ выполнено</span>`;
                }
            }
 
            function tick() {
                const el = document.getElementById(loaderId);
                if (!el) { clearInterval(window._councilTimer); return; }
 
                const phase   = PHASES[phaseIdx % PHASES.length];
                const textEl  = el.querySelector('.council-phase-text');
                const barEl   = el.querySelector('.council-progress');
                const pctEl   = el.querySelector('.council-percent');
 
                // Обновляем заголовок и общий прогресс
                if (textEl) textEl.textContent = phase.headerText;
                if (barEl)  barEl.style.width  = phase.progress + '%';
                if (pctEl)  pctEl.textContent  = phase.progress + '%';
 
                // Завершаем предыдущий директор
                if (phaseIdx > 0) {
                    const prevDir = PHASES[phaseIdx - 1].director;
                    if (dirState[prevDir] !== 'done') {
                        dirState[prevDir] = 'done';
                        updateDirectorRow(el, prevDir, 'done');
                    }
                }
 
                // Активируем текущий
                const curDir = phase.director;
                dirState[curDir] = 'active';
                updateDirectorRow(el, curDir, 'active');
 
                tickCount++;
                textIdx++;
 
                // Каждые 2 тика — переходим к следующей фазе
                if (tickCount % 2 === 0) {
                    phaseIdx++;
                    // После последней фазы — мягкий сброс
                    if (phaseIdx >= PHASES.length) {
                        phaseIdx = 0;
                        textIdx  = 0;
                        setTimeout(() => {
                            const el2 = document.getElementById(loaderId);
                            if (!el2) return;
                            // Сбрасываем всё
                            Object.keys(dirState).forEach(d => { dirState[d] = 'pending'; });
                            el2.querySelectorAll('.director-row').forEach(row => {
                                row.classList.remove('opacity-100', 'director-row-active');
                                row.classList.add('opacity-35');
                                const bar = row.querySelector('.director-bar');
                                const txt = row.querySelector('.director-status-text');
                                if (bar) bar.style.width = '0%';
                                if (txt) txt.innerHTML = 'ожидает...';
                            });
                            const b2 = el2.querySelector('.council-progress');
                            const p2 = el2.querySelector('.council-percent');
                            const t2 = el2.querySelector('.council-phase-text');
                            if (b2) b2.style.width = '3%';
                            if (p2) p2.textContent = '3%';
                            if (t2) t2.textContent = 'Совет продолжает работу...';
                        }, 1200);
                    }
                } else {
                    // Между сменой фазы — только обновляем бегущий текст активного директора
                    const row = el.querySelector(`[data-director="${curDir}"]`);
                    if (row) {
                        const txt = row.querySelector('.director-status-text');
                        if (txt) {
                            const texts = TEXTS[curDir] || ['обрабатывает...'];
                            const t = texts[textIdx % texts.length];
                            txt.innerHTML = `<span class="director-inline-spinner"></span>${t}`;
                        }
                    }
                }
            }
 
            // Первый тик сразу, потом каждые 3.5 сек
            tick();
            window._councilTimer = setInterval(tick, 3500);
        }

        // Кнопка «Стоп» — прерывает текущий fetch
        function stopGeneration() {
            clearInterval(window._councilTimer);
            if (state.abortController) state.abortController.abort();
            if (state.activeWebSocket) state.activeWebSocket.close();
        }

        // ==========================================
        // FILE HANDLING
        // ==========================================
        function handleFileSelect(e) {
            const files = Array.from(e.target.files);
            files.forEach(file => {
                if (file.size > CONFIG.MAX_FILE_SIZE) {
                    showToast(i18n[state.currentLanguage].fileTooLarge, 'error');
                    return;
                }
                if (!CONFIG.ALLOWED_FILE_TYPES.includes(file.type) && !file.name.match(/\.(txt|pdf|doc|docx|png|jpg|jpeg|gif|mp3|wav|m4a)$/i)) {
                    showToast(i18n[state.currentLanguage].invalidFileType, 'error');
                    return;
                }
                state.selectedFiles.push(file);
                renderFilePreview(file);
            });
            elements.fileInput.value = '';
        }

        function renderFilePreview(file) {
            elements.filePreview.classList.remove('hidden');
            const fileId = 'file-' + Date.now() + Math.random();
            const div = document.createElement('div');
            div.id = fileId;
            div.className = 'flex items-center gap-2 px-3 py-2 bg-theme-secondary border border-theme rounded-lg text-xs';
            div.innerHTML = `
                <i class="fas fa-file text-accent-theme" aria-hidden="true"></i>
                <span class="truncate max-w-[120px] text-theme-primary">${SecurityUtils.escapeHtml(file.name)}</span>
                <button class="ml-1 text-theme-tertiary hover:text-red-500" aria-label="Usuń plik">
                    <i class="fas fa-times" aria-hidden="true"></i>
                </button>
            `;
            
            EventManager.add(div.querySelector('button'), 'click', () => {
                state.selectedFiles = state.selectedFiles.filter(f => f !== file);
                div.remove();
                if (state.selectedFiles.length === 0) {
                    elements.filePreview.classList.add('hidden');
                }
            });
            
            elements.filePreview.appendChild(div);
        }

        // ==========================================
        // VOICE RECORDING
        // ==========================================
        async function toggleVoiceRecording() {
            if (state.isRecording) {
                stopRecording();
            } else {
                startRecording();
            }
        }

        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                state.mediaRecorder = new MediaRecorder(stream);
                state.audioChunks = [];
                
                state.mediaRecorder.ondataavailable = (e) => {
                    state.audioChunks.push(e.data);
                };
                
                state.mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(state.audioChunks, { type: 'audio/wav' });
                    showToast('Nagranie zapisane (funkcja w przygotowaniu)', 'success');
                };
                
                state.mediaRecorder.start();
                state.isRecording = true;
                elements.voiceBtn.classList.add('recording-pulse', 'text-red-500');
                elements.voiceBtn.innerHTML = '<i class="fas fa-stop text-lg" aria-hidden="true"></i>';
            } catch (err) {
                showToast('Brak dostępu do mikrofonu', 'error');
            }
        }

        function stopRecording() {
            if (state.mediaRecorder) {
                state.mediaRecorder.stop();
                state.mediaRecorder.stream.getTracks().forEach(track => track.stop());
            }
            state.isRecording = false;
            elements.voiceBtn.classList.remove('recording-pulse', 'text-red-500');
            elements.voiceBtn.innerHTML = '<i class="fas fa-microphone text-lg" aria-hidden="true"></i>';
        }

        function initCouncilWS() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${CONFIG.API_BASE_URL.replace(/^http/, 'ws')}/council/ws`;
            
            state.councilSocket = new WebSocket(wsUrl);

            state.councilSocket.onmessage = function(event) {
                const data = JSON.parse(event.data);
                const msgId = state.lastSentMsgId;
                if (!msgId) return;

                if (data.type === 'phase_start') {
                    const step = document.getElementById(`step-${data.phase}-${msgId}`);
                    if (step) {
                        document.querySelectorAll(`#protocol-container-${msgId} .protocol-step`).forEach(s => s.classList.remove('active'));
                        step.classList.add('active');
                        step.querySelector('.step-info').innerText = data.text;
                    }
                }

                if (data.type === 'phase_done') {
                    const step = document.getElementById(`step-${data.phase}-${msgId}`);
                    if (step) {
                        step.classList.remove('active');
                        step.classList.add('done');
                        const provider = data.provider || 'Ollama';
                        step.querySelector('.step-info').innerHTML = `
                            <span class="text-green-500">✓</span> ${data.preview ? data.preview.substring(0, 40) + '...' : 'Выполнено'}
                            <br><span class="text-[10px] opacity-40">[${provider} | ${data.tokens || 0} tkn]</span>
                        `;
                    }
                }
            };

            state.councilSocket.onclose = () => {
                setTimeout(initCouncilWS, 3000); // Реконнект при обрыве
            };
        }

        // Запускаем инициализацию сразу
        initCouncilWS();

        // ==========================================
        // API COMMUNICATION
        // ==========================================
        async function sendQuery() {
            const text = elements.messageInput.value.trim();
            if (!text && state.selectedFiles.length === 0) return;
            if (!state.currentChatId) startNewChat();

            // Создаем уникальный ID для текущей сессии размышлений
            const tempMsgId = Date.now();
            state.lastSentMsgId = tempMsgId; 

            // 1. Показываем сообщение пользователя
            if (text) {
                appendMessage('user', text);
                elements.messageInput.value = '';
                autoResizeTextarea();
            }

            // 2. Показываем вложения
            if (state.selectedFiles.length > 0) {
                state.selectedFiles.forEach(file => {
                    appendMessage('user', `[Załącznik: ${file.name}]`);
                });
            }

            // 3. ЗАПУСК ЖИВОГО ПРОТОКОЛА (Визуализация размышлений)
            renderLiveProtocol(tempMsgId);

            // Сохраняем оригинальный лоадер (если он используется для статус-бара)
            const loadingId = createCouncilMessage();

            // ── DEMO MODE ──────────────────────────────────────────────────
            if (state.isDemoMode) {
                setTimeout(() => {
                    removeLoadingMessage(loadingId);
                    let response = DemoAI.getResponse(text || '');
                    if (state.selectedFiles.length > 0) {
                        const fileResponses = state.selectedFiles.map(f => DemoAI.processFile(f.name)).join('\n\n');
                        response = fileResponses + '\n\n' + response;
                    }
                    appendMessage('assistant', response);
                    debouncedSaveChat();
                    state.selectedFiles = [];
                    elements.filePreview.innerHTML = '';
                    elements.filePreview.classList.add('hidden');
                }, 1000 + Math.random() * 1000);
                return;
            }
 
            const token = localStorage.getItem('consilium_token');
            if (!token) { logout(); return; }
 
            // ── Определяем тип запроса ─────────────────────────────────────
            const isCasual = text.length < 30 || /^(привет|hello|hi|hey|cześć|witaj|hej|привіт|как дела|спасибо|thanks|thank you|dziękuję|дякую|пока|bye|ok|okay|да|нет|yes|no)/i.test(text);
 
            // ── CASUAL → POST /chat (быстро, без стриминга) ────────────────
            if (isCasual) {
                if (state.abortController) state.abortController.abort();
                state.abortController = new AbortController();
 
                try {
                    const response = await fetch(`${CONFIG.API_BASE_URL}/chat`, {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'X-CSRF-Token': SecurityUtils.getCSRFToken(),
                            'Content-Type': 'application/json',
                        },
                        credentials: 'include',
                        body: JSON.stringify({
                            message: text,
                            chat_id: state.currentChatId,
                            model: state.currentModel,
                        }),
                        signal: state.abortController.signal,
                    });
 
                    removeLoadingMessage(loadingId);
 
                    if (response.ok) {
                        const data = await response.json();
                        appendMessage('assistant', data.response);
                        debouncedSaveChat();
                        state.selectedFiles = [];
                        elements.filePreview.innerHTML = '';
                        elements.filePreview.classList.add('hidden');
                        refreshCredits();
                    } else if (response.status === 401) {
                        logout();
                    } else {
                        const err = await response.json().catch(() => ({}));
                        appendMessage('assistant', err.message || i18n[state.currentLanguage].serverError, true);
                    }
                } catch (error) {
                    removeLoadingMessage(loadingId);
                    if (error.name === 'AbortError') {
                        appendMessage('assistant', '⛔ Генерация остановлена пользователем.');
                    } else {
                        appendMessage('assistant', i18n[state.currentLanguage].connectionError, true);
                    }
                }
                return;
            }
 
            // ── COUNCIL → WebSocket /ws/council (стриминг) ─────────────────
            const wsUrl = CONFIG.API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
 
            // Если WebSocket не поддерживается — fallback на POST
            if (!window.WebSocket) {
                return await _councilViaPost(text, token, loadingId);
            }
 
            let ws;
            try {
                ws = new WebSocket(`${wsUrl}/ws/council`);
            } catch (e) {
                return await _councilViaPost(text, token, loadingId);
            }
 
            // Сохраняем ws для кнопки Стоп
            state.activeWebSocket = ws;
			
			ws.onopen = () => {
                ws.send(JSON.stringify({
                token: token,
                message: text,
                chat_id: state.currentChatId
                }));
            };
 
            ws.onmessage = (event) => {
                let msg;
                try { msg = JSON.parse(event.data); }
                catch { return; }

                const el = document.getElementById(loadingId);
                const msgId = state.lastSentMsgId; // Наш ID для Live Protocol

                switch (msg.type) {
                    case 'council_ready': {
                        if (!el) break;
                        const selected = msg.selected || [];
                        el.querySelectorAll('.director-row').forEach(row => {
                            const dir = row.dataset.director;
                            if (!selected.includes(dir)) row.style.display = 'none';
                        });
                        break;
                    }

                    case 'phase_start': {
                        // 1. Обновляем старый лоадер (если есть)
                        if (el) {
                            const row = el.querySelector(`[data-director="${msg.phase}"]`);
                            if (row) {
                                row.style.display = '';
                                row.classList.remove('opacity-35');
                                row.classList.add('opacity-100', 'director-row-active');
                                const txt = row.querySelector('.director-status-text');
                                if (txt) txt.innerHTML = `<span class="director-inline-spinner"></span>${msg.text || 'Обрабатывает...'}`;
                            }
                        }
                        
                        // 2. ОБНОВЛЯЕМ LIVE PROTOCOL V3.0
                        const step = document.getElementById(`step-${msg.phase}-${msgId}`);
                        if (step) {
                            document.querySelectorAll(`#protocol-container-${msgId} .protocol-step`).forEach(s => s.classList.remove('active'));
                            step.classList.add('active');
                            step.querySelector('.step-info').innerText = msg.text || "Анализ данных...";
                        }
                        break;
                    }

                    case 'phase_done': {
                        // 1. Старый лоадер
                        if (el) {
                            const row = el.querySelector(`[data-director="${msg.phase}"]`);
                            if (row) {
                                row.classList.remove('director-row-active');
                                const txt = row.querySelector('.director-status-text');
                                if (txt) txt.innerHTML = `<span class="text-green-500">✓ выполнено</span>`;
                            }
                        }

                        // 2. LIVE PROTOCOL V3.0 (Галочка + детали модели)
                        const step = document.getElementById(`step-${msg.phase}-${msgId}`);
                        if (step) {
                            step.classList.remove('active');
                            step.classList.add('done');
                            const provider = msg.provider || 'Ollama';
                            step.querySelector('.step-info').innerHTML = `
                                <span class="text-green-500">✓</span> ${msg.preview ? msg.preview.substring(0, 40) + '...' : 'Завершено'}
                                <br><span class="text-[9px] opacity-40">[${provider} | ${msg.tokens || 0} tkn]</span>
                            `;
                        }
                        break;
                    }

                    case 'final': {
                        clearInterval(window._councilTimer);
                        removeLoadingMessage(loadingId);

                        // Останавливаем анимацию карточки протокола
                        const protocolContainer = document.getElementById(`protocol-container-${msgId}`);
                        if (protocolContainer) {
                            protocolContainer.querySelector('.animate-pulse')?.classList.remove('animate-pulse');
                        }

                        if (msg.council_used && msg.council_used.length > 0) {
                            appendCouncilCard(msg.council_used, msg.cost_usd || 0, msg.deliberation || {});
                        }
                        
                        appendMessage('assistant', msg.response);
                        debouncedSaveChat();

                        state.selectedFiles = [];
                        elements.filePreview.innerHTML = '';
                        elements.filePreview.classList.add('hidden');

                        if (typeof msg.credits_left === 'number') {
                            state.credits = msg.credits_left;
                            elements.creditsAmount.textContent = msg.credits_left;
                        } else {
                            refreshCredits();
                        }
                        ws.close(); // Закрываем после финала
                        break;
                    }

                    case 'error': {
                        clearInterval(window._councilTimer);
                        removeLoadingMessage(loadingId);
                        appendMessage('assistant', `❌ ${msg.message || 'Ошибка сервера'}`, true);
                        break;
                    }
                }
            };

            ws.onerror = async () => {
                clearInterval(window._councilTimer);
                removeLoadingMessage(loadingId);
                await _councilViaPost(text, token, null);
            };

            ws.onclose = () => {
                state.activeWebSocket = null;
            };
        }
 
 
        // ── FALLBACK: council через обычный POST /chat ─────────────────────
 
        async function _councilViaPost(text, token, loadingId) {
            const newLoadingId = loadingId || createCouncilMessage();
 
            if (state.abortController) state.abortController.abort();
            state.abortController = new AbortController();
 
            try {
                const response = await fetch(`${CONFIG.API_BASE_URL}/chat`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'X-CSRF-Token': SecurityUtils.getCSRFToken(),
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        message: text,
                        chat_id: state.currentChatId,
                        model: state.currentModel,
                    }),
                    signal: state.abortController.signal,
                });
 
                removeLoadingMessage(newLoadingId);
 
                if (response.ok) {
                    const data = await response.json();
                    if (data.mode === 'council' && Array.isArray(data.council_used) && data.council_used.length > 0) {
                        appendCouncilCard(data.council_used, data.cost_usd || 0, data.deliberation || {});
                    }
                    appendMessage('assistant', data.response);
                    debouncedSaveChat();
                    state.selectedFiles = [];
                    elements.filePreview.innerHTML = '';
                    elements.filePreview.classList.add('hidden');
                    refreshCredits();
                } else if (response.status === 401) {
                    logout();
                } else {
                    const err = await response.json().catch(() => ({}));
                    appendMessage('assistant', err.message || i18n[state.currentLanguage].serverError, true);
                }
            } catch (error) {
                removeLoadingMessage(newLoadingId);
                if (error.name !== 'AbortError') {
                    appendMessage('assistant', i18n[state.currentLanguage].connectionError, true);
                }
            }
        }

        async function refreshCredits() {
            if (!state.currentUserId || state.isDemoMode) return;
            
            try {
                const token = localStorage.getItem('consilium_token');
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000);
                
                const response = await fetch(`${CONFIG.API_BASE_URL}/credits`, {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'X-CSRF-Token': SecurityUtils.getCSRFToken()
                    },
                    credentials: 'include',
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (response.ok) {
                    const data = await response.json();
                    state.credits = data.credits;
                    elements.creditsAmount.textContent = state.credits;
                }
            } catch (error) {
                console.error('Credits refresh error:', error);
            }
        }

        async function buyCredits() {
            if (state.isDemoMode) {
                showToast('W trybie demo kredyty są nielimitowane!', 'success');
                return;
            }
            
            const selectedOption = document.querySelector('.credit-option.border-accent-theme');
            if (!selectedOption) return;

            const amount = parseInt(selectedOption.dataset.amount);
            const price = selectedOption.dataset.price;

            try {
                const token = localStorage.getItem('consilium_token');
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT);
                
                const response = await fetch(`${CONFIG.API_BASE_URL}/buy_credits`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`,
                        'X-CSRF-Token': SecurityUtils.getCSRFToken()
                    },
                    credentials: 'include',
                    body: JSON.stringify({ amount, price }),
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);

                if (response.ok) {
                    await refreshCredits();
                    closeModal(elements.creditsModal);
                    showToast(i18n[state.currentLanguage].confirmPurchase, 'success');
                } else {
                    showToast(i18n[state.currentLanguage].purchaseError, 'error');
                }
            } catch (error) {
                showToast(i18n[state.currentLanguage].connectionError, 'error');
            }
        }

        // ==========================================
        // CHAT HISTORY
        // ==========================================
        function saveCurrentChat() {
            if (!state.currentChatId || elements.chatBox.children.length === 0) return;
            
            const messages = [];
            elements.chatBox.querySelectorAll('.flex.gap-4').forEach(msg => {
                const content = msg.querySelector('.content');
                const isUser = msg.classList.contains('flex-row-reverse');
                if (content) {
                    messages.push({
                        role: isUser ? 'user' : 'assistant',
                        content: content.textContent,
                        timestamp: new Date().toISOString()
                    });
                }
            });

            if (messages.length === 0) return;

            const chatData = {
                id: state.currentChatId,
                title: messages[0].content.substring(0, 50) + '...',
                messages: messages,
                updatedAt: new Date().toISOString()
            };

            state.chatHistory.set(state.currentChatId, chatData);
            persistHistory();
            updateHistoryUI();
        }

        const debouncedSaveChat = debounce(saveCurrentChat, 1000);

        function persistHistory() {
            try {
                const historyObj = Object.fromEntries(state.chatHistory);
                const serialized = JSON.stringify(historyObj);
                
                if (serialized.length > CONFIG.MAX_STORAGE_SIZE) {
                    const sorted = Array.from(state.chatHistory.entries())
                        .sort((a, b) => new Date(a[1].updatedAt) - new Date(b[1].updatedAt));
                    
                    while (JSON.stringify(Object.fromEntries(state.chatHistory)).length > CONFIG.MAX_STORAGE_SIZE && state.chatHistory.size > 10) {
                        state.chatHistory.delete(sorted.shift()[0]);
                    }
                }
                
                localStorage.setItem('consilium_histories', JSON.stringify(Object.fromEntries(state.chatHistory)));
            } catch (e) {
                if (e.name === 'QuotaExceededError') {
                    showToast(i18n[state.currentLanguage].storageFull, 'error');
                }
            }
        }

        function loadChatHistory() {
            try {
                const stored = localStorage.getItem('consilium_histories');
                if (stored) {
                    const parsed = JSON.parse(stored);
                    Object.entries(parsed).forEach(([id, data]) => {
                        if (id.startsWith(CONFIG.CHAT_ID_PREFIX) && data && Array.isArray(data.messages)) {
                            state.chatHistory.set(id, data);
                        }
                    });
                }
                updateHistoryUI();
            } catch (e) {
                console.error('History load error:', e);
                localStorage.removeItem('consilium_histories');
            }
        }

        function updateHistoryUI() {
            const list = elements.chatHistoryList;
            list.innerHTML = '';
            
            if (state.chatHistory.size === 0) {
                list.innerHTML = `<div class="text-center text-theme-tertiary text-sm py-8">Brak historii</div>`;
                return;
            }

            const fragment = document.createDocumentFragment();
            
            Array.from(state.chatHistory.entries())
                .sort((a, b) => new Date(b[1].updatedAt) - new Date(a[1].updatedAt))
                .forEach(([id, chat]) => {
                    const item = document.createElement('div');
                    item.className = `group flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all mb-1 ${
                        id === state.currentChatId ? 'bg-accent-theme/10 border border-accent-theme/30' : 'hover:bg-theme-tertiary border border-transparent'
                    }`;
                    item.setAttribute('role', 'listitem');
                    item.tabIndex = 0;
                    
                    item.innerHTML = `
                        <i class="fas fa-comment-alt text-theme-secondary group-hover:accent-theme" aria-hidden="true"></i>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm font-medium text-theme-primary truncate">${SecurityUtils.escapeHtml(chat.title)}</p>
                            <p class="text-xs text-theme-tertiary">${new Date(chat.updatedAt).toLocaleDateString()}</p>
                        </div>
                        <button class="delete-chat-btn opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg text-theme-secondary hover:text-red-500 transition-all" aria-label="Usuń czat">
                            <i class="fas fa-trash-alt text-xs" aria-hidden="true"></i>
                        </button>
                    `;
                    
                    EventManager.add(item, 'click', (e) => {
                        if (!e.target.closest('.delete-chat-btn')) {
                            loadSpecificChat(id);
                        }
                    });
                    
                    EventManager.add(item, 'keydown', (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            loadSpecificChat(id);
                        }
                    });
                    
                    const deleteBtn = item.querySelector('.delete-chat-btn');
                    EventManager.add(deleteBtn, 'click', (e) => {
                        e.stopPropagation();
                        deleteChat(id);
                    });
                    
                    fragment.appendChild(item);
                });
            
            list.appendChild(fragment);
        }

        function loadSpecificChat(chatId) {
            const chat = state.chatHistory.get(chatId);
            if (!chat || !Array.isArray(chat.messages)) return;
            
            state.currentChatId = chatId;
            elements.chatBox.innerHTML = '';
            showChatInterface();
            
            chat.messages.forEach(msg => {
                appendMessage(msg.role, msg.content);
            });
            
            updateHistoryUI();
            closeSidebar();
        }

        function deleteChat(id) {
            if (!confirm(i18n[state.currentLanguage].confirmDeleteChat)) return;
            
            state.chatHistory.delete(id);
            persistHistory();
            updateHistoryUI();
            
            if (state.currentChatId === id) {
                showEmptyState();
            }
        }

        function clearAllHistory() {
            if (!confirm(i18n[state.currentLanguage].confirmClearHistory)) return;
            
            state.chatHistory.clear();
            localStorage.removeItem('consilium_histories');
            updateHistoryUI();
            showEmptyState();
            showToast(i18n[state.currentLanguage].clearHistory, 'success');
        }

        // ==========================================
        // SETTINGS
        // ==========================================
        function openSettings() {
            elements.settingsPanel.classList.remove('translate-x-full');
            elements.settingsOverlay.classList.remove('hidden');
            elements.closeSettings.focus();
            document.body.style.overflow = 'hidden';
        }

        function closeSettings() {
            elements.settingsPanel.classList.add('translate-x-full');
            elements.settingsOverlay.classList.add('hidden');
            elements.settingsBtn.focus();
            document.body.style.overflow = '';
        }

        function changeLanguage(e) {
            state.currentLanguage = e.target.value;
            localStorage.setItem('consilium_language', state.currentLanguage);
            applyTranslations();
        }

        function changeTheme(theme) {
            state.currentTheme = theme;
            document.body.className = document.body.className.replace(/(dark|sepia|midnight)/g, '').trim();
            if (theme !== 'light') {
                document.body.classList.add(theme);
            }
            localStorage.setItem('consilium_theme', theme);
            
            elements.themeBtns.forEach(btn => {
                btn.classList.toggle('border-accent-theme', btn.dataset.theme === theme);
                btn.classList.toggle('bg-blue-50', btn.dataset.theme === theme);
                btn.classList.toggle('dark:bg-blue-900/20', btn.dataset.theme === theme);
            });
        }

        function toggleNightShift() {
            state.nightShift = !state.nightShift;
            document.body.classList.toggle('night-shift-active', state.nightShift);
            elements.nightShiftToggle.setAttribute('aria-checked', state.nightShift);
            elements.nightShiftToggle.querySelector('span').style.transform = state.nightShift ? 'translateX(24px)' : 'translateX(0)';
            elements.nightShiftToggle.classList.toggle('bg-accent-theme', state.nightShift);
            localStorage.setItem('consilium_night_shift', state.nightShift);
        }

        function changeFontSize(e) {
            state.fontSize = e.target.value;
            document.documentElement.style.fontSize = state.fontSize + 'px';
            localStorage.setItem('consilium_font_size', state.fontSize);
        }

        function changeModel(e) {
            state.currentModel = e.target.value;
            localStorage.setItem('consilium_model', state.currentModel);
        }

        function exportChat() {
            if (!state.currentChatId || elements.chatBox.children.length === 0) {
                showToast('Brak czatu do eksportu', 'error');
                return;
            }

            const chat = state.chatHistory.get(state.currentChatId);
            if (!chat) return;

            const exportData = {
                title: chat.title,
                exportedAt: new Date().toISOString(),
                messages: chat.messages
            };

            const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `chat-${state.currentChatId}-${Date.now()}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            showToast('Czat wyeksportowany', 'success');
        }

        function loadSettings() {
            const savedTheme = localStorage.getItem('consilium_theme') || 'light';
            changeTheme(savedTheme);
            elements.themeBtns.forEach(btn => {
                if (btn.dataset.theme === savedTheme) {
                    btn.classList.add('border-accent-theme', 'bg-blue-50', 'dark:bg-blue-900/20');
                }
            });

            const savedLang = localStorage.getItem('consilium_language') || 'pl';
            state.currentLanguage = savedLang;
            elements.languageSelect.value = savedLang;
            applyTranslations();

            const savedNightShift = localStorage.getItem('consilium_night_shift') === 'true';
            if (savedNightShift) toggleNightShift();

            const savedFontSize = localStorage.getItem('consilium_font_size') || '16';
            state.fontSize = savedFontSize;
            elements.fontSizeSlider.value = savedFontSize;
            document.documentElement.style.fontSize = savedFontSize + 'px';

            const savedModel = localStorage.getItem('consilium_model') || 'gpt-4';
            state.currentModel = savedModel;
            elements.modelSelect.value = savedModel;
        }

        function applyTranslations() {
            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.dataset.i18n;
                if (i18n[state.currentLanguage][key]) {
                    el.textContent = i18n[state.currentLanguage][key];
                }
            });
            
            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
                const key = el.dataset.i18nPlaceholder;
                if (i18n[state.currentLanguage][key]) {
                    el.placeholder = i18n[state.currentLanguage][key];
                }
            });

            if (elements.authSubmitBtn) {
                elements.authSubmitBtn.innerHTML = `<span>${i18n[state.currentLanguage][state.isRegisterMode ? 'register' : 'login']}</span>`;
            }
        }

        // ==========================================
        // DRAG AND DROP
        // ==========================================
        function setupDragAndDrop() {
            const dropZone = document.body;
            
            EventManager.add(dropZone, 'dragenter', (e) => {
                if (e.dataTransfer.types.includes('Files')) {
                    e.preventDefault();
                    dropZone.classList.add('bg-blue-50/50', 'dark:bg-blue-900/10');
                }
            });

            EventManager.add(dropZone, 'dragover', (e) => {
                if (e.dataTransfer.types.includes('Files')) {
                    e.preventDefault();
                }
            });

            EventManager.add(dropZone, 'dragleave', (e) => {
                if (e.relatedTarget === null) {
                    dropZone.classList.remove('bg-blue-50/50', 'dark:bg-blue-900/10');
                }
            });

            EventManager.add(dropZone, 'drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('bg-blue-50/50', 'dark:bg-blue-900/10');
                
                const files = Array.from(e.dataTransfer.files);
                files.forEach(file => {
                    if (file.size <= CONFIG.MAX_FILE_SIZE && (CONFIG.ALLOWED_FILE_TYPES.includes(file.type) || file.name.match(/\.(txt|pdf|doc|docx|png|jpg|jpeg|gif|mp3|wav|m4a)$/i))) {
                        state.selectedFiles.push(file);
                        renderFilePreview(file);
                    }
                });
            });

            EventManager.add(document, 'paste', (e) => {
                const items = e.clipboardData.items;
                for (let item of items) {
                    if (item.kind === 'file') {
                        const file = item.getAsFile();
                        if (file && file.size <= CONFIG.MAX_FILE_SIZE) {
                            state.selectedFiles.push(file);
                            renderFilePreview(file);
                        }
                    }
                }
            });
        }

        // ==========================================
        // UTILITY FUNCTIONS
        // ==========================================
        function debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }

        function copyToClipboard(text) {
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(text).then(() => {
                    showToast(i18n[state.currentLanguage].copied, 'success');
                }).catch(() => {
                    fallbackCopy(text);
                });
            } else {
                fallbackCopy(text);
            }
        }

        function fallbackCopy(text) {
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-9999px';
            document.body.appendChild(textArea);
            textArea.select();
            
            try {
                document.execCommand('copy');
                showToast(i18n[state.currentLanguage].copied, 'success');
            } catch (err) {
                showToast('Kopiowanie nie powiodło się', 'error');
            }
            
            document.body.removeChild(textArea);
        }

        function showToast(message, type = 'info') {
            const toast = elements.toast;
            const icon = elements.toastIcon;
            const msg = elements.toastMessage;
            
            msg.textContent = message;
            icon.className = type === 'success' ? 'fas fa-check-circle text-green-500' : 
                            type === 'error' ? 'fas fa-exclamation-circle text-red-500' : 
                            'fas fa-info-circle text-blue-500';
            
            toast.classList.remove('translate-y-20', 'opacity-0');
            
            setTimeout(() => {
                toast.classList.add('translate-y-20', 'opacity-0');
            }, 3000);
        }

        function toggleSidebar() {
            state.isSidebarOpen = !state.isSidebarOpen;
            elements.sidebar.classList.toggle('-translate-x-full', !state.isSidebarOpen);
            elements.sidebarOverlay.classList.toggle('hidden', !state.isSidebarOpen);
            elements.menuBtn.setAttribute('aria-expanded', state.isSidebarOpen);
        }

        function closeSidebar() {
            state.isSidebarOpen = false;
            elements.sidebar.classList.add('-translate-x-full');
            elements.sidebarOverlay.classList.add('hidden');
            elements.menuBtn.setAttribute('aria-expanded', 'false');
        }

        function openModal(modal) {
            modal.classList.remove('hidden');
            modal.setAttribute('aria-hidden', 'false');
            const focusable = modal.querySelector('button, input, select, textarea, [href]');
            if (focusable) focusable.focus();
            document.body.style.overflow = 'hidden';
        }

        function closeModal(modal) {
            modal.classList.add('hidden');
            modal.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
        }

        function autoResizeTextarea() {
            const textarea = elements.messageInput;
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 128) + 'px';
        }

        function handleInputKeydown(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendQuery();
            }
        }

        function handleGlobalKeydown(e) {
            if (e.key === 'Escape') {
                if (!elements.settingsPanel.classList.contains('translate-x-full')) {
                    closeSettings();
                } else if (!elements.creditsModal.classList.contains('hidden')) {
                    closeModal(elements.creditsModal);
                } else if (state.isSidebarOpen) {
                    closeSidebar();
                }
            }
            
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                sendQuery();
            }
        }

        function scrollToBottom() {
            elements.chatBox.scrollTop = elements.chatBox.scrollHeight;
        }

        function selectCreditOption(e) {
            const btn = e.currentTarget;
            elements.creditOptions.forEach(opt => {
                opt.classList.remove('border-accent-theme', 'bg-blue-50', 'dark:bg-blue-900/20');
                opt.classList.add('border-theme');
            });
            btn.classList.remove('border-theme');
            btn.classList.add('border-accent-theme', 'bg-blue-50', 'dark:bg-blue-900/20');
            elements.confirmPurchaseBtn.disabled = false;
            elements.confirmPurchaseBtn.textContent = `${i18n[state.currentLanguage].buyCredits} - $${btn.dataset.price}`;
        }

        function handleVisibilityChange() {
            if (document.hidden && state.currentChatId) {
                saveCurrentChat();
            }
        }

        function handleBeforeUnload() {
            if (state.currentChatId) {
                saveCurrentChat();
            }
        }

        window.addEventListener('unload', () => {
            EventManager.listeners.forEach((listeners, element) => {
                listeners.forEach(({ event, handler, options }) => {
                    element.removeEventListener(event, handler, options);
                });
            });
            EventManager.listeners.clear();
        });