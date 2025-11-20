(() => {
    const $ = (selector, scope = document) => scope.querySelector(selector);
    const $$ = (selector, scope = document) => scope.querySelectorAll(selector);

    document.addEventListener('DOMContentLoaded', () => {
        initModeSelector();
        initAnimations();
        initDropzones();
        initFormSubmit();
        initDetailsToggle();
        initCharts();
        initPairingEditor();
    });

    function initAnimations() {
        const elements = $$('.info-card, .stat-card, .chart-card');
        if (!('IntersectionObserver' in window) || !elements.length) {
            return;
        }
        const observer = new IntersectionObserver((entries, obs) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    obs.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });
        elements.forEach(el => {
            el.classList.add('will-animate');
            observer.observe(el);
        });
    }

    function initModeSelector() {
        const modeButtons = $$('[data-mode]');
        if (!modeButtons.length) return;

        const form = document.getElementById('upload-form');
        const pumlJsonSection = document.querySelector('[data-dropzone="json"][data-mode="puml-json"]');
        const pumlPumlSection = document.querySelector('[data-dropzone="puml2"][data-mode="puml-puml"]');
        const submitHint = document.getElementById('submit-hint');
        const submitText = document.getElementById('submit-text');
        const jsonFilesInput = document.getElementById('json_files');
        const puml2FilesInput = document.getElementById('puml2_files');
        const pumlFilesInput = document.getElementById('puml_files');

        if (!form) return;

        // Установка начального состояния required для PUML vs JSON режима
        if (pumlFilesInput) pumlFilesInput.required = true;
        if (jsonFilesInput) jsonFilesInput.required = true;
        if (puml2FilesInput) puml2FilesInput.required = false;

        let previousMode = window.CURRENT_MODE || 'puml-json';

        modeButtons.forEach(btn => {
            btn.addEventListener('click', function () {
                const mode = this.getAttribute('data-mode');

                // Если режим действительно изменился, очищаем файлы
                if (mode !== previousMode) {
                    window.CURRENT_MODE = mode;
                    previousMode = mode;

                    // Обновляем активную кнопку
                    modeButtons.forEach(b => b.classList.remove('mode-btn-active'));
                    this.classList.add('mode-btn-active');

                    // Очищаем файлы при переключении и триггерим change событие
                    if (pumlFilesInput) {
                        pumlFilesInput.value = '';
                        pumlFilesInput.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    if (jsonFilesInput) {
                        jsonFilesInput.value = '';
                        jsonFilesInput.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    if (puml2FilesInput) {
                        puml2FilesInput.value = '';
                        puml2FilesInput.dispatchEvent(new Event('change', { bubbles: true }));
                    }

                    if (mode === 'puml-json') {
                        if (pumlJsonSection) pumlJsonSection.style.display = 'block';
                        if (pumlPumlSection) pumlPumlSection.style.display = 'none';
                        if (pumlFilesInput) pumlFilesInput.required = true;
                        if (jsonFilesInput) jsonFilesInput.required = true;
                        if (puml2FilesInput) puml2FilesInput.required = false;
                        if (submitHint) submitHint.textContent = 'После загрузки вы сможете подтвердить соответствия перед сравнением.';
                        if (submitText) submitText.textContent = 'Предпросмотр соответствий';
                        form.action = '/preview';
                    } else if (mode === 'puml-puml') {
                        if (pumlJsonSection) pumlJsonSection.style.display = 'none';
                        if (pumlPumlSection) pumlPumlSection.style.display = 'block';
                        if (pumlFilesInput) pumlFilesInput.required = true;
                        if (jsonFilesInput) jsonFilesInput.required = false;
                        if (puml2FilesInput) puml2FilesInput.required = true;
                        if (submitHint) submitHint.textContent = 'Загрузите два набора PUML файлов для сравнения.';
                        if (submitText) submitText.textContent = 'Сравнить PUML файлы';
                        form.action = '/preview-puml-puml';
                    }
                }
            });
        });
    }

    function initDropzones() {
        const zones = $$('[data-dropzone]');
        if (!zones.length) return;

        const counts = { puml: 0, json: 0, puml2: 0 };
        const mismatch = document.querySelector('[data-mismatch-alert]');
        const mismatchText = mismatch ? mismatch.querySelector('[data-mismatch-text]') : null;
        const submitBtn = document.querySelector('.upload-form button[type="submit"]');
        const maxProgressFiles = 5;
        const maxFileSize = window.MAX_UPLOAD_SIZE || 1024 * 1024; // Default 1MB if not set
        const supportsDataTransfer = typeof DataTransfer !== 'undefined';

        zones.forEach(zone => {
            const type = zone.dataset.dropzone;
            const input = zone.querySelector('input[type="file"]');
            const target = zone.querySelector('[data-drop-target]') || zone;
            const trigger = zone.querySelector('[data-drop-trigger]');
            const list = zone.querySelector('[data-file-list]');
            const errorBox = zone.querySelector('[data-file-error]');
            const progress = zone.querySelector('[data-progress-bar]');
            if (!input) return;

            const prevent = event => {
                event.preventDefault();
                event.stopPropagation();
            };

            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                target.addEventListener(eventName, prevent);
            });

            ['dragenter', 'dragover'].forEach(eventName => {
                target.addEventListener(eventName, () => zone.classList.add('is-dragover'));
            });

            ['dragleave', 'drop'].forEach(eventName => {
                target.addEventListener(eventName, () => zone.classList.remove('is-dragover'));
            });

            target.addEventListener('drop', event => {
                if (!event.dataTransfer) return;
                const files = filterFiles(event.dataTransfer.files, input.accept);
                if (!files.length) return;
                const validFiles = enforceSizeLimit(files, errorBox);
                if (!validFiles.length) return;
                if (supportsDataTransfer) {
                    const transfer = new DataTransfer();
                    validFiles.forEach(file => transfer.items.add(file));
                    input.files = transfer.files;
                } else {
                    input.files = files;
                }
                syncState();
            });

            input.addEventListener('change', syncState);

            if (trigger) {
                trigger.addEventListener('click', evt => {
                    evt.preventDefault();
                    input.click();
                });
            }

            syncState();

            function syncState() {
                renderList();
                updateProgress();
                counts[type] = input.files ? input.files.length : 0;
                updateMismatch();
            }

            function renderList() {
                if (!list) return;
                list.innerHTML = '';
                if (!input.files || !input.files.length) {
                    return;
                }
                const fragment = document.createDocumentFragment();
                Array.from(input.files).forEach(file => {
                    const pill = document.createElement('span');
                    pill.className = 'file-pill';
                    const sizeLabel = (file.size / 1024).toFixed(1);
                    pill.textContent = `${file.name} (${sizeLabel} KB)`;
                    fragment.appendChild(pill);
                });
                list.appendChild(fragment);
            }

            function updateProgress() {
                if (!progress) return;
                const count = input.files ? input.files.length : 0;
                const percentage = Math.min(count / maxProgressFiles, 1) * 100;
                progress.style.width = `${percentage}%`;
            }
        });

        updateMismatch();

        function updateMismatch() {
            if (!mismatch) return;

            // Определяем текущий режим
            const currentMode = window.CURRENT_MODE || 'puml-json';
            const { puml, json, puml2 } = counts;

            let state = 'ok';
            let message = '';

            if (currentMode === 'puml-json') {
                // Режим PUML vs JSON
                if (!puml && !json) {
                    message = 'Добавьте PUML и JSON файлы';
                    state = 'error';
                } else if (!puml || !json) {
                    message = 'Добавьте недостающие файлы, чтобы пары были полными';
                    state = 'error';
                } else if (puml !== json) {
                    message = `Количество файлов не совпадает: ${puml} PUML vs ${json} JSON`;
                    state = 'warning';
                }
            } else if (currentMode === 'puml-puml') {
                // Режим PUML vs PUML
                if (!puml && !puml2) {
                    message = 'Добавьте оба набора PUML файлов';
                    state = 'error';
                } else if (!puml || !puml2) {
                    message = 'Добавьте недостающие файлы, чтобы пары были полными';
                    state = 'error';
                } else if (puml !== puml2) {
                    message = `Количество файлов не совпадает: ${puml} первых vs ${puml2} вторых`;
                    state = 'warning';
                }
            }

            mismatch.hidden = state === 'ok';
            mismatch.dataset.state = state;
            if (mismatchText) {
                mismatchText.textContent = message;
            }
            if (submitBtn) {
                submitBtn.disabled = state === 'error';
            }
        }

        function filterFiles(fileList, accept) {
            if (!accept) return Array.from(fileList);
            const exts = accept
                .split(',')
                .map(entry => entry.trim().toLowerCase())
                .filter(Boolean);
            if (!exts.length) return Array.from(fileList);
            return Array.from(fileList).filter(file =>
                exts.some(ext => file.name.toLowerCase().endsWith(ext))
            );
        }

        function enforceSizeLimit(files, errorBox) {
            const valid = [];
            const rejected = [];
            files.forEach(file => {
                if (file.size <= maxFileSize) {
                    valid.push(file);
                } else {
                    rejected.push(file.name);
                }
            });

            if (errorBox) {
                if (rejected.length) {
                    errorBox.hidden = false;
                    errorBox.textContent = `Файлы превышают 1MB: ${rejected.join(', ')}`;
                } else {
                    errorBox.hidden = true;
                    errorBox.textContent = '';
                }
            }

            return valid;
        }
    }

    function initFormSubmit() {
        const form = $('.upload-form');
        if (!form) return;
        form.addEventListener('submit', () => {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="btn-icon">⏳</span> Обработка...';
            }
        });
    }

    function initDetailsToggle() {
        document.addEventListener('click', event => {
            const toggle = event.target.closest('[data-details-target]');
            if (!toggle) return;
            const target = document.getElementById(toggle.dataset.detailsTarget);
            if (!target) return;
            const isHidden = target.classList.toggle('is-hidden');
            toggle.setAttribute('aria-expanded', String(!isHidden));
            toggle.textContent = isHidden ? 'Подробнее' : 'Скрыть';
            if (!isHidden) {
                target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        });
    }

    function initCharts() {
        const dataNode = document.getElementById('comparison-chart-data');
        if (!dataNode || !window.Chart) return;
        let payload = { labels: [], scores: [] };
        try {
            payload = JSON.parse(dataNode.textContent);
        } catch (err) {
            console.error('Не удалось распарсить данные графиков', err);
            return;
        }
        const labels = payload.labels || [];
        const scores = payload.scores || [];

        const palette = score => score >= 90
            ? { bg: 'rgba(34, 197, 94, 0.8)', border: 'rgb(34, 197, 94)' }
            : score >= 70
                ? { bg: 'rgba(59, 130, 246, 0.8)', border: 'rgb(59, 130, 246)' }
                : { bg: 'rgba(239, 68, 68, 0.8)', border: 'rgb(239, 68, 68)' };

        const scoresCanvas = document.getElementById('scoresChart');
        if (scoresCanvas) {
            const ctx = scoresCanvas.getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [{
                        label: 'Оценка (%)',
                        data: scores,
                        backgroundColor: scores.map(score => palette(score).bg),
                        borderColor: scores.map(score => palette(score).border),
                        borderWidth: 2,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                callback: value => value + '%'
                            }
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: ctx => `Оценка: ${ctx.parsed.y.toFixed(1)}%`
                            }
                        }
                    }
                }
            });
        }

        const doughnutCanvas = document.getElementById('distributionChart');
        if (doughnutCanvas) {
            const distribution = {
                excellent: scores.filter(score => score >= 90).length,
                good: scores.filter(score => score >= 70 && score < 90).length,
                poor: scores.filter(score => score < 70).length
            };
            const ctx = doughnutCanvas.getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Отлично (≥90%)', 'Хорошо (70-89%)', 'Неудовлетворительно (<70%)'],
                    datasets: [{
                        data: [distribution.excellent, distribution.good, distribution.poor],
                        backgroundColor: [
                            'rgba(34, 197, 94, 0.8)',
                            'rgba(59, 130, 246, 0.8)',
                            'rgba(239, 68, 68, 0.8)'
                        ],
                        borderColor: [
                            'rgb(34, 197, 94)',
                            'rgb(59, 130, 246)',
                            'rgb(239, 68, 68)'
                        ],
                        borderWidth: 2,
                        hoverOffset: 8
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom' },
                        tooltip: {
                            callbacks: {
                                label: context => {
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0) || 1;
                                    const percentage = ((context.parsed / total) * 100).toFixed(1);
                                    return `${context.label}: ${context.parsed} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    function initPairingEditor() {
        const rows = $$('[data-pairing-row]');
        if (!rows.length) return;
        rows.forEach(row => {
            const select = $('[data-pairing-select]', row);
            const label = $('[data-selection-label]', row);
            const editBtn = $('[data-edit-pairing]', row);
            if (!select || !label) return;

            row.classList.add('is-enhanced');
            syncLabel();

            select.addEventListener('change', () => {
                syncLabel();
                row.classList.remove('is-editing');
            });

            if (editBtn) {
                editBtn.addEventListener('click', evt => {
                    evt.preventDefault();
                    row.classList.toggle('is-editing');
                    if (row.classList.contains('is-editing')) {
                        select.focus();
                    }
                });
            }

            function syncLabel() {
                const option = select.selectedOptions[0];
                label.textContent = option ? option.textContent : 'Не выбран';
            }
        });
    }
})();
