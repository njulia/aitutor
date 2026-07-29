        // Compatibility for older iPads that are limited to Safari 12.
        // Keep this block in ES5 syntax so it runs before the app uses newer
        // DOM convenience methods.
        (function installLegacySafariCompatibility() {
            function defineMethod(prototype, name, implementation) {
                if (!prototype || prototype[name]) return;
                try {
                    Object.defineProperty(prototype, name, {
                        configurable: true,
                        writable: true,
                        value: implementation
                    });
                } catch (error) {
                    prototype[name] = implementation;
                }
            }

            if (typeof NodeList !== 'undefined') {
                defineMethod(NodeList.prototype, 'forEach', function(callback, thisArg) {
                    return Array.prototype.forEach.call(this, callback, thisArg);
                });
            }

            defineMethod(Array.prototype, 'flatMap', function(callback, thisArg) {
                return Array.prototype.concat.apply([], this.map(callback, thisArg));
            });

            if (typeof Element !== 'undefined') {
                defineMethod(Element.prototype, 'replaceChildren', function() {
                    while (this.firstChild) {
                        this.removeChild(this.firstChild);
                    }
                    for (var index = 0; index < arguments.length; index += 1) {
                        var child = arguments[index];
                        this.appendChild(
                            child && typeof child.nodeType === 'number'
                                ? child
                                : document.createTextNode(String(child))
                        );
                    }
                });
            }

            if (typeof Promise !== 'undefined') {
                defineMethod(Promise.prototype, 'finally', function(callback) {
                    var PromiseConstructor = this.constructor || Promise;
                    return this.then(
                        function(value) {
                            return PromiseConstructor.resolve(callback()).then(function() {
                                return value;
                            });
                        },
                        function(reason) {
                            return PromiseConstructor.resolve(callback()).then(function() {
                                throw reason;
                            });
                        }
                    );
                });
            }
        })();

        let currentHomework = [];
        let currentSubject = 'Maths';
        let currentProfile = null;
        let currentInputMethod = 'text';
        let currentPhotoData = null;
        let currentFileData = null;
        let extractedContent = '';
        let fileUploadPromise = null;
        let photoUploadPromise = null;
        let activeReviewContext = null;
        // 练习模式状态
        let isPracticeMode = false;
        let currentPracticeContent = '';
        let currentPracticeSubject = 'Maths';

        // Homework mode and current question index
        let currentHomeworkMode = 'homework'; // 'homework' or 'tutor'
        let currentQuestionIndex = 0;
        let currentQuestionAnswers = {}; // Store answers for each question in tutor mode
        localStorage.removeItem('student_id');
        localStorage.removeItem('student_email');
        let currentStudentId = localStorage.getItem('auth_state') === 'logged_in' ? 'authenticated' : null;
        let currentStudentEmail = null;
        let anonymousClientId = null; // Server-issued random cookie ID
        let primarySubjects = ['Maths', 'English', 'Science'];
        let elevenPlusSubjects = ['Maths', 'English', 'Verbal Reasoning', 'Non-Verbal Reasoning'];

        // ===== Voice Feature Detection & State (Tier 0: Browser-native) =====
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRec) {
            console.log("Speech recognition is supported!");
        } else {
            console.log("Speech recognition is not supported in this browser.");
        }
        const ttsSupported = 'speechSynthesis' in window;
        const sttSupported = !!SpeechRec;
        let recognizer = null;
        let isListening = false;
        let speechPlaybackId = 0;
        let activeSpeechUtterance = null;
        let activeSpeechButton = null;

        // Warm up and cache voices asynchronously for Web Speech API
        let voiceCache = [];
        function updateVoiceCache() {
            if (ttsSupported && window.speechSynthesis) {
                try {
                    voiceCache = window.speechSynthesis.getVoices() || [];
                } catch (e) {
                    voiceCache = [];
                }
            }
        }
        if (ttsSupported && window.speechSynthesis) {
            updateVoiceCache();
            if (typeof window.speechSynthesis.onvoiceschanged !== 'undefined') {
                window.speechSynthesis.onvoiceschanged = updateVoiceCache;
            }
        }

        // 获取女声教师语音（en-GB优先）
        function getFemaleVoice() {
            if (!ttsSupported || !window.speechSynthesis) return null;
            const voices = window.speechSynthesis.getVoices();
            // 优先匹配明确的女性英音
            const femaleGb = voices.find(v =>
                v.lang === 'en-GB' && /female|woman|girl/i.test(v.name)
            );
            if (femaleGb) return femaleGb;
            // 回退：任意女性英文语音
            const femaleAny = voices.find(v =>
                v.lang.startsWith('en') && /female|woman|girl/i.test(v.name)
            );
            if (femaleAny) return femaleAny;
            // 再回退：en-GB 任意语音
            const anyGb = voices.find(v => v.lang === 'en-GB');
            if (anyGb) return anyGb;
            // 最终回退：任意英文语音
            return voices.find(v => v.lang.startsWith('en')) || null;
        }

        const HOMEWORK_COMMON_SUBJECTS = ['Maths', 'English', 'Science'];
        const HOMEWORK_SESSION_QUESTIONS = {
            10: 5,
            15: 8,
            20: 10
        };
        const HOMEWORK_DIFFICULTY_LABELS = {
            gentle: '😊 Gentle',
            just_right: '👍 Just right',
            challenge: '🚀 Challenge me'
        };

        function combineRewardUpdates(updates) {
            const valid = (updates || []).filter(update => update && Number(update.awarded_xp) > 0);
            if (!valid.length) return null;
            const uniqueBy = (items, key) => Array.from(
                new Map(items.filter(Boolean).map(item => [
                    item[key] || item.label || JSON.stringify(item), item
                ])).values()
            );
            return {
                awarded_xp: valid.reduce(
                    (total, update) => total + Number(update.awarded_xp || 0), 0
                ),
                quest_completions: uniqueBy(
                    valid.flatMap(update => update.quest_completions || []), 'label'
                ),
                new_certificates: uniqueBy(
                    valid.flatMap(update => update.new_certificates || []), 'code'
                )
            };
        }

        function showRewardCelebration(update) {
            if (!update || Number(update.awarded_xp || 0) <= 0) return;
            let toast = document.getElementById('xp-celebration');
            if (!toast) {
                toast = document.createElement('aside');
                toast.id = 'xp-celebration';
                toast.className = 'xp-celebration';
                toast.setAttribute('role', 'status');
                toast.setAttribute('aria-live', 'polite');
                document.body.appendChild(toast);
            }
            toast.textContent = '';
            const title = document.createElement('strong');
            title.textContent = `✨ +${Number(update.awarded_xp)} XP for your effort!`;
            toast.appendChild(title);
            const questNames = (update.quest_completions || [])
                .map(item => item.label).filter(Boolean);
            if (questNames.length) {
                const quest = document.createElement('span');
                quest.textContent = ` Quest complete: ${questNames.join(', ')}.`;
                toast.appendChild(quest);
            }
            const certificates = (update.new_certificates || [])
                .map(item => item.title).filter(Boolean);
            if (certificates.length) {
                const certificate = document.createElement('span');
                certificate.textContent = ` New certificate: ${certificates.join(', ')}!`;
                toast.appendChild(certificate);
            }
            const link = document.createElement('a');
            link.href = '/rewards';
            link.textContent = 'See my quests';
            toast.appendChild(link);
            toast.hidden = false;
            window.clearTimeout(showRewardCelebration.timer);
            showRewardCelebration.timer = window.setTimeout(() => {
                toast.hidden = true;
            }, 7000);
        }

        const homeworkGuideState = {
            stepIndex: 0,
            answers: {},
            showAllSubjects: false,
            showQuickStart: false
        };

        function getHomeworkGuideSteps() {
            const commonSubjects = HOMEWORK_COMMON_SUBJECTS.filter(subject => primarySubjects.includes(subject));
            const subjectOptions = homeworkGuideState.showAllSubjects
                ? primarySubjects.map(subject => ({value: subject, label: subject}))
                : [
                    ...commonSubjects.map(subject => ({value: subject, label: subject})),
                    ...(primarySubjects.length > commonSubjects.length
                        ? [{value: '__more__', label: '➕ More subjects'}]
                        : [])
                ];
            return [
                {
                    key: 'year_group',
                    question: 'Hi! What year are you in?',
                    options: [1, 2, 3, 4, 5, 6].map(year => ({
                        value: year,
                        label: `Year ${year}`
                    }))
                },
                {
                    key: 'subject',
                    question: 'What shall we practise today?',
                    options: subjectOptions
                },
                {
                    key: 'session_minutes',
                    question: 'How long shall we practise?',
                    options: [
                        {value: 10, label: '10 minutes · Quick'},
                        {value: 15, label: '15 minutes · Just enough'},
                        {value: 20, label: '20 minutes · Longer'}
                    ]
                },
                {
                    key: 'difficulty',
                    question: 'How tricky should it be?',
                    options: Object.entries(HOMEWORK_DIFFICULTY_LABELS).map(([value, label]) => ({
                        value,
                        label
                    }))
                },
                {
                    key: 'mode',
                    question: 'How shall I show the questions?',
                    options: [
                        {value: 'tutor', label: '🪄 One at a time'},
                        {value: 'homework', label: '📄 All together'}
                    ]
                }
            ];
        }

        function isHomeworkGuideComplete() {
            const answers = homeworkGuideState.answers;
            return Number.isInteger(Number(answers.year_group))
                && Number(answers.year_group) >= 1
                && Number(answers.year_group) <= 6
                && primarySubjects.includes(answers.subject)
                && Object.prototype.hasOwnProperty.call(HOMEWORK_SESSION_QUESTIONS, Number(answers.session_minutes))
                && Object.prototype.hasOwnProperty.call(HOMEWORK_DIFFICULTY_LABELS, answers.difficulty)
                && (answers.mode === 'homework' || answers.mode === 'tutor');
        }

        function appendHomeworkSummaryItem(list, label, value) {
            const item = document.createElement('li');
            const strong = document.createElement('strong');
            strong.textContent = `${label}: `;
            item.append(strong, document.createTextNode(String(value)));
            list.appendChild(item);
        }

        function renderHomeworkGuideSummary() {
            const summary = document.getElementById('homework-guide-summary');
            if (!summary) return;
            const answers = homeworkGuideState.answers;
            summary.replaceChildren();

            const title = document.createElement('h3');
            title.textContent = 'Your homework plan';
            summary.appendChild(title);

            const list = document.createElement('ul');
            list.className = 'guide-summary-list';
            appendHomeworkSummaryItem(list, 'Year', `Year ${answers.year_group}`);
            appendHomeworkSummaryItem(list, 'Subject', answers.subject);
            appendHomeworkSummaryItem(list, 'Time', `${answers.session_minutes} minutes`);
            appendHomeworkSummaryItem(list, 'Level', HOMEWORK_DIFFICULTY_LABELS[answers.difficulty]);
            const modeStep = getHomeworkGuideSteps().find(step => step.key === 'mode');
            const modeOptions = modeStep && Array.isArray(modeStep.options)
                ? modeStep.options
                : [];
            const modeOption = modeOptions.find(option => option.value === answers.mode);
            appendHomeworkSummaryItem(
                list,
                'Style',
                modeOption && modeOption.label ? modeOption.label : answers.mode
            );
            summary.appendChild(list);
        }

        function renderHomeworkQuickStart() {
            const answers = homeworkGuideState.answers;
            const title = document.getElementById('homework-quick-title');
            const detail = document.getElementById('homework-quick-detail');
            if (!title || !detail) return;
            title.textContent = `Ready for Year ${answers.year_group} ${answers.subject} for ${answers.session_minutes} minutes?`;
            const style = answers.mode === 'tutor' ? '🪄 One at a time' : '📄 All together';
            detail.textContent = `${HOMEWORK_DIFFICULTY_LABELS[answers.difficulty]} · ${style}. Tap Start now, or change your choices.`;
        }

        function hideLegacyHomeworkQuestionStyle() {
            const questionStyle = document.getElementById('homework-question-style');
            if (!questionStyle) return;

            // Keep the old select in the page for compatibility with older
            // handlers, but move its choice into the guided homework steps.
            questionStyle.value = homeworkGuideState.answers.mode === 'tutor' ? 'tutor' : 'homework';
            const wrapper = questionStyle.closest(
                '.form-group, .field-group, .setting-row, .settings-row, .parent-setting'
            );
            if (wrapper) {
                wrapper.hidden = true;
                wrapper.style.display = 'none';
                return;
            }

            const label = document.querySelector('label[for="homework-question-style"]');
            if (label) {
                label.hidden = true;
                label.style.display = 'none';
            }
            questionStyle.hidden = true;
            questionStyle.style.display = 'none';
        }

        function renderHomeworkGuide() {
            const panel = document.getElementById('homework-guide-panel');
            const quickStart = document.getElementById('homework-quick-start');
            const question = document.getElementById('homework-guide-question');
            const optionsContainer = document.getElementById('homework-guide-options');
            const stepLabel = document.getElementById('homework-guide-step-label');
            const progress = document.getElementById('homework-guide-progress');
            const summary = document.getElementById('homework-guide-summary');
            const backButton = document.getElementById('homework-guide-back');
            const startButton = document.getElementById('homework-guide-start');
            if (!panel || !quickStart || !question || !optionsContainer || !stepLabel
                || !progress || !summary || !backButton || !startButton) {
                return;
            }

            if (homeworkGuideState.showQuickStart && isHomeworkGuideComplete()) {
                panel.hidden = true;
                quickStart.hidden = false;
                renderHomeworkQuickStart();
                return;
            }

            panel.hidden = false;
            quickStart.hidden = true;
            const steps = getHomeworkGuideSteps();
            const isSummary = homeworkGuideState.stepIndex >= steps.length;
            const completed = Math.min(homeworkGuideState.stepIndex + 1, steps.length);
            progress.style.width = `${(completed / steps.length) * 100}%`;

            if (isSummary) {
                stepLabel.textContent = 'Ready to start';
                question.textContent = 'Great! I have made your homework plan.';
                optionsContainer.replaceChildren();
                optionsContainer.hidden = true;
                summary.hidden = false;
                startButton.hidden = false;
                backButton.hidden = false;
                renderHomeworkGuideSummary();
                return;
            }

            const step = steps[homeworkGuideState.stepIndex];
            stepLabel.textContent = `Step ${homeworkGuideState.stepIndex + 1} of ${steps.length}`;
            question.textContent = step.question;
            optionsContainer.hidden = false;
            summary.hidden = true;
            startButton.hidden = true;
            backButton.hidden = homeworkGuideState.stepIndex === 0;
            optionsContainer.replaceChildren();

            step.options.forEach(option => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'guide-option';
                button.textContent = option.label;
                const isMoreButton = option.value === '__more__';
                const isSelected = !isMoreButton
                    && String(homeworkGuideState.answers[step.key]) === String(option.value);
                button.setAttribute('aria-pressed', String(isSelected));
                if (isSelected) button.classList.add('selected');
                button.addEventListener('click', () => {
                    if (isMoreButton) {
                        homeworkGuideState.showAllSubjects = true;
                        renderHomeworkGuide();
                        return;
                    }
                    homeworkGuideState.answers[step.key] = option.value;
                    if (step.key === 'mode') {
                        const questionStyle = document.getElementById('homework-question-style');
                        if (questionStyle) questionStyle.value = option.value;
                    }
                    homeworkGuideState.stepIndex += 1;
                    if (homeworkGuideState.stepIndex >= steps.length) {
                        saveLearningChoices();
                    }
                    renderHomeworkGuide();
                });
                optionsContainer.appendChild(button);
            });
        }

        function previousHomeworkGuideStep() {
            if (homeworkGuideState.stepIndex > 0) {
                homeworkGuideState.stepIndex -= 1;
                renderHomeworkGuide();
            }
        }

        function changeHomeworkGuide() {
            homeworkGuideState.showQuickStart = false;
            homeworkGuideState.stepIndex = 0;
            renderHomeworkGuide();
        }

        const elevenGuideState = {
            stepIndex: 0,
            answers: {},
            showQuickStart: false
        };

        function getElevenGuideSteps() {
            return [
                {
                    key: 'year_group',
                    question: 'Hi! What year are you in?',
                    options: [3, 4, 5, 6].map(year => ({
                        value: year,
                        label: `Year ${year}`
                    }))
                },
                {
                    key: 'subject',
                    question: 'Which subject would you like to practise?',
                    options: elevenPlusSubjects.map(subject => ({
                        value: subject,
                        label: subject
                    }))
                },
                {
                    key: 'confidence',
                    question: 'How does this subject feel today?',
                    options: [
                        { value: 'confident', label: '😊 I feel confident' },
                        { value: 'sometimes_tricky', label: '😐 Sometimes tricky' },
                        { value: 'needs_help', label: '🌱 I need some help' }
                    ]
                },
                {
                    key: 'question_count',
                    question: 'How long shall we practise?',
                    options: [
                        {value: 10, label: '10 minutes · Quick'},
                        {value: 15, label: '15 minutes · Longer'}
                    ]
                },
                {
                    key: 'mode',
                    question: 'How shall I show the questions?',
                    options: [
                        { value: 'tutor', label: '🪄 One at a time' },
                        { value: 'homework', label: '📄 All together' }
                    ]
                }
            ];
        }

        function findElevenGuideLabel(step, value) {
            const option = step.options.find(item => String(item.value) === String(value));
            return option ? option.label : String(value || '');
        }

        function appendElevenSummaryItem(list, label, value) {
            if (!value) return;
            const item = document.createElement('li');
            const strong = document.createElement('strong');
            strong.textContent = `${label}: `;
            item.append(strong, document.createTextNode(String(value)));
            list.appendChild(item);
        }

        function renderElevenGuideSummary(steps) {
            const summary = document.getElementById('eleven-guide-summary');
            if (!summary) return;
            summary.replaceChildren();

            const title = document.createElement('h3');
            title.textContent = 'Your practice plan';
            summary.appendChild(title);

            const list = document.createElement('ul');
            list.className = 'guide-summary-list';
            appendElevenSummaryItem(list, 'Year', findElevenGuideLabel(steps[0], elevenGuideState.answers.year_group));
            appendElevenSummaryItem(list, 'Subject', findElevenGuideLabel(steps[1], elevenGuideState.answers.subject));
            appendElevenSummaryItem(list, 'How it feels', findElevenGuideLabel(steps[2], elevenGuideState.answers.confidence));
            appendElevenSummaryItem(list, 'Practice', findElevenGuideLabel(steps[3], elevenGuideState.answers.question_count));
            appendElevenSummaryItem(list, 'Style', findElevenGuideLabel(steps[4], elevenGuideState.answers.mode));

            const examBoardInput = document.getElementById('eleven-exam-board');
            const examDateInput = document.getElementById('eleven-exam-date');
            const targetSchoolInput = document.getElementById('eleven-target-school');
            const examBoard = examBoardInput ? examBoardInput.value : '';
            const examDate = examDateInput ? examDateInput.value : '';
            const targetSchool = targetSchoolInput ? targetSchoolInput.value.trim() : '';
            if (examBoard && examBoard !== 'Not sure') appendElevenSummaryItem(list, 'Exam format', examBoard);
            if (examDate) appendElevenSummaryItem(list, 'Exam date', examDate);
            if (targetSchool) appendElevenSummaryItem(list, 'Target school', targetSchool);
            summary.appendChild(list);
        }

        function getElevenGuidePanel() {
            const question = document.getElementById('eleven-guide-question');
            if (!question) return null;
            return document.getElementById('eleven-guide-panel')
                || question.closest('.guide-panel')
                || question.parentElement;
        }

        function setElementHidden(element, hidden) {
            if (!element) return;
            element.hidden = hidden;
            // Some page styles set display on cards and override the browser's
            // default [hidden] rule. Set display as well so the two 11+ states
            // can never appear together or leave an empty card behind.
            element.style.display = hidden ? 'none' : '';
        }

        function ensureElevenQuickStart() {
            const panel = getElevenGuidePanel();
            if (!panel || !panel.parentElement) return null;

            let quickStart = document.getElementById('eleven-quick-start');
            if (!quickStart) {
                quickStart = document.createElement('section');
                quickStart.id = 'eleven-quick-start';
            }

            quickStart.className = 'quick-start-card';

            // Keep quick start outside the editor, just like Make Homework.
            // Older HTML/JS versions may already have placed it inside the
            // editor; moving the same node also avoids duplicate cards.
            if (quickStart.parentElement !== panel.parentElement
                || quickStart.nextElementSibling !== panel) {
                panel.parentElement.insertBefore(quickStart, panel);
            }

            // Rebuild once so pre-existing page markup cannot leave an
            // unbound "Change it" button.
            if (quickStart.dataset.elevenQuickStartReady !== 'true') {
                const title = document.createElement('h3');
                title.id = 'eleven-quick-title';

                const detail = document.createElement('p');
                detail.id = 'eleven-quick-detail';

                const actions = document.createElement('div');
                actions.className = 'quick-start-actions';

                const startButton = document.createElement('button');
                startButton.type = 'button';
                startButton.id = 'eleven-quick-start-button';
                startButton.className = 'btn btn-primary';
                startButton.textContent = 'Start now';
                startButton.addEventListener('click', generateCustomHomeworkEleven);

                const changeButton = document.createElement('button');
                changeButton.type = 'button';
                changeButton.id = 'eleven-quick-change-button';
                changeButton.className = 'btn btn-secondary';
                changeButton.textContent = 'Change it';
                changeButton.addEventListener('click', changeElevenGuide);

                actions.append(startButton, changeButton);
                quickStart.replaceChildren(title, detail, actions);
                quickStart.dataset.elevenQuickStartReady = 'true';
            }

            return quickStart;
        }

        function setElevenGuideControlsHidden(hidden) {
            const controlIds = [
                'eleven-guide-step-label',
                'eleven-guide-question',
                'eleven-guide-options',
                'eleven-guide-summary',
                'eleven-guide-back',
                'eleven-guide-start'
            ];
            controlIds.forEach(id => {
                const element = document.getElementById(id);
                setElementHidden(element, hidden);
            });

            const progress = document.getElementById('eleven-guide-progress');
            if (progress) {
                const progressContainer = progress.closest('.guide-progress') || progress;
                setElementHidden(progressContainer, hidden);
            }
        }

        function renderElevenQuickStart(steps) {
            const answers = elevenGuideState.answers;
            const title = document.getElementById('eleven-quick-title');
            const detail = document.getElementById('eleven-quick-detail');
            if (!title || !detail) return;

            const year = findElevenGuideLabel(steps[0], answers.year_group);
            const subject = findElevenGuideLabel(steps[1], answers.subject);
            const questionCount = findElevenGuideLabel(steps[3], answers.question_count);
            const mode = findElevenGuideLabel(steps[4], answers.mode);
            title.textContent = `Ready for ${year} 11+ ${subject}?`;
            detail.textContent = `${questionCount} · ${mode}. Tap Start now, or change your choices.`;
        }

        function renderElevenGuide() {
            const question = document.getElementById('eleven-guide-question');
            const optionsContainer = document.getElementById('eleven-guide-options');
            const stepLabel = document.getElementById('eleven-guide-step-label');
            const progress = document.getElementById('eleven-guide-progress');
            const summary = document.getElementById('eleven-guide-summary');
            const backButton = document.getElementById('eleven-guide-back');
            const startButton = document.getElementById('eleven-guide-start');
            if (!question || !optionsContainer || !stepLabel || !progress || !summary || !backButton || !startButton) {
                return;
            }

            const steps = getElevenGuideSteps();
            const quickStart = ensureElevenQuickStart();
            const panel = getElevenGuidePanel();
            if (elevenGuideState.showQuickStart && isElevenGuideComplete()) {
                // A saved plan uses only the compact Start now / Change it
                // card. Hide legacy summary and navigation controls even on
                // older page structures where they sit outside the panel.
                setElevenGuideControlsHidden(true);
                setElementHidden(panel, true);
                setElementHidden(quickStart, false);
                renderElevenQuickStart(steps);
                return;
            }

            setElementHidden(quickStart, true);
            setElementHidden(panel, false);
            // This remains as a compatibility fallback for older pages where
            // the guide controls do not share a dedicated panel.
            setElevenGuideControlsHidden(false);
            const isSummary = elevenGuideState.stepIndex >= steps.length;
            const completed = Math.min(elevenGuideState.stepIndex + 1, steps.length);
            progress.style.width = `${(completed / steps.length) * 100}%`;

            if (isSummary) {
                stepLabel.textContent = 'Ready to start';
                question.textContent = 'Brilliant! I have made your practice plan.';
                optionsContainer.replaceChildren();
                optionsContainer.hidden = true;
                summary.hidden = false;
                startButton.hidden = false;
                backButton.hidden = false;
                renderElevenGuideSummary(steps);
                return;
            }

            const step = steps[elevenGuideState.stepIndex];
            stepLabel.textContent = `Step ${elevenGuideState.stepIndex + 1} of ${steps.length}`;
            question.textContent = step.question;
            optionsContainer.hidden = false;
            summary.hidden = true;
            startButton.hidden = true;
            backButton.hidden = elevenGuideState.stepIndex === 0;
            optionsContainer.replaceChildren();

            step.options.forEach(option => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'guide-option';
                button.textContent = option.label;
                const isSelected = String(elevenGuideState.answers[step.key]) === String(option.value);
                button.setAttribute('aria-pressed', String(isSelected));
                if (isSelected) button.classList.add('selected');
                button.addEventListener('click', () => {
                    elevenGuideState.answers[step.key] = option.value;
                    elevenGuideState.stepIndex += 1;
                    if (elevenGuideState.stepIndex >= steps.length) {
                        saveLearningChoices();
                    }
                    renderElevenGuide();
                });
                optionsContainer.appendChild(button);
            });
        }

        function previousElevenGuideStep() {
            if (elevenGuideState.stepIndex > 0) {
                elevenGuideState.stepIndex -= 1;
                renderElevenGuide();
            }
        }

        function changeElevenGuide() {
            elevenGuideState.showQuickStart = false;
            elevenGuideState.stepIndex = 0;
            setElementHidden(document.getElementById('eleven-quick-start'), true);
            setElementHidden(getElevenGuidePanel(), false);
            renderElevenGuide();
        }

        function isElevenGuideComplete() {
            return getElevenGuideSteps().every(step =>
                step.options.some(option =>
                    String(option.value) === String(elevenGuideState.answers[step.key])
                )
            );
        }

        // Get the server-resolved learner ID. It is backed by an HttpOnly
        // cookie and is never derived from an IP address.
        async function getEffectiveStudentId() {
            if (anonymousClientId) return anonymousClientId;
            try {
                const resp = await fetch('/api/client-id', {credentials: 'same-origin'});
                const data = await resp.json();
                anonymousClientId = data.client_id || null;
                return anonymousClientId;
            } catch (error) {
                console.error('Failed to get learner ID:', error);
                return null;
            }
        }

        function getEffectiveStudentIdSync() {
            return anonymousClientId;
        }

        function getLearnerReviewProfile() {
            const source = currentProfile && typeof currentProfile === 'object' ? currentProfile : {};
            const rawYear = Number(source.year_group);
            const yearGroup = Number.isFinite(rawYear) ? Math.min(6, Math.max(1, Math.round(rawYear))) : 3;
            const rawAge = Number(source.age);
            const age = Number.isFinite(rawAge) ? Math.min(11, Math.max(5, Math.round(rawAge))) : Math.min(11, yearGroup + 4);
            const profile = { year_group: yearGroup, age: age };
            if (Number.isFinite(Number(source.plan_week))) {
                profile.plan_week = Math.min(52, Math.max(1, Math.round(Number(source.plan_week))));
            }
            if (typeof source.plan_phase === 'string') profile.plan_phase = source.plan_phase.slice(0, 40);
            if (Array.isArray(source.learning_goals)) {
                profile.learning_goals = source.learning_goals.slice(0, 4).map(item => String(item).slice(0, 100));
            }
            return profile;
        }


        // Subscription status
        let hasSubscription = null; // null = 未检查, true/false = 已检查
        const HOMEWORK_PREMIUM_PLAN = 'homework_monthly';
        const ELEVENPLUS_PREMIUM_PLAN = 'elevenplus_monthly';
        const PREMIUM_PLAN_NAMES = {
            [HOMEWORK_PREMIUM_PLAN]: 'Homework Premium',
            [ELEVENPLUS_PREMIUM_PLAN]: '11+ Premium'
        };
        const LEARNING_CHOICES_KEY = 'homeworkMagic.learningChoices.v1';

        function loadLearningChoices() {
            try {
                const value = JSON.parse(localStorage.getItem(LEARNING_CHOICES_KEY) || '{}');
                return value && typeof value === 'object' ? value : {};
            } catch (error) {
                console.warn('Could not read saved learning choices:', error);
                return {};
            }
        }

        function saveLearningChoices() {
            const existing = loadLearningChoices();
            delete existing.homeworkPrompt;
            delete existing.elevenPrompt;
            const elevenSubject = elevenGuideState.answers.subject
                || getSelectedSubjects('eleven-subjects')[0];
            const value = {
                ...existing,
                elevenSubject: elevenSubject || existing.elevenSubject || 'Maths'
            };
            const answers = homeworkGuideState.answers;
            const yearGroup = Number(answers.year_group);
            const sessionMinutes = Number(answers.session_minutes);
            if (Number.isInteger(yearGroup) && yearGroup >= 1 && yearGroup <= 6) {
                value.homeworkYear = yearGroup;
            }
            const homeworkGridSubject = getSelectedSubjects('homework-subjects')[0];
            if (typeof answers.subject === 'string' && answers.subject) {
                value.homeworkSubject = answers.subject;
            }
            if (homeworkGridSubject) {
                value.homeworkQuickSubject = homeworkGridSubject;
            }
            if (Object.prototype.hasOwnProperty.call(HOMEWORK_SESSION_QUESTIONS, sessionMinutes)) {
                value.homeworkMinutes = sessionMinutes;
            }
            if (Object.prototype.hasOwnProperty.call(HOMEWORK_DIFFICULTY_LABELS, answers.difficulty)) {
                value.homeworkDifficulty = answers.difficulty;
            }
            const homeworkQuestionStyle = document.getElementById('homework-question-style');
            const homeworkMode = answers.mode
                || (homeworkQuestionStyle ? homeworkQuestionStyle.value : '');
            if (homeworkMode === 'homework' || homeworkMode === 'tutor') {
                value.homeworkMode = homeworkMode;
            }
            const homeworkYearInput = document.getElementById('homework-year');
            const homeworkQuickYear = Number(homeworkYearInput ? homeworkYearInput.value : NaN);
            const homeworkQuickMode = getSelectedMode('homework-quick-mode');
            if (Number.isInteger(homeworkQuickYear) && homeworkQuickYear >= 1 && homeworkQuickYear <= 6) {
                value.homeworkQuickYear = homeworkQuickYear;
            }
            if (homeworkQuickMode === 'homework' || homeworkQuickMode === 'tutor') {
                value.homeworkQuickMode = homeworkQuickMode;
            }

            const elevenAnswers = elevenGuideState.answers;
            const elevenYear = Number(elevenAnswers.year_group);
            const elevenQuestionCount = Number(elevenAnswers.question_count);
            if ([3, 4, 5, 6].includes(elevenYear)) {
                value.elevenYear = elevenYear;
            }
            if (typeof elevenAnswers.subject === 'string' && elevenAnswers.subject.trim()) {
                value.elevenSubject = elevenAnswers.subject.trim();
            }
            if (['confident', 'sometimes_tricky', 'needs_help'].includes(elevenAnswers.confidence)) {
                value.elevenConfidence = elevenAnswers.confidence;
            }
            if ([5, 8].includes(elevenQuestionCount)) {
                value.elevenQuestionCount = elevenQuestionCount;
            }
            if (elevenAnswers.mode === 'homework' || elevenAnswers.mode === 'tutor') {
                value.elevenMode = elevenAnswers.mode;
            }
            const elevenYearInput = document.getElementById('eleven-year');
            const elevenQuickYear = Number(elevenYearInput ? elevenYearInput.value : NaN);
            const elevenQuickMode = getSelectedMode('eleven-quick-mode');
            if ([3, 4, 5, 6].includes(elevenQuickYear)) {
                value.elevenQuickYear = elevenQuickYear;
            }
            if (elevenQuickMode === 'homework' || elevenQuickMode === 'tutor') {
                value.elevenQuickMode = elevenQuickMode;
            }
            try {
                localStorage.setItem(LEARNING_CHOICES_KEY, JSON.stringify(value));
            } catch (error) {
                console.warn('Could not save learning choices:', error);
            }
        }

        function restoreLearningChoices() {
            const saved = loadLearningChoices();
            let removedLegacyText = false;
            ['homeworkPrompt', 'elevenPrompt'].forEach(key => {
                if (!Object.prototype.hasOwnProperty.call(saved, key)) return;
                removedLegacyText = true;
                delete saved[key];
            });
            if (removedLegacyText) {
                try {
                    localStorage.setItem(LEARNING_CHOICES_KEY, JSON.stringify(saved));
                } catch (error) {
                    console.warn('Could not remove an old learner description:', error);
                }
            }

            const yearGroup = Number(saved.homeworkYear);
            const sessionMinutes = Number(saved.homeworkMinutes);
            if (Number.isInteger(yearGroup) && yearGroup >= 1 && yearGroup <= 6) {
                homeworkGuideState.answers.year_group = yearGroup;
            }
            if (typeof saved.homeworkSubject === 'string' && saved.homeworkSubject.trim()) {
                homeworkGuideState.answers.subject = saved.homeworkSubject.trim();
                homeworkGuideState.showAllSubjects = !HOMEWORK_COMMON_SUBJECTS.includes(
                    homeworkGuideState.answers.subject
                );
            }
            if (Object.prototype.hasOwnProperty.call(HOMEWORK_SESSION_QUESTIONS, sessionMinutes)) {
                homeworkGuideState.answers.session_minutes = sessionMinutes;
            }
            if (Object.prototype.hasOwnProperty.call(HOMEWORK_DIFFICULTY_LABELS, saved.homeworkDifficulty)) {
                homeworkGuideState.answers.difficulty = saved.homeworkDifficulty;
            }
            if (saved.homeworkMode === 'homework' || saved.homeworkMode === 'tutor') {
                homeworkGuideState.answers.mode = saved.homeworkMode;
                const questionStyle = document.getElementById('homework-question-style');
                if (questionStyle) questionStyle.value = saved.homeworkMode;
            } else if (
                Number.isInteger(yearGroup)
                && typeof saved.homeworkSubject === 'string'
                && Object.prototype.hasOwnProperty.call(
                    HOMEWORK_SESSION_QUESTIONS, sessionMinutes
                )
                && Object.prototype.hasOwnProperty.call(
                    HOMEWORK_DIFFICULTY_LABELS, saved.homeworkDifficulty
                )
            ) {
                // Existing saved plans predate the display-style choice.
                homeworkGuideState.answers.mode = 'homework';
            }
            homeworkGuideState.showQuickStart = isHomeworkGuideComplete();

            const homeworkQuickYear = Number(saved.homeworkQuickYear);
            const homeworkYearSelect = document.getElementById('homework-year');
            if (homeworkYearSelect
                    && Number.isInteger(homeworkQuickYear)
                    && homeworkQuickYear >= 1
                    && homeworkQuickYear <= 6) {
                homeworkYearSelect.value = String(homeworkQuickYear);
            } else if (homeworkYearSelect
                    && Number.isInteger(yearGroup)
                    && yearGroup >= 1
                    && yearGroup <= 6) {
                homeworkYearSelect.value = String(yearGroup);
            }
            const homeworkQuickMode = saved.homeworkQuickMode || saved.homeworkMode;
            if (homeworkQuickMode === 'homework' || homeworkQuickMode === 'tutor') {
                const quickModeInput = document.querySelector(
                    `input[name="homework-quick-mode"][value="${homeworkQuickMode}"]`
                );
                if (quickModeInput) quickModeInput.checked = true;
            }

            const elevenYear = Number(saved.elevenYear);
            const elevenQuestionCount = Number(saved.elevenQuestionCount);
            if ([3, 4, 5, 6].includes(elevenYear)) {
                elevenGuideState.answers.year_group = elevenYear;
            }
            if (typeof saved.elevenSubject === 'string' && saved.elevenSubject.trim()) {
                elevenGuideState.answers.subject = saved.elevenSubject.trim();
            }
            if (['confident', 'sometimes_tricky', 'needs_help'].includes(saved.elevenConfidence)) {
                elevenGuideState.answers.confidence = saved.elevenConfidence;
            }
            if ([5, 8].includes(elevenQuestionCount)) {
                elevenGuideState.answers.question_count = elevenQuestionCount;
            }
            if (saved.elevenMode === 'homework' || saved.elevenMode === 'tutor') {
                elevenGuideState.answers.mode = saved.elevenMode;
            }
            elevenGuideState.showQuickStart = isElevenGuideComplete();

            const elevenQuickYear = Number(saved.elevenQuickYear);
            const elevenYearSelect = document.getElementById('eleven-year');
            if (elevenYearSelect && [3, 4, 5, 6].includes(elevenQuickYear)) {
                elevenYearSelect.value = String(elevenQuickYear);
            }
            const elevenQuickMode = saved.elevenQuickMode;
            if (elevenQuickMode === 'homework' || elevenQuickMode === 'tutor') {
                const quickModeInput = document.querySelector(
                    `input[name="eleven-quick-mode"][value="${elevenQuickMode}"]`
                );
                if (quickModeInput) quickModeInput.checked = true;
            }
        }

        function clearSavedLearningPrompts() {
            const saved = loadLearningChoices();
            delete saved.homeworkPrompt;
            delete saved.elevenPrompt;
            try {
                localStorage.setItem(LEARNING_CHOICES_KEY, JSON.stringify(saved));
            } catch (error) {
                console.warn('Could not clear saved learner descriptions:', error);
            }
        }

        function premiumPlanForContext(context = null) {
            const isElevenPlus = Boolean(
                context && context.is_eleven_plus
                || Array.isArray(currentHomework) && currentHomework.some(item => item && item.is_eleven_plus)
            );
            return isElevenPlus ? ELEVENPLUS_PREMIUM_PLAN : HOMEWORK_PREMIUM_PLAN;
        }

        // 检查订阅状态
        async function checkSubscription(plan = null) {
            if (plan === null && hasSubscription !== null) return hasSubscription;

            const url = plan ? `/api/check-subscription?plan=${encodeURIComponent(plan)}` : `/api/check-subscription`;
            try {
                const resp = await fetch(url);
                const data = await resp.json();
                const result = data.has_subscription === true;
                if (plan === null) hasSubscription = result;

                if (plan === 'elevenplus_monthly' && !result) {
                    console.warn('11+ Premium subscription check failed');
                }

                return result;
            } catch(e) {
                console.error('Failed to check subscription:', e);
                if (plan === null) hasSubscription = false;
                return false;
            }
        }

        // 检查是否需要订阅才能使用高级功能
        async function requireSubscription(featureName, isFree = false, plan = null) {
            if (isFree) return true;

            if (!currentStudentId) {
                redirectToLogin()
                return false;
            }
            const requiredPlan = plan || HOMEWORK_PREMIUM_PLAN;
            const subscribed = await checkSubscription(requiredPlan);
            if (!subscribed) {
                const planName = PREMIUM_PLAN_NAMES[requiredPlan] || 'Premium';
                alert(`${featureName} requires ${planName}. Please subscribe to continue.`);
                redirectToPricing();
                return false;
            }
            return true;
        }

        // 状态保存（用于在功能切换时保留答案和批改结果）
        let savedHomeworkState = null;

        const HOMEWORK_ACTION_BUTTONS_HTML = `
            <button class="btn btn-primary" onclick="reviewGeneratedHomework()">
                Quick Review
            </button>
            <button class="btn btn-secondary" onclick="clearResults()">
                New Homework
            </button>
            <button class="btn btn-secondary" onclick="ExplainDeep()">
                Explain in Detail
            </button>
            <button class="btn btn-secondary" onclick="ImprovePractice()">
                Help me improve
            </button>
            <button class="btn btn-secondary" onclick="TrackProgress()">
                Track Progress
            </button>
        `;

        function resetHomeworkActionButtons() {
            const buttonArea = document.getElementById('homework-buttons');
            if (!buttonArea) return;
            buttonArea.innerHTML = HOMEWORK_ACTION_BUTTONS_HTML;
            buttonArea.style.display = 'block';
        }


        function getAnswerStorageKey(input, index = 0) {
            if (!input) return `answer-${index}`;
            return input.dataset.answerKey || input.id ||
                `${input.dataset.subject || 'answer'}-${input.dataset.homeworkIndex || '0'}-${input.dataset.questionIndex || index}`;
        }

        function captureVisibleAnswers(target = {}) {
            document.querySelectorAll('.answer-input-inline').forEach((input, index) => {
                target[getAnswerStorageKey(input, index)] = input.value;
            });
            return target;
        }

        function restoreVisibleAnswers(savedAnswers) {
            if (!savedAnswers || typeof savedAnswers !== 'object') return;
            document.querySelectorAll('.answer-input-inline').forEach((input, index) => {
                const key = getAnswerStorageKey(input, index);
                const legacyKey = input.dataset.subject;
                if (savedAnswers[key] !== undefined) input.value = savedAnswers[key];
                else if (legacyKey && savedAnswers[legacyKey] !== undefined) input.value = savedAnswers[legacyKey];
            });
        }

        function saveStateToSessionStorage() {
            const state = {
                homework: currentHomework,
                profile: currentProfile,
                subject: currentSubject,
                answers: {},
                reviewHTML: document.getElementById('review-result').innerHTML,
                mode: currentHomeworkMode,
                questionIndex: currentQuestionIndex,
                questionAnswers: currentQuestionAnswers
            };
            captureVisibleAnswers(state.answers);
            try {
                sessionStorage.setItem('homeworkState', JSON.stringify(state));
            } catch(e) {
                console.error('Failed to save state to sessionStorage:', e);
            }
        }

        function safeNextPath(path) {
            return typeof path === 'string' && path.startsWith('/') && !path.startsWith('//')
                ? path : '/app';
        }

        function redirectToLogin(resumeSessionId = null) {
            saveStateToSessionStorage();
            const next = resumeSessionId
                ? `/app?resume_session=${encodeURIComponent(resumeSessionId)}`
                : '/app';
            sessionStorage.setItem('postLoginPath', next);
            window.location.assign(`/login?next=${encodeURIComponent(safeNextPath(next))}`);
        }

        function redirectToPricing(resumeSessionId = null) {
            saveStateToSessionStorage();
            if (resumeSessionId) sessionStorage.setItem('resumeSessionId', resumeSessionId);
            window.location.assign('/pricing');
        }

        async function restoreResumableSession() {
            const params = new URLSearchParams(window.location.search);
            const sessionId = params.get('resume_session') || sessionStorage.getItem('resumeSessionId');
            if (!sessionId) return false;
            try {
                let response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/claim`, {
                    method: 'POST', credentials: 'same-origin'
                });
                if (response.status === 404 || response.status === 401) {
                    response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
                        credentials: 'same-origin'
                    });
                }
                const data = await response.json().catch(() => ({}));
                if (!response.ok || !data.success || !data.session) return false;
                const session = data.session;
                currentHomework = session.homework || [];
                currentProfile = session.profile || {};
                currentHomeworkMode = session.mode || 'homework';
                currentQuestionIndex = 0;
                currentQuestionAnswers = {};
                if (currentHomeworkMode === 'tutor') displayTutorQuestion(0);
                else displayHomework(currentHomework);
                sessionStorage.removeItem('resumeSessionId');
                history.replaceState({}, '', '/app');
                return true;
            } catch (error) {
                console.error('Could not restore saved homework:', error);
                return false;
            }
        }

        function saveCurrentState() {
            if (savedHomeworkState) return;
            savedHomeworkState = {
                answers: {},
                reviewHTML: document.getElementById('review-result').innerHTML,
            };
            captureVisibleAnswers(savedHomeworkState.answers);
        }

        function restoreSavedState() {
            if (!savedHomeworkState) return false;
            restoreVisibleAnswers(savedHomeworkState.answers);
            document.getElementById('review-result').innerHTML = savedHomeworkState.reviewHTML || '';
            return true;
        }

        function clearSavedState() {
            savedHomeworkState = null;
        }

        // Configure marked for better line breaks and open links in new tab
        const renderer = new marked.Renderer();
        renderer.link = function(href, title, text) {
            let link = '<a href="' + href + '" target="_blank" rel="noopener noreferrer"';
            if (title) {
                link += ' title="' + title + '"';
            }
            link += '>' + text + '</a>';
            return link;
        };
        marked.setOptions({
            breaks: true,
            gfm: true,
            renderer: renderer
        });

        // Initialize subjects and check dev mode
        document.addEventListener('DOMContentLoaded', async function() {
            restoreLearningChoices();
            hideLegacyHomeworkQuestionStyle();
            renderHomeworkGuide();
            renderElevenGuide();
            // The API can add more subjects later, but the selectors should
            // never start empty while an older or slower device is waiting.
            renderDefaultSubjectButtons();
            loadSubjects();
            const homeworkQuestionStyle = document.getElementById('homework-question-style');
            if (homeworkQuestionStyle) {
                homeworkQuestionStyle.addEventListener('change', saveLearningChoices);
            }
            const elevenYear = document.getElementById('eleven-year');
            if (elevenYear) {
                elevenYear.addEventListener('change', saveLearningChoices);
            }
            document.querySelectorAll('input[name="eleven-quick-mode"]').forEach(input => {
                input.addEventListener('change', saveLearningChoices);
            });
            ['eleven-exam-board', 'eleven-exam-date', 'eleven-target-school'].forEach(elementId => {
                const field = document.getElementById(elementId);
                if (!field) return;
                const eventName = field.tagName === 'INPUT' && field.type === 'text' ? 'input' : 'change';
                field.addEventListener(eventName, () => {
                    if (elevenGuideState.stepIndex >= getElevenGuideSteps().length) {
                        renderElevenGuide();
                    }
                });
            });
            checkAdminAccess(); // Show admin tools only to configured administrators
            const resumedPendingHomework = await restoreResumableSession();

            // Update UI based on login status
            if (currentStudentId) {
                document.getElementById('logout-link').style.display = 'block';
                document.querySelector('nav.nav-links a[href="/login"]').style.display = 'none';
                document.querySelector('nav.nav-links a[href="/register"]').style.display = 'none';
            }

            // Check for tab parameter in URL
            const urlParams = new URLSearchParams(window.location.search);
            const tabParam = urlParams.get('tab');
            if (tabParam) {
                setTimeout(() => switchTab(tabParam), 100);
            }

            // Restore local UI state only when no server-side pending homework won.
            try {
                const savedStr = resumedPendingHomework ? null : sessionStorage.getItem('homeworkState');
                if (savedStr) {
                    sessionStorage.removeItem('homeworkState');
                    const state = JSON.parse(savedStr);
                    if (state.homework && state.homework.length > 0) {
                        const restore = () => {
                            currentHomework = state.homework;
                            currentProfile = state.profile;
                            currentSubject = state.subject || 'Maths';
                            currentHomeworkMode = state.mode || 'homework';
                            if (currentHomeworkMode === 'tutor') {
                                currentQuestionIndex = state.questionIndex || 0;
                                currentQuestionAnswers = state.questionAnswers || {};
                                displayTutorQuestion(currentQuestionIndex);
                            } else {
                                displayHomework(state.homework);
                            }

                            setTimeout(() => {
                                restoreVisibleAnswers(state.answers);
                                if (window.HomeworkQuestionRenderer) {
                                    window.HomeworkQuestionRenderer.restoreFromProxies(document);
                                }
                                if (state.reviewHTML) {
                                    document.getElementById('review-result').innerHTML = state.reviewHTML;
                                }
                            }, 50);
                        };

                        if (document.getElementById('homework-results')) {
                            setTimeout(restore, 200);
                        } else {
                            setTimeout(restore, 500);
                        }
                    }
                }
            } catch(e) {
                console.error('Failed to restore state from sessionStorage:', e);
                sessionStorage.removeItem('homeworkState');
            }
        });

        // Logout functionality
        document.getElementById('logout-link').addEventListener('click', async function(event) {
            event.preventDefault();
            try {
                await fetch('/api/logout', {method: 'POST', credentials: 'same-origin'});
            } catch (error) {
                console.error('Logout request failed:', error);
            }
            localStorage.removeItem('student_id');
            localStorage.removeItem('student_email');
            localStorage.removeItem('auth_state');
            clearSavedLearningPrompts();
            currentStudentId = null;
            currentStudentEmail = null;
            hasSubscription = null;
            window.location.assign('/');
        });

        // Input method handling
        function setInputMethod(method, selectedButton = null) {
            currentInputMethod = method;

            document.querySelectorAll('.input-method-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            if (selectedButton) selectedButton.classList.add('active');

            document.querySelectorAll('.input-method-content').forEach(content => {
                content.style.display = 'none';
            });

            document.getElementById('input-' + method).style.display = 'block';

            const subjectGroup = document.getElementById('review-subject-group');
            if (subjectGroup) subjectGroup.style.display = method === 'file' ? 'none' : 'block';
        }

        // Photo handling
        function handlePhotoSelect(event) {
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function(e) {
                currentPhotoData = e.target.result;

                document.getElementById('photo-img').src = currentPhotoData;
                document.getElementById('photo-preview').style.display = 'block';
                document.querySelector('#input-photo .upload-placeholder').style.display = 'none';

                photoUploadPromise = processPhoto(currentPhotoData);
            };
            reader.readAsDataURL(file);
        }

        function clearPhoto() {
            currentPhotoData = null;
            extractedContent = '';
            photoUploadPromise = null;
            document.getElementById('photo-preview').style.display = 'none';
            document.querySelector('#input-photo .upload-placeholder').style.display = 'block';
            document.getElementById('photo-input').value = '';
        }

        async function processPhoto(dataUrl) {
            showLoading();

            try {
                const response = await fetch('/api/upload-photo', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ photo: dataUrl })
                });

                const data = await response.json().catch(() => ({}));

                if (!response.ok || !data.success) {
                    throw new Error(getApiErrorMessage(data, 'We could not read that photo.'));
                }
                extractedContent = String(data.content || '').trim();
                if (!extractedContent) {
                    throw new Error('The photo did not contain any readable text.');
                }
                return true;
            } catch (error) {
                console.error('Photo processing failed:', error);
                extractedContent = '';
                alert(error.message || 'We could not read that photo.');
                return false;
            } finally {
                photoUploadPromise = null;
                hideLoading();
            }
        }

        // File handling
        function handleFileSelect(event) {
            const file = event.target.files[0];
            if (!file) return;

            currentFileData = file;

            document.getElementById('file-name').textContent = file.name;
            document.getElementById('file-info').style.display = 'block';
            document.querySelector('#input-file .upload-placeholder').style.display = 'none';

            fileUploadPromise = processFile(file);
        }

        function clearFile() {
            currentFileData = null;
            extractedContent = '';
            fileUploadPromise = null;
            document.getElementById('file-info').style.display = 'none';
            document.querySelector('#input-file .upload-placeholder').style.display = 'block';
            document.getElementById('file-input').value = '';
            const preview = document.getElementById('uploaded-homework-preview');
            const previewText = document.getElementById('review-uploaded-homework');
            if (preview) preview.style.display = 'none';
            if (previewText) previewText.value = '';
        }

        function getApiErrorMessage(data, fallbackMessage) {
            if (!data) return fallbackMessage;

            const detail = data.error !== null && data.error !== undefined
                ? data.error
                : (data.detail !== null && data.detail !== undefined
                    ? data.detail
                    : data.message);
            if (typeof detail === 'string' && detail.trim()) {
                return detail.trim();
            }
            if (Array.isArray(detail)) {
                const messages = detail
                    .map(item => {
                        if (typeof item === 'string') return item;
                        if (item && typeof item === 'object') return item.msg || item.message || '';
                        return '';
                    })
                    .filter(Boolean);
                if (messages.length) return messages.join(' ');
            }
            if (detail && typeof detail === 'object') {
                const message = detail.msg || detail.message;
                if (message) return String(message);
            }
            return fallbackMessage;
        }

        function splitUploadedHomeworkText(rawText) {
            const text = String(rawText || '').replace(/\r\n?/g, '\n').trim();
            if (!text) return { homework: '', answers: '', combined: false };

            const lines = text.split('\n');
            const isQuestionHeading = line => /^\s*(homework\s+)?(questions?|worksheet|problems?|tasks?)\s*:?\s*$/i.test(line);
            const isAnswerHeading = line => /^\s*((student|pupil)(?:'s)?\s+)?(answers?|responses?|solutions?)\s*:?\s*$/i.test(line);
            const questionHeadingIndex = lines.findIndex(isQuestionHeading);
            const answerHeadingIndex = lines.findIndex(isAnswerHeading);

            if (answerHeadingIndex >= 0) {
                const questionStart = questionHeadingIndex >= 0 && questionHeadingIndex < answerHeadingIndex
                    ? questionHeadingIndex + 1
                    : 0;
                const homework = lines
                    .slice(questionStart, answerHeadingIndex)
                    .filter(line => !isQuestionHeading(line))
                    .join('\n')
                    .trim();
                const answers = lines.slice(answerHeadingIndex + 1).join('\n').trim();
                if (homework && answers) return { homework, answers, combined: false };
            }

            const questionLines = [];
            const answerLines = [];
            let inlineAnswerCount = 0;
            lines.forEach(line => {
                const match = line.match(/^\s*((?:Q(?:uestion)?\s*)?\d+[.)]?\s*)?(.*?)\s+(?:answer|ans)\s*[:=-]\s*(.+)\s*$/i);
                if (!match) return;
                inlineAnswerCount += 1;
                const number = (match[1] || '').trim();
                questionLines.push(`${number ? number + ' ' : ''}${match[2].trim()}`.trim());
                answerLines.push(`${number ? number + ' ' : ''}${match[3].trim()}`.trim());
            });
            if (inlineAnswerCount > 0) {
                return {
                    homework: questionLines.join('\n'),
                    answers: answerLines.join('\n'),
                    combined: false
                };
            }

            return { homework: '', answers: text, combined: true };
        }

        async function processFile(file) {
            showLoading();

            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('/api/upload-file', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json().catch(() => ({}));

                if (!response.ok || !data.success) {
                    throw new Error(getApiErrorMessage(data, 'We could not read that file.'));
                }

                extractedContent = String(data.content || '').trim();
                if (!extractedContent) {
                    throw new Error('The file did not contain any readable text.');
                }
                const preview = document.getElementById('uploaded-homework-preview');
                const previewText = document.getElementById('review-uploaded-homework');
                if (previewText) previewText.value = extractedContent;
                if (preview) preview.style.display = 'block';
                return true;
            } catch (error) {
                console.error('File processing failed:', error);
                extractedContent = '';
                alert(error.message || 'We could not read that file.');
                return false;
            } finally {
                fileUploadPromise = null;
                hideLoading();
            }
        }

        function loadSubjects() {
            return fetch('/api/subjects')
                .then(response => response.json())
                .then(data => {
                    const saved = loadLearningChoices();
                    const loadedPrimarySubjects = Array.isArray(data.primary) && data.primary.length > 0
                        ? data.primary
                        : primarySubjects;
                    const loadedElevenPlusSubjects = Array.isArray(data.eleven_plus)
                        && data.eleven_plus.length > 0
                        ? data.eleven_plus
                        : elevenPlusSubjects;
                    if (loadedPrimarySubjects.length > 0) {
                        primarySubjects = loadedPrimarySubjects;
                        const selectedSubject = homeworkGuideState.answers.subject;
                        if (selectedSubject && !primarySubjects.includes(selectedSubject)) {
                            delete homeworkGuideState.answers.subject;
                            homeworkGuideState.showQuickStart = false;
                        } else if (selectedSubject) {
                            homeworkGuideState.showAllSubjects = !HOMEWORK_COMMON_SUBJECTS.includes(selectedSubject);
                        }
                        homeworkGuideState.showQuickStart = isHomeworkGuideComplete();
                        renderHomeworkGuide();
                    }
                    renderSubjects(
                        'homework-subjects',
                        loadedPrimarySubjects,
                        saved.homeworkQuickSubject || saved.homeworkSubject
                    );
                    renderSubjects(
                        'eleven-subjects',
                        loadedElevenPlusSubjects,
                        saved.elevenSubject
                    );
                    if (loadedElevenPlusSubjects.length > 0) {
                        elevenPlusSubjects = loadedElevenPlusSubjects;
                        const selectedSubject = elevenGuideState.answers.subject;
                        if (selectedSubject && !elevenPlusSubjects.includes(selectedSubject)) {
                            delete elevenGuideState.answers.subject;
                        }
                        renderElevenGuide();
                    }

                    const reviewSelect = document.getElementById('review-subject');
                    if (reviewSelect) {
                        reviewSelect.innerHTML = '';
                        const allSubjects = [
                            ...new Set([
                                ...loadedPrimarySubjects,
                                ...loadedElevenPlusSubjects
                            ])
                        ].sort();
                        allSubjects.forEach(subject => {
                            const option = document.createElement('option');
                            option.value = subject;
                            option.textContent = subject;
                            reviewSelect.appendChild(option);
                        });
                    }
                })
                .catch(error => console.error('Error loading subjects:', error));
        }

        function renderDefaultSubjectButtons() {
            const saved = loadLearningChoices();
            renderSubjects(
                'homework-subjects',
                primarySubjects,
                saved.homeworkQuickSubject || saved.homeworkSubject
            );
            renderSubjects('eleven-subjects', elevenPlusSubjects, saved.elevenSubject);
        }

        function renderSubjects(containerId, subjects, savedSubject = null) {
            const container = document.getElementById(containerId);
            if (!container) {
                console.error(`Subject container with id '${containerId}' not found.`);
                return;
            }
            const subjectList = Array.isArray(subjects) ? subjects : [];
            if (subjectList.length === 0) {
                container.innerHTML = '<p style="color: #999; text-align: center; grid-column: 1 / -1;">No subjects available to display.</p>';
                return;
            }

            const selectedSubject = subjectList.includes(savedSubject)
                ? savedSubject
                : (subjectList.includes('Maths') ? 'Maths' : subjectList[0]);
            container.innerHTML = subjectList.map(subject => {
                const isSelected = subject === selectedSubject;
                return `
                    <div class="subject-item ${isSelected ? 'selected' : ''}"
                         data-subject="${subject}"
                         onclick="toggleSubject(this, '${containerId}')">
                        ${subject}
                    </div>
                `;
            }).join('');
        }

        function toggleSubject(element, containerId) {
            const container = document.getElementById(containerId);
            container.querySelectorAll('.subject-item.selected').forEach(item => {
                item.classList.remove('selected');
            });
            element.classList.add('selected');
            saveLearningChoices();
        }

        function getSelectedSubjects(containerId) {
            const container = document.getElementById(containerId);
            if (!container) return [];
            const selected = container.querySelectorAll('.subject-item.selected');
            return Array.from(selected).map(el => el.dataset.subject);
        }

        function switchTab(tabId, selectedButton = null) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));

            const tabButton = selectedButton || document.querySelector(`.tab[onclick*="${tabId}"]`);
            if (tabButton) tabButton.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }

        function showLoading() {
            stopSpeechPlayback();
            if (sttSupported && isListening && recognizer) {
                try { recognizer.stop(); } catch (e) {}
                isListening = false;
            }
            document.getElementById('loading').style.display = 'block';
            document.getElementById('results').style.display = 'none';
        }

        function hideLoading() {
            document.getElementById('loading').style.display = 'none';
        }

        function showResults() {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('results').style.display = 'block';
            document.getElementById('review-result').innerHTML = '';
            activeReviewContext = null;
        }

        function clearResults() {
            stopSpeechPlayback();
            if (sttSupported && isListening && recognizer) {
                try { recognizer.stop(); } catch (e) {}
                isListening = false;
            }
            document.getElementById('results').style.display = 'none';
            currentHomework = [];
            isPracticeMode = false;
            currentPracticeContent = '';
            currentHomeworkMode = 'homework';
            currentQuestionIndex = 0;
            currentQuestionAnswers = {};
            activeReviewContext = null;
            resetHomeworkActionButtons();
            document.getElementById('tutor-mode-buttons').style.display = 'none';
            clearSavedState();
        }

        async function generateGuidedHomework() {
            if (!isHomeworkGuideComplete()) {
                alert('Please answer each short question first.');
                homeworkGuideState.showQuickStart = false;
                homeworkGuideState.stepIndex = 0;
                renderHomeworkGuide();
                return;
            }

            const answers = homeworkGuideState.answers;
            const yearGroup = Number(answers.year_group);
            const sessionMinutes = Number(answers.session_minutes);
            const questionCount = HOMEWORK_SESSION_QUESTIONS[sessionMinutes];
            const mode = answers.mode === 'tutor' ? 'tutor' : 'homework';
            const learningNotesInput = document.getElementById('homework-parent-notes');
            const learningNotes = learningNotesInput
                ? learningNotesInput.value.trim() || null
                : null;
            const studentId = await getEffectiveStudentId();
            const profile = {
                setup_source: 'guided_homework',
                year_group: yearGroup,
                age: yearGroup + 5,
                subject: answers.subject,
                session_minutes: sessionMinutes,
                difficulty: answers.difficulty,
                learning_notes: learningNotes,
                student_id: studentId
            };

            saveLearningChoices();
            homeworkGuideState.showQuickStart = true;
            clearSavedState();
            showLoading();

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        profile,
                        subjects: [answers.subject],
                        student_id: studentId,
                        mode,
                        question_count: questionCount
                    })
                });

                const data = await response.json().catch(() => ({}));
                if (response.status === 402) {
                    alert(data.error || 'Subscription required for this feature.');
                    redirectToPricing(data.resume_session_id || null);
                    return;
                }
                if (response.status === 401) {
                    redirectToLogin(data.resume_session_id || null);
                    return;
                }

                if (data.success) {
                    currentHomework = data.homework;
                    currentProfile = data.profile;
                    currentHomeworkMode = mode;
                    currentQuestionIndex = 0;
                    currentQuestionAnswers = {};
                    renderHomeworkGuide();

                    if (currentHomeworkMode === 'tutor') {
                        displayTutorQuestion(currentQuestionIndex);
                    } else {
                        displayHomework(data.homework);
                    }
                } else {
                    alert('Error: ' + (data.error || 'We could not make that homework just now.'));
                }
            } catch (error) {
                console.error('Error:', error);
                alert('We could not make that homework just now. Please try again.');
            } finally {
                hideLoading();
            }
        }

        function getSelectedMode(name) {
            const radios = document.getElementsByName(name);
            for (const radio of radios) {
                if (radio.checked) {
                    return radio.value;
                }
            }
            return 'homework';
        }

        async function generateHomework() {
            const year = parseInt(document.getElementById('homework-year').value);
            const subjects = getSelectedSubjects('homework-subjects');
            const mode = getSelectedMode('homework-quick-mode');
            const profileInput = document.getElementById('homework-parent-notes');
            const profileText = profileInput ? profileInput.value.trim() : '';
            saveLearningChoices();

            if (subjects.length === 0) {
                alert('Please select one subject!');
                return;
            }

            const profile = {
                year_group: year,
                age: 5 + (year - 1),
                student_id: await getEffectiveStudentId()
            };
            if (profileText) {
                profile.description = profileText;
            }

            clearSavedState();
            showLoading();

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        quick_select: true,
                        year: year,
                        subjects: subjects,
                        student_id: profile.student_id,
                        mode: mode,
                        profile: profile
                    })
                });

                const data = await response.json().catch(() => ({}));
                if (response.status === 402) {
                    alert(data.error || 'Subscription required for this feature.');
                    redirectToPricing(data.resume_session_id || null);
                    return;
                }
                if (response.status === 401) {
                    redirectToLogin(data.resume_session_id || null);
                    return;
                }

                if (data.success) {
                    currentHomework = data.homework;
                    currentProfile = data.profile;
                    currentHomeworkMode = mode;
                    currentQuestionIndex = 0;
                    currentQuestionAnswers = {};

                    if (currentHomeworkMode === 'tutor') {
                        displayTutorQuestion(currentQuestionIndex);
                    } else {
                        displayHomework(data.homework);
                    }
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred');
            } finally {
                hideLoading();
            }
        }

        async function generateQuickHomeworkEleven() {
            const subjects = getSelectedSubjects('eleven-subjects');
            const elevenYearInput = document.getElementById('eleven-year');
            const selectedYear = Number(elevenYearInput ? elevenYearInput.value : NaN);
            const year = [3, 4, 5, 6].includes(selectedYear) ? selectedYear : 5;
            const mode = getSelectedMode('eleven-quick-mode') === 'tutor' ? 'tutor' : 'homework';
            const ageByYear = {3: 8, 4: 9, 5: 10, 6: 11};

            if (subjects.length === 0) {
                alert('Please select one subject!');
                return;
            }

            const profile = {
                year_group: year,
                age: ageByYear[year],
                student_id: await getEffectiveStudentId()
            };

            saveLearningChoices();
            clearSavedState();
            showLoading();

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        quick_select: true,
                        year: year,
                        subjects: subjects,
                        is_eleven_plus: true,
                        mode: mode,
                        profile: profile
                    })
                });

                const data = await response.json().catch(() => ({}));
                if (response.status === 402) {
                    alert(data.error || 'Subscription required for this feature.');
                    redirectToPricing(data.resume_session_id || null);
                    return;
                }
                if (response.status === 401) {
                    redirectToLogin(data.resume_session_id || null);
                    return;
                }

                if (data.success) {
                    currentHomework = data.homework;
                    currentProfile = data.profile;
                    currentHomeworkMode = mode;
                    currentQuestionIndex = 0;
                    currentQuestionAnswers = {};

                    if (currentHomeworkMode === 'tutor') {
                        displayTutorQuestion(currentQuestionIndex);
                    } else {
                        displayHomework(data.homework);
                    }
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred');
            } finally {
                hideLoading();
            }
        }

        async function generateCustomHomeworkEleven() {
            if (!isElevenGuideComplete()) {
                alert('Please answer each short question first.');
                elevenGuideState.showQuickStart = false;
                elevenGuideState.stepIndex = 0;
                renderElevenGuide();
                return;
            }

            saveLearningChoices();
            elevenGuideState.showQuickStart = true;
            renderElevenGuide();

            if (!await requireSubscription('Guided 11+ Practice', false, 'elevenplus_monthly')) return;

            const answers = elevenGuideState.answers;
            const yearGroup = Number(answers.year_group);
            const ageByYear = {3: 8, 4: 9, 5: 10, 6: 11};
            const examBoardInput = document.getElementById('eleven-exam-board');
            const examDateInput = document.getElementById('eleven-exam-date');
            const parentNotesInput = document.getElementById('eleven-parent-notes');
            const examBoard = examBoardInput ? examBoardInput.value || 'Not sure' : 'Not sure';
            const examDate = examDateInput ? examDateInput.value || null : null;
            const parentNotes = parentNotesInput
                ? parentNotesInput.value.trim() || null
                : null;
            const studentId = await getEffectiveStudentId();
            const subjects = [answers.subject];
            const mode = answers.mode;

            const profile = {
                setup_source: 'guided_11plus',
                year_group: yearGroup,
                age: ageByYear[yearGroup] || 10,
                subject: answers.subject,
                confidence: answers.confidence,
                question_count: Number(answers.question_count),
                exam_format: examBoard,
                exam_date: examDate,
                learning_notes: parentNotes,
                student_id: studentId
            };

            clearSavedState();
            showLoading();

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        profile: profile,
                        subjects: subjects,
                        is_eleven_plus: true,
                        mode: mode,
                        question_count: Number(answers.question_count),
                        student_id: studentId
                    })
                });

                const data = await response.json().catch(() => ({}));
                if (response.status === 402) {
                    alert(data.error || 'Subscription required for this feature.');
                    redirectToPricing(data.resume_session_id || null);
                    return;
                }
                if (response.status === 401) {
                    redirectToLogin(data.resume_session_id || null);
                    return;
                }

                if (data.success) {
                    currentHomework = data.homework;
                    currentProfile = data.profile;
                    currentHomeworkMode = mode;
                    currentQuestionIndex = 0;
                    currentQuestionAnswers = {};

                    if (currentHomeworkMode === 'tutor') {
                        displayTutorQuestion(currentQuestionIndex);
                    } else {
                        displayHomework(data.homework);
                    }
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred');
            } finally {
                hideLoading();
            }
        }

        function formatQuestions(html) {
            let formatted = html
                .replace(/<p>(\d+\.)/g, '<p class="question-number">$1')
                .replace(/<li>/g, '<li class="question-item">');

            return formatted;
        }

        function escapeHomeworkText(value) {
            return String(value || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function unwrapHomeworkValue(value, depth = 0) {
            if (depth > 4 || value == null) return '';
            if (Array.isArray(value)) {
                return value.map((item, index) => {
                    if (item && typeof item === 'object') {
                        const question = item.question || item.prompt || item.text || item.content || item.task || '';
                        const options = Array.isArray(item.options)
                            ? item.options.map((option, optionIndex) => {
                                const label = option && typeof option === 'object'
                                    ? (option.label || String.fromCharCode(65 + optionIndex))
                                    : String.fromCharCode(65 + optionIndex);
                                const optionText = option && typeof option === 'object'
                                    ? (option.text || option.value || '') : option;
                                return optionText ? `${label}) ${optionText}` : '';
                            }).filter(Boolean) : [];
                        return [`${item.number || index + 1}. ${question}`, ...options].join('\n');
                    }
                    return `${index + 1}. ${String(item || '')}`;
                }).filter(Boolean).join('\n');
            }
            if (typeof value === 'object') {
                return unwrapHomeworkValue(
                    value.homework || value.worksheet || value.content || value.questions || '',
                    depth + 1
                );
            }

            let text = String(value || '').trim();
            if (text.startsWith('```')) {
                text = text.replace(/^```(?:json|javascript|python)?\s*/i, '').replace(/\s*```$/, '');
            }
            if (/^[\[{\"]/.test(text)) {
                try {
                    const decoded = JSON.parse(text);
                    if (decoded !== text) {
                        const unwrapped = unwrapHomeworkValue(decoded, depth + 1);
                        if (unwrapped) return unwrapped;
                    }
                } catch (_error) {
                }
            }
            const escapedBreaks = (text.match(/\\n/g) || []).length;
            const structuralBreak = /\\n(?:\\n|\s*(?:#{1,6}\s*)?(?:question\s*\d+|\d+[.)]|[A-H][).]|[-*•]))/i.test(text);
            if (escapedBreaks >= 2 || structuralBreak) {
                text = text.replace(/\\r\\n|\\n|\\r/g, '\n').replace(/\\t/g, '\t');
            }
            return text;
        }

        function normaliseQuestionText(value) {
            return unwrapHomeworkValue(value)
                .replace(/\r\n?/g, '\n')
                .replace(/[ \t]+$/gm, '')
                .trim();
        }

        function questionTextFromObject(item) {
            if (typeof item === 'string') return normaliseQuestionText(item);
            if (!item || typeof item !== 'object') return '';
            return normaliseQuestionText(
                item.question || item.prompt || item.text || item.content || item.task || ''
            );
        }

        function splitQuestionOnlyHomework(homeworkItem) {
            if (homeworkItem && Array.isArray(homeworkItem.questions)) {
                const structured = homeworkItem.questions
                    .map(questionTextFromObject)
                    .filter(Boolean);
                if (structured.length) return structured;
            }

            const content = normaliseQuestionText(homeworkItem && homeworkItem.content);
            if (!content) return [];

            const lines = content.split('\n');
            const questions = [];
            let current = [];
            let foundNumberedQuestion = false;

            const numberedStart = /^\s*(?:#{1,6}\s*)?(?:(?:question|q)\s*)?(?:\(?\d+\)?[.):\-]|\d+\s*\))\s+(.+)$/i;
            const bulletStart = /^\s*[-*•]\s+(.+)$/;
            const looksLikeHeading = line => /^\s*(?:#{1,6}\s*)?(?:homework|questions?|worksheet|tasks?|practice|activity|instructions?)\s*:?[\s#]*$/i.test(line);

            const pushCurrent = () => {
                const value = normaliseQuestionText(current.join('\n'));
                if (value) questions.push(value);
                current = [];
            };

            lines.forEach(line => {
                const numbered = line.match(numberedStart);
                if (numbered) {
                    if (foundNumberedQuestion) pushCurrent();
                    else current = [];
                    foundNumberedQuestion = true;
                    current.push(numbered[1].trim());
                    return;
                }

                if (!foundNumberedQuestion && looksLikeHeading(line)) return;
                current.push(line);
            });
            pushCurrent();

            if (foundNumberedQuestion && questions.length) return questions;

            const bulletQuestions = lines
                .map(line => {
                    const match = line.match(bulletStart);
                    return match ? normaliseQuestionText(match[1]) : '';
                })
                .filter(Boolean);
            if (bulletQuestions.length >= 2) return bulletQuestions;

            const paragraphQuestions = content
                .split(/\n\s*\n+/)
                .map(normaliseQuestionText)
                .filter(value => value && !looksLikeHeading(value));
            if (paragraphQuestions.length >= 2 && paragraphQuestions.every(value => /[?!.]$/.test(value))) {
                return paragraphQuestions;
            }

            return [content];
        }

        function removeVisibleAnswerLabels(root) {
            if (!root) return;
            const labelPattern = /^\s*your\s+answers?\s*:?\s*$/i;
            root.querySelectorAll('h1, h2, h3, h4, h5, h6, label, legend, p, div, span').forEach(element => {
                const containsAnswerControl = element.querySelector('input, textarea, select, button');
                if (!containsAnswerControl && labelPattern.test(element.textContent || '')) {
                    element.remove();
                }
            });
        }

        function stripStandaloneAnswerLabels(text) {
            return String(text || '')
                .split('\n')
                .filter(line => !/^\s*(?:#{1,6}\s*)?your\s+answers?\s*:?\s*$/i.test(line))
                .join('\n')
                .trim();
        }

        function getAnswerInputSpec(questionText) {
            const text = normaliseQuestionText(questionText).toLowerCase();
            const longAnswer = /\b(explain|describe|compare|discuss|justify|give reasons?|show your working|show all working|write (?:a|an|the|your)|paragraph|story|letter|report|method|how do you know|why do you think)\b/.test(text);
            const mediumAnswer = /\b(list|name (?:two|three|four)|give (?:two|three|four)|what happens|how|why|sentence|working|steps?|solve|word problem)\b/.test(text);
            const numericAnswer = /[=+×÷*/<>]|\b(calculate|total|difference|sum|product|fraction|decimal|percentage|perimeter|area|volume|time|money|number)\b/.test(text);

            if (longAnswer) {
                return { kind: 'textarea', rows: 6, sizeClass: 'answer-size-long', placeholder: 'Write your full answer here...' };
            }
            if (mediumAnswer) {
                return { kind: 'textarea', rows: 3, sizeClass: 'answer-size-medium', placeholder: 'Write your answer here...' };
            }
            if (numericAnswer || text.length <= 100) {
                return { kind: 'input', rows: 1, sizeClass: 'answer-size-short', placeholder: 'Type your answer...' };
            }
            return { kind: 'textarea', rows: 3, sizeClass: 'answer-size-medium', placeholder: 'Write your answer here...' };
        }

        function renderQuestionAnswerControl({ questionText, homeworkIndex, questionIndex, subject, id = null, savedAnswer = '', inputSpec = null }) {
            const spec = inputSpec || getAnswerInputSpec(questionText);
            const inputId = id || `homework-answer-${homeworkIndex}-${questionIndex}`;
            const safeSubject = String(subject || 'Homework').replace(/"/g, '&quot;');
            const answerKey = `homework-${homeworkIndex}-question-${questionIndex}`;
            const common = `class="answer-input-inline question-answer-input ${spec.sizeClass}" id="${inputId}" ` +
                `data-subject="${safeSubject}" data-homework-index="${homeworkIndex}" ` +
                `data-question-index="${questionIndex}" data-answer-key="${answerKey}" ` +
                `aria-label="Answer to question ${questionIndex + 1}" placeholder="${spec.placeholder}"`;

            if (spec.kind === 'input') {
                return `<input type="text" ${common} value="${escapeHomeworkText(String(savedAnswer || ''))}" autocomplete="off">`;
            }
            return `<textarea ${common} rows="${spec.rows}">${escapeHomeworkText(String(savedAnswer || ''))}</textarea>`;
        }

        function renderStandardHomeworkBlock(hw, idx) {
            const questions = splitQuestionOnlyHomework(hw).map(stripStandaloneAnswerLabels).filter(Boolean);
            const subject = hw.subject || 'Homework';
            const questionCards = questions.map((questionText, questionIndex) => {
                const inputSpec = getAnswerInputSpec(questionText);
                const bodyClass = inputSpec.kind === 'input'
                    ? 'single-question-body single-question-body-inline'
                    : 'single-question-body single-question-body-stacked';
                const answerInputId = `homework-answer-${idx}-${questionIndex}`;
                return `
                    <section class="single-question-card" data-question-index="${questionIndex}">
                        <div class="single-question-heading">Question ${questionIndex + 1} of ${questions.length}</div>
                        <div class="${bodyClass}">
                            <div class="voice-controls-tutor">
                                ${ttsSupported ? `<button type="button" class="voice-btn" onclick="speakQuestionFromCard(this)" title="Read question aloud">\uD83D\uDD0A Read it to me</button>` : ''}
                            </div>
                            <div class="single-question-text">${formatQuestions(renderSafeMarkdown(questionText))}</div>
                            ${renderQuestionAnswerControl({
                                questionText: questionText,
                                homeworkIndex: idx,
                                questionIndex: questionIndex,
                                subject: subject,
                                inputSpec: inputSpec
                            })}
                            <div class="voice-controls-answer">
                                ${sttSupported ? `<button type="button" class="voice-btn" onclick="toggleVoiceAnswerFor(this, '${answerInputId}')" title="Answer by speaking">\uD83C\uDFA4 Answer by voice</button>` : ''}
                            </div>
                        </div>
                    </section>
                `;
            }).join('');

            return `
                <div class="homework-block standard-question-list" data-homework-index="${idx}">
                    <h3 class="subject-header">${escapeHomeworkText(subject)} ${hw.from_rag ? '(Free - from library)' : ''}</h3>
                    <div class="single-question-list">
                        ${questionCards}
                    </div>
                </div>
            `;
        }

        function displayHomework(homeworkList) {
            const container = document.getElementById('homework-results');
            const renderer = window.HomeworkQuestionRenderer;
            const list = Array.isArray(homeworkList) ? homeworkList : [];

            container.innerHTML = list.map((hw, idx) => {
                if (renderer && renderer.hasChoiceQuestions(hw)) {
                    return renderer.renderResponseBlock(hw, idx, {
                        headerText: hw.subject || 'Homework',
                        groupPrefix: 'homework-choice'
                    });
                }
                return renderStandardHomeworkBlock(hw, idx);
            }).join('');

            if (renderer) renderer.bindAll(container);
            removeVisibleAnswerLabels(container);
            showResults();
            resetHomeworkActionButtons();
            document.getElementById('tutor-mode-buttons').style.display = 'none';
        }

        function displayTutorQuestion(index) {
            if (index >= currentHomework.length) {
                alert('You have completed all questions!');
                clearResults();
                return;
            }

            const hw = currentHomework[index];
            const savedAnswer = currentQuestionAnswers[index] || '';
            const renderer = window.HomeworkQuestionRenderer;
            const container = document.getElementById('homework-results');

            if (renderer && renderer.hasChoiceQuestions(hw)) {
                container.innerHTML = renderer.renderResponseBlock(hw, index, {
                    outerClass: 'homework-block question-response-block tutor-multiple-choice-block',
                    headerText: `${hw.subject || 'Homework'} (Question ${index + 1} of ${currentHomework.length})`,
                    groupPrefix: 'tutor-choice',
                    proxyId: 'tutor-answer-input',
                    savedAnswer: savedAnswer
                });
                const block = container.querySelector('.question-response-block');
                renderer.bindBlock(block, value => {
                    currentQuestionAnswers[index] = value;
                });
            } else {
                const tutorQuestion = stripStandaloneAnswerLabels(splitQuestionOnlyHomework(hw)[0] || hw.content || '');
                const inputSpec = getAnswerInputSpec(tutorQuestion);
                const bodyClass = inputSpec.kind === 'input'
                    ? 'single-question-body single-question-body-inline'
                    : 'single-question-body single-question-body-stacked';
                container.innerHTML = `
                    <div class="homework-block tutor-question-only-block">
                        <h3 class="subject-header">${escapeHomeworkText(hw.subject || 'Homework')} (Question ${index + 1} of ${currentHomework.length}) ${hw.from_rag ? '(Free - from library)' : ''}</h3>
                        <section class="single-question-card">
                            <div class="${bodyClass}">
                                <div class="voice-controls-tutor">
                                    ${ttsSupported ? `<button type="button" class="voice-btn" id="speak-question-btn" onclick="speakQuestion()" title="Read question aloud">\uD83D\uDD0A Read it to me</button>` : ''}
                                </div>
                                <div class="single-question-text">${formatQuestions(renderSafeMarkdown(tutorQuestion))}</div>
                                ${renderQuestionAnswerControl({
                                    questionText: tutorQuestion,
                                    homeworkIndex: index,
                                    questionIndex: 0,
                                    subject: hw.subject || 'Homework',
                                    id: 'tutor-answer-input',
                                    savedAnswer: savedAnswer,
                                    inputSpec: inputSpec
                                })}
                                <div class="voice-controls-answer">
                                    ${sttSupported ? `<button type="button" class="voice-btn" id="voice-answer-btn" onclick="toggleVoiceAnswer()" title="Answer by speaking">\uD83C\uDFA4 Answer by voice</button>` : ''}
                                </div>
                            </div>
                        </section>
                    </div>
                `;
            }

            removeVisibleAnswerLabels(container);
            showResults();
            document.getElementById('homework-buttons').style.display = 'none';
            document.getElementById('tutor-mode-buttons').style.display = 'block';
            document.getElementById('review-result').innerHTML = '';
        }

        async function reviewCurrentQuestion() {
            const answerInput = document.getElementById('tutor-answer-input');
            const studentAnswer = answerInput ? answerInput.value.trim() : '';

            if (!studentAnswer) {
                alert('Please select or enter your answer for this question!');
                return;
            }

            currentQuestionAnswers[currentQuestionIndex] = studentAnswer;

            const hw = currentHomework[currentQuestionIndex];
            const homeworkContent = hw.content;
            const subject = hw.subject;
            const requiredPlan = hw.is_eleven_plus
                ? ELEVENPLUS_PREMIUM_PLAN
                : HOMEWORK_PREMIUM_PLAN;
            if (!await requireSubscription('Review Question', false, requiredPlan)) return;

            showLoading();

            try {
                const response = await fetch('/api/review', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        homework: homeworkContent,
                        answers: studentAnswer,
                        subject: subject,
                        profile: getLearnerReviewProfile(),
                        is_tutor_mode: true,
                        from_rag: hw.from_rag,
                        homework_doc_id: hw.doc_id,
                        is_eleven_plus: !!hw.is_eleven_plus,
                        question_index: Number.isInteger(hw.question_index)
                            ? hw.question_index
                            : currentQuestionIndex
                    })
                });

                const data = await response.json().catch(() => ({}));
                if (response.status === 402) {
                    alert(data.error || 'Subscription required for this feature.');
                    redirectToPricing(data.resume_session_id || null);
                    return;
                }
                if (response.status === 401) {
                    redirectToLogin(data.resume_session_id || null);
                    return;
                }

                if (data.success) {
                    displayReview(data.display_review || data.llm_response || data.review, {
                        homework: homeworkContent,
                        answers: studentAnswer,
                        subject: subject || 'Maths',
                        from_rag: Boolean(hw.from_rag),
                        homework_doc_id: hw.doc_id || null,
                        is_eleven_plus: Boolean(hw.is_eleven_plus),
                        question_index: Number.isInteger(hw.question_index)
                            ? hw.question_index : currentQuestionIndex
                    }, data.solution_methods || []);
                    showRewardCelebration(data.reward_update);
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred during review');
            } finally {
                hideLoading();
            }
        }

        function nextQuestion() {
            const answerInput = document.getElementById('tutor-answer-input');
            if (answerInput) {
                currentQuestionAnswers[currentQuestionIndex] = answerInput.value.trim();
            }
            currentQuestionIndex++;
            displayTutorQuestion(currentQuestionIndex);
        }


        function readResponseBlockAnswer(block) {
            if (!block) return '';

            const renderer = window.HomeworkQuestionRenderer;
            if (renderer && typeof renderer.getBlockAnswer === 'function' && block.classList.contains('question-response-block')) {
                return String(renderer.getBlockAnswer(block) || '').trim();
            }

            const questionInputs = Array.from(block.querySelectorAll('.question-answer-input'));
            if (questionInputs.length) {
                return questionInputs
                    .map((input, index) => `${index + 1}. ${String(input.value || '').trim()}`)
                    .join('\n')
                    .trim();
            }

            const input = block.querySelector('.answer-input-inline, .answer-box, textarea');
            return input ? String(input.value || '').trim() : '';
        }

        function findFirstUnansweredStandardQuestion(block) {
            if (!block) return null;
            return Array.from(block.querySelectorAll('.question-answer-input'))
                .find(input => !String(input.value || '').trim()) || null;
        }

        function focusUnansweredStandardQuestion(input) {
            if (!input) return;
            if (typeof input.focus === 'function') input.focus();
            const card = input.closest('.single-question-card');
            if (card && typeof card.scrollIntoView === 'function') {
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        function findFirstUnansweredResponse(block) {
            if (!block) return null;
            const items = Array.from(block.querySelectorAll('.question-response-item'));
            return items.find(item => {
                if (item.dataset.responseType === 'single_choice') {
                    return !item.querySelector('.multiple-choice-input:checked');
                }
                const input = item.querySelector('.question-response-input');
                return !input || !input.value.trim();
            }) || null;
        }

        function focusUnansweredResponse(item) {
            if (!item) return;
            const control = item.querySelector('.multiple-choice-input, .question-response-input');
            if (control && typeof control.focus === 'function') control.focus();
            if (typeof item.scrollIntoView === 'function') {
                item.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        async function reviewGeneratedHomework() {
            const reviewItems = [];

            for (let index = 0; index < currentHomework.length; index += 1) {
                const homeworkItem = currentHomework[index];
                const block = document.querySelector(`.homework-block[data-homework-index="${index}"], .question-response-block[data-homework-index="${index}"]`);

                const unansweredStandard = findFirstUnansweredStandardQuestion(block);
                if (unansweredStandard) {
                    alert('Please answer every question before using Quick Review.');
                    focusUnansweredStandardQuestion(unansweredStandard);
                    return;
                }

                const unansweredChoice = block && block.classList.contains('question-response-block')
                    ? findFirstUnansweredResponse(block)
                    : null;
                if (unansweredChoice) {
                    alert('Please answer every question before using Quick Review.');
                    focusUnansweredResponse(unansweredChoice);
                    return;
                }

                const answer = readResponseBlockAnswer(block);
                if (answer) reviewItems.push({ homeworkItem, index, answer });
            }

            if (!reviewItems.length) {
                alert('Please enter your answers first!');
                return;
            }

            currentSubject = reviewItems[0].homeworkItem.subject || 'Maths';
            showLoading();
            try {
                const results = await Promise.all(reviewItems.map(async ({ homeworkItem, index, answer }) => {
                    const response = await fetch('/api/review', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            homework: homeworkItem.content,
                            answers: answer,
                            subject: homeworkItem.subject || 'Maths',
                            profile: getLearnerReviewProfile(),
                            quick_review: true,
                            from_rag: Boolean(homeworkItem.from_rag),
                            homework_doc_id: homeworkItem.doc_id || null,
                            is_eleven_plus: Boolean(homeworkItem.is_eleven_plus),
                            question_index: Number.isInteger(homeworkItem.question_index)
                                ? homeworkItem.question_index : null
                        })
                    });
                    const data = await response.json().catch(() => ({}));
                    if (response.status === 401 || response.status === 402) {
                        const accessError = new Error(data.error || 'A parent account is needed for this feature.');
                        accessError.status = response.status;
                        throw accessError;
                    }
                    if (!response.ok || !data.success) {
                        throw new Error(data.error || 'We could not check that answer just now.');
                    }
                    return {
                        markdown: `## ${homeworkItem.subject || `Homework ${index + 1}`}\n\n${data.review || ''}`,
                        rewardUpdate: data.reward_update || null
                    };
                }));
                displayReview(results.map(item => item.markdown).join('\n\n---\n\n'), {
                    homework: reviewItems.map(item => item.homeworkItem.content || '').filter(Boolean).join('\n\n'),
                    answers: reviewItems.map(item => `--- ${item.homeworkItem.subject || 'Homework'} ---\n${item.answer}`).join('\n\n'),
                    subject: reviewItems[0].homeworkItem.subject || 'Maths',
                    from_rag: reviewItems.every(item => Boolean(item.homeworkItem.from_rag)),
                    homework_doc_id: reviewItems.length === 1 ? (reviewItems[0].homeworkItem.doc_id || null) : null,
                    is_eleven_plus: reviewItems.some(item => Boolean(item.homeworkItem.is_eleven_plus))
                });
                showRewardCelebration(
                    combineRewardUpdates(results.map(item => item.rewardUpdate))
                );
            } catch (error) {
                console.error('Review failed:', error);
                if (error.status === 401) redirectToLogin();
                else if (error.status === 402) redirectToPricing();
                else alert(error.message || 'We could not check those answers just now.');
            } finally {
                hideLoading();
            }
        }

        function inferUploadedHomeworkSubject(text) {
            const value = String(text || '').toLowerCase();
            if (/\b(verbal reasoning|analogy|odd one out|letter code)\b/.test(value)) return 'Verbal Reasoning';
            if (/\b(non[- ]?verbal reasoning|rotation|mirror image|shape sequence|spatial)\b/.test(value)) return 'Non-Verbal Reasoning';
            if (/\b(science|experiment|habitat|electricity|forces?|materials?|plants?|animals?)\b/.test(value)) return 'Science';
            if (/\b(grammar|punctuation|spelling|comprehension|vocabulary|sentence|noun|verb|adjective)\b/.test(value)) return 'English';
            if (/[=+×÷*/<>]|\b(add|subtract|multiply|divide|fraction|decimal|percentage|number|calculate|maths?|geometry|measure)\b/.test(value)) return 'Maths';
            return 'General Homework';
        }

        async function reviewHomework() {
            if (!currentStudentId) {
                saveStateToSessionStorage();
                window.location.href = '/login';
                return;
            }
            if (!await requireSubscription('Mark Homework', false, HOMEWORK_PREMIUM_PLAN)) return;

            let homeworkText = '';
            let answersText = '';

            let subject = 'General Homework';
            let uploadedTextForDisplay = '';

            if (currentInputMethod === 'text') {
                homeworkText = document.getElementById('review-homework').value.trim();
                answersText = document.getElementById('review-answers').value.trim();
                const subjectSelect = document.getElementById('review-subject');
                subject = subjectSelect ? subjectSelect.value : 'General Homework';
            } else if (currentInputMethod === 'file' || currentInputMethod === 'photo') {
                const pendingUpload = currentInputMethod === 'file'
                    ? fileUploadPromise
                    : photoUploadPromise;
                if (pendingUpload) {
                    const uploadSucceeded = await pendingUpload;
                    if (!uploadSucceeded) return;
                }

                const uploadedText = String(extractedContent || '').trim();
                if (!uploadedText) {
                    alert('Please upload a readable TXT, PDF or image file first.');
                    return;
                }

                uploadedTextForDisplay = uploadedText;
                subject = inferUploadedHomeworkSubject(uploadedText);
                const splitContent = splitUploadedHomeworkText(uploadedText);
                homeworkText = splitContent.homework;
                answersText = splitContent.answers;

                if (!homeworkText && splitContent.combined) {
                    homeworkText = uploadedText;
                    answersText = 'The pupil answers are written inside the uploaded homework. Identify each written answer and mark it against its question.';
                }
            }

            if (!homeworkText) {
                alert('Please include the homework questions in the file or paste them into the questions box.');
                return;
            }
            if (!answersText) {
                alert('Please include the pupil\'s answers in the uploaded file.');
                return;
            }

            const submittedWork = (currentInputMethod === 'file' || currentInputMethod === 'photo') ? {
                content: uploadedTextForDisplay
            } : null;

            await reviewHomeworkWithContent(homeworkText, answersText, subject, null, submittedWork);
        }

        async function reviewHomeworkWithContent(homework, answers, subject, homeworkDocId = null, submittedWork = null) {

            showLoading();

            try {
                const requestBody = {
                    homework: homework,
                    answers: answers,
                    subject: subject,
                    profile: getLearnerReviewProfile(),
                    uploaded_work: Boolean(submittedWork)
                };
                if (homeworkDocId) {
                    requestBody.homework_doc_id = homeworkDocId;
                    requestBody.is_eleven_plus = currentHomework.some(item => item.is_eleven_plus === true);
                }
                requestBody.is_eleven_plus = !!(currentHomework[0] && currentHomework[0].is_eleven_plus);

                const response = await fetch('/api/review', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody)
                });

                if (response.status === 402) {
                    saveStateToSessionStorage();
                    alert('Subscription required for this feature.');
                    window.location.href = '/pricing';
                    return;
                }
                if (response.status === 401) {
                    saveStateToSessionStorage();
                    window.location.href = '/login';
                    return;
                }
                const data = await response.json().catch(() => ({}));

                if (!response.ok || !data.success) {
                    throw new Error(getApiErrorMessage(
                        data,
                        'We could not mark that homework just now. Please check the file and try again.'
                    ));
                }
                const followUpAnswers = submittedWork && submittedWork.content &&
                    answers.startsWith('The pupil answers are written inside')
                    ? submittedWork.content
                    : answers;

                displayReview(
                    data.display_review || data.llm_response || data.review ||
                        'The homework was checked, but no feedback was returned.',
                    {
                        homework: homework,
                        answers: followUpAnswers,
                        subject: subject || 'General Homework',
                        from_rag: Boolean(homeworkDocId),
                        homework_doc_id: homeworkDocId || null,
                        is_eleven_plus: Boolean(requestBody.is_eleven_plus)
                    },
                    data.solution_methods || []
                );
                showRewardCelebration(data.reward_update);
            } catch (error) {
                console.error('Homework review failed:', error);
                alert(error.message || 'We could not mark that homework just now.');
            } finally {
                hideLoading();
            }
        }

        function buildGeneratedReviewContext() {
            if (!Array.isArray(currentHomework) || currentHomework.length === 0) return null;

            const answeredItems = currentHomework.map((homeworkItem, index) => {
                const block = document.querySelector(`.homework-block[data-homework-index="${index}"], .question-response-block[data-homework-index="${index}"]`);
                const answer = readResponseBlockAnswer(block);
                return { homeworkItem, index, answer };
            }).filter(item => item.answer);

            if (!answeredItems.length) return null;

            return {
                homework: answeredItems.map(item => item.homeworkItem.content || '').filter(Boolean).join('\n\n'),
                answers: answeredItems.map(item => `--- ${item.homeworkItem.subject || 'Homework'} ---\n${item.answer}`).join('\n\n'),
                subject: answeredItems[0].homeworkItem.subject || 'Maths',
                from_rag: answeredItems.every(item => Boolean(item.homeworkItem.from_rag)),
                homework_doc_id: answeredItems.length === 1 ? (answeredItems[0].homeworkItem.doc_id || null) : null,
                is_eleven_plus: answeredItems.some(item => Boolean(item.homeworkItem.is_eleven_plus))
            };
        }

        function getReviewActionContext() {
            if (activeReviewContext && activeReviewContext.homework && activeReviewContext.answers) {
                return activeReviewContext;
            }
            return buildGeneratedReviewContext();
        }

        function renderSolutionMethods(solutionMethods) {
            if (!Array.isArray(solutionMethods) || solutionMethods.length === 0) {
                return '';
            }
            const cards = solutionMethods.map((item, index) => {
                const label = solutionMethods.length > 1
                    ? `<h4>Question ${index + 1}</h4>`
                    : '';
                return `<div class="solution-method-card">${label}${renderSafeMarkdown(item.method || '')}</div>`;
            }).join('');
            return `
                <section class="review-output solution-methods-output" aria-labelledby="solution-methods-title">
                    <h3 id="solution-methods-title">A helpful way to solve this question</h3>
                    ${cards}
                </section>
            `;
        }

        function displayReview(review, reviewContext = null, solutionMethods = []) {
            activeReviewContext = reviewContext || buildGeneratedReviewContext();

            const container = document.getElementById('review-result');
            container.innerHTML = `
                <div class="review-header">
                    <h3 class="teacher-feedback-heading">Teacher Feedback</h3>
                    ${ttsSupported ? `<button type="button" class="voice-btn" id="speak-review-btn" onclick="speakReviewFeedback()" title="Read feedback aloud">\uD83D\uDD0A Read it to me</button>` : ''}
                </div>
                <div class="review-output teacher-feedback-output">${renderSafeMarkdown(review)}</div>
                ${renderSolutionMethods(solutionMethods)}
            `;

            document.getElementById('results').style.display = 'block';
        }

        async function ExplainDeep() {
            const reviewContext = getReviewActionContext();
            if (!reviewContext) {
                alert('Please check the homework first, then choose Explain in Detail.');
                return;
            }

            const fromRag = Boolean(reviewContext.from_rag);
            const isFree = false;
            const requiredPlan = premiumPlanForContext(reviewContext);

            if (!await requireSubscription('Explain in Detail', isFree, requiredPlan)) return;

            saveCurrentState();

            const homework = String(reviewContext.homework || '').trim();
            const combinedAnswers = String(reviewContext.answers || '').trim();
            const subject = reviewContext.subject || 'Maths';

            if (!homework) {
                alert('No homework content found to explain.');
                return;
            }
            if (!combinedAnswers) {
                alert('No pupil answers were found in the reviewed homework.');
                return;
            }

            const reviewEl = document.querySelector('#review-result .teacher-feedback-output');
            const reviewFeedback = reviewEl ? reviewEl.innerText : '';

            showLoading();

            try {
                const response = await fetch('/api/explain-deep', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        homework: homework,
                        answers: combinedAnswers,
                        subject: subject,
                        profile: getLearnerReviewProfile(),
                        review_feedback: reviewFeedback,
                        from_rag: fromRag,
                        homework_doc_id: reviewContext.homework_doc_id || null,
                        is_eleven_plus: Boolean(reviewContext.is_eleven_plus)
                    })
                });

                const data = await response.json().catch(() => ({}));
                if (response.status === 402) {
                    alert(data.error || 'Subscription required for this feature.');
                    redirectToPricing(data.resume_session_id || null);
                    return;
                }
                if (response.status === 401) {
                    redirectToLogin(data.resume_session_id || null);
                    return;
                }

                if (response.status === 504) {
                    alert('That took too long. Please try again or use a shorter question.');
                    return;
                }

                if (response.ok && data.success) {
                    displayExplainDeep(data.explanation);
                } else {
                    const errorMsg = data.error || (data.detail && typeof data.detail === 'object' ? JSON.stringify(data.detail) : data.detail) || 'Unknown error';
                    alert('Error: ' + errorMsg);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred during deep explanation');
            } finally {
                hideLoading();
            }
        }

        function displayExplainDeep(explanation) {
            const container = document.getElementById('review-result');
            const hasSavedReview = savedHomeworkState && savedHomeworkState.reviewHTML && savedHomeworkState.reviewHTML.trim();
            container.innerHTML = `
                ${hasSavedReview ? '<div style="margin-top: 20px; text-align: right;"><button class="btn btn-secondary" onclick="backToReview()">Back to Review</button></div>' : ''}
                <div class="review-header" style="margin-top: 20px; margin-bottom: 20px;">
                    <h3>Deep Explanation</h3>
                    ${ttsSupported ? `<button type="button" class="voice-btn" id="speak-review-btn" onclick="speakReviewFeedback()" title="Read explanation aloud">\uD83D\uDD0A Read it to me</button>` : ''}
                </div>
                <div class="review-output">${renderSafeMarkdown(explanation)}</div>
            `;

            document.getElementById('results').style.display = 'block';
        }

        function backToReview() {
            if (savedHomeworkState && savedHomeworkState.reviewHTML) {
                document.getElementById('review-result').innerHTML = savedHomeworkState.reviewHTML;
            }
        }

        async function ImprovePractice() {
            const reviewContext = getReviewActionContext();
            if (!reviewContext) {
                alert('Please check the homework first, then choose Help me improve.');
                return;
            }

            const fromRag = Boolean(reviewContext.from_rag);
            const isFree = false;
            const requiredPlan = premiumPlanForContext(reviewContext);

            if (!await requireSubscription('Help me improve', isFree, requiredPlan)) return;

            saveCurrentState();

            const homework = String(reviewContext.homework || '').trim();
            const combinedAnswers = String(reviewContext.answers || '').trim();
            const subject = reviewContext.subject || 'Maths';

            if (!homework) {
                alert('No homework content found to practise.');
                return;
            }
            if (!combinedAnswers) {
                alert('No pupil answers were found in the reviewed homework.');
                return;
            }

            const reviewEl = document.querySelector('#review-result .teacher-feedback-output');
            const reviewFeedback = reviewEl ? reviewEl.innerText : '';

            const oldMessage = document.getElementById('practice-generation-message');
            if (oldMessage) oldMessage.remove();

            showLoading();

            try {
                const response = await fetch('/api/improve-practice', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        homework: homework,
                        answers: combinedAnswers,
                        subject: subject,
                        profile: getLearnerReviewProfile(),
                        review_feedback: reviewFeedback,
                        from_rag: fromRag,
                        homework_doc_id: reviewContext.homework_doc_id || null,
                        is_eleven_plus: Boolean(reviewContext.is_eleven_plus),
                        question_index: Number.isInteger(reviewContext.question_index)
                            ? reviewContext.question_index : null
                    })
                });

                const data = await response.json().catch(() => ({}));
                if (response.status === 402) {
                    alert(data.error || 'Subscription required for this feature.');
                    redirectToPricing(data.resume_session_id || null);
                    return;
                }
                if (response.status === 401) {
                    redirectToLogin(data.resume_session_id || null);
                    return;
                }

                if (response.status === 504) {
                    alert('That took too long. Please try again or use a shorter question.');
                    return;
                }

                const practiceContent = String(data.practice || '').trim();
                if (response.ok && data.success && practiceContent) {
                    displayPracticeQuestions(practiceContent, subject);
                } else {
                    const errorMsg = data.error || (data.detail && typeof data.detail === 'object' ? JSON.stringify(data.detail) : data.detail) ||
                        'The AI tutor did not return any usable practice questions, so no new content was created. Please try again in a moment.';
                    showPracticeGenerationMessage(errorMsg);
                }
            } catch (error) {
                console.error('Error:', error);
                showPracticeGenerationMessage(
                    'The AI tutor could not generate extra practice content just now. Please try again in a moment.'
                );
            } finally {
                hideLoading();
            }
        }

        function showPracticeGenerationMessage(message) {
            const container = document.getElementById('review-result');
            if (!container) {
                alert(message);
                return;
            }
            let panel = document.getElementById('practice-generation-message');
            if (!panel) {
                panel = document.createElement('div');
                panel.id = 'practice-generation-message';
                panel.className = 'review-output practice-generation-message';
                panel.setAttribute('role', 'alert');
                panel.style.marginTop = '18px';
                panel.style.borderLeftColor = '#b86b12';
                container.appendChild(panel);
            }
            panel.textContent = String(message || 'The AI tutor could not generate practice questions.');
            document.getElementById('results').style.display = 'block';
            panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function displayPracticeQuestions(practiceContent, subject) {
            const container = document.getElementById('homework-results');
            const renderer = window.HomeworkQuestionRenderer;

            currentPracticeContent = practiceContent;
            currentPracticeSubject = subject;
            isPracticeMode = true;

            const practiceItem = {
                subject: subject,
                content: practiceContent,
                questions: renderer ? renderer.parseQuestions(practiceContent) : []
            };
            if (renderer && renderer.hasChoiceQuestions(practiceItem)) {
                container.innerHTML = renderer.renderResponseBlock(practiceItem, 0, {
                    outerClass: 'homework-block question-response-block practice-question-block',
                    headerClass: 'subject-header practice-subject-header',
                    headerText: `Practice - ${subject}`,
                    groupPrefix: 'practice-choice',
                    proxyId: 'practice-answer-input'
                });
                renderer.bindAll(container);
            } else {
                container.innerHTML = `
                    <div class="homework-block">
                        <h3 class="subject-header practice-subject-header">Practice - ${subject}</h3>
                        <div class="homework-content">
                            <div class="question-column practice-question-column">
                                ${renderSafeMarkdown(practiceContent)}
                            </div>
                            <div class="answer-column">
                                <h4 class="practice-answer-heading">Your Answers:</h4>
                                <textarea class="answer-input-inline practice-answer-input"
                                          id="practice-answer-input"
                                          placeholder="Work through the practice questions above and write your answers here..."></textarea>
                            </div>
                        </div>
                    </div>
                `;
            }

            const buttonArea = document.getElementById('homework-buttons');
            if (buttonArea) {
                buttonArea.innerHTML = `
                    <button class="btn btn-primary practice-check-button" onclick="checkPracticeAnswers()">
                        Check Answers
                    </button>
                    <button class="btn btn-secondary" onclick="exitPracticeMode()">
                        Back to Homework
                    </button>
                `;
            }

            document.getElementById('review-result').innerHTML = '';
            document.getElementById('results').style.display = 'block';
        }

        function checkPracticeAnswers() {
            const practiceBlock = document.querySelector('#homework-results .practice-question-block, #homework-results .question-response-block');
            const unanswered = findFirstUnansweredResponse(practiceBlock);
            if (unanswered) {
                alert('Please answer every question before checking.');
                focusUnansweredResponse(unanswered);
                return;
            }

            const answerInput = document.getElementById('practice-answer-input');
            const answers = practiceBlock
                ? readResponseBlockAnswer(practiceBlock)
                : (answerInput ? answerInput.value.trim() : '');

            if (!answers) {
                alert('Please write your answers first!');
                if (answerInput && typeof answerInput.focus === 'function') answerInput.focus();
                return;
            }

            showLoading();

            fetch('/api/review', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    homework: currentPracticeContent,
                    answers: answers,
                    subject: currentPracticeSubject,
                    profile: getLearnerReviewProfile()
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const container = document.getElementById('review-result');
                    container.innerHTML = `
                        <h3 style="margin-top: 30px; margin-bottom: 20px;">Practice Feedback</h3>
                        <div class="review-output" style="border-left-color: #f57c00;">${renderSafeMarkdown(data.review)}</div>
                    `;
                    document.getElementById('results').style.display = 'block';
                    showRewardCelebration(data.reward_update);
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred during practice answer check');
            })
            .finally(() => hideLoading());
        }

        function exitPracticeMode() {
            isPracticeMode = false;
            currentPracticeContent = '';
            displayHomework(currentHomework);
            restoreSavedState();
            resetHomeworkActionButtons();
            clearSavedState();
        }

        // ---- 学习进度追踪 ----

        async function TrackProgress() {
            const progressWindow = window.open('about:blank', '_blank');
            if (!progressWindow) {
                alert('Please allow pop-ups so Progress can open in a new tab.');
                return;
            }
            progressWindow.opener = null;

            if (!await requireSubscription('Track Progress', false, premiumPlanForContext())) {
                progressWindow.close();
                return;
            }

            saveStateToSessionStorage();
            progressWindow.location.replace('/progress');
        }

        // ---- Admin Tools Functions ----
        let isAdminUser = false;

        async function checkAdminAccess() {
            const adminTab = document.getElementById('admin-tools-tab');
            if (!adminTab) return;

            adminTab.style.display = 'none';
            try {
                const response = await fetch('/api/admin/access-status', {
                    credentials: 'same-origin',
                    cache: 'no-store'
                });
                if (!response.ok) return;

                const data = await response.json();
                isAdminUser = data.is_admin === true;
                if (isAdminUser) {
                    adminTab.style.display = 'block';
                }
            } catch (error) {
                console.error('Failed to check admin access:', error);
                isAdminUser = false;
            }
        }

        async function createTestUser() {
            const name = document.getElementById('test-user-name').value;
            const email = document.getElementById('test-user-email').value;
            const year_group = parseInt(document.getElementById('test-user-year').value);

            const testUserMessage = document.getElementById('test-user-message');
            testUserMessage.className = 'message';
            testUserMessage.textContent = 'Creating test user...';

            if (!name || !email) {
                testUserMessage.classList.add('error-message');
                testUserMessage.textContent = 'Name and Email are required for test user.';
                return;
            }

            try {
                const response = await fetch('/api/admin/users', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, email, year_group, age: 5 + (year_group - 1) })
                });
                const data = await response.json();
                if (data.success) {
                    testUserMessage.classList.add('success-message');
                    testUserMessage.textContent = `Test user created: ${data.student.name} (ID: ${data.student.student_id})`;
                } else {
                    testUserMessage.classList.add('error-message');
                    testUserMessage.textContent = 'Failed to create test user: ' + (data.detail || data.error || 'Unknown error');
                }
            } catch (error) {
                testUserMessage.classList.add('error-message');
                testUserMessage.textContent = 'An error occurred: ' + error.message;
            }
        }

        async function createTestSubscription() {
            const email = document.getElementById('sub-email').value;
            const name = document.getElementById('sub-name').value;
            const duration = document.getElementById('sub-duration').value;
            const testSubscriptionMessage = document.getElementById('test-subscription-message');
            testSubscriptionMessage.className = 'message';
            testSubscriptionMessage.textContent = 'Creating test subscription...';

            if (!email || !name) {
                testSubscriptionMessage.classList.add('error-message');
                testSubscriptionMessage.textContent = 'Email and Name are required for subscription.';
                return;
            }

            try {
                const response = await fetch('/api/admin/subscriptions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, name, duration })
                });
                const data = await response.json();
                if (data.success) {
                    testSubscriptionMessage.classList.add('success-message');
                    testSubscriptionMessage.textContent = `Subscription created for ${data.subscription.customer_email} (${data.subscription.product_name})`;
                } else {
                    testSubscriptionMessage.classList.add('error-message');
                    testSubscriptionMessage.textContent = 'Failed to create test subscription: ' + (data.detail || data.error || 'Unknown error');
                }
            } catch (error) {
                testSubscriptionMessage.classList.add('error-message');
                testSubscriptionMessage.textContent = 'An error occurred: ' + error.message;
            }
        }

        // ===== VOICE FEATURE FUNCTIONS (Tier 0: Browser-native) =====

        function getYearGroupForLogging() {
            return (currentProfile && currentProfile.year_group) || null;
        }

        function logVoiceUsage(eventType) {
            const yearGroup = getYearGroupForLogging();
            const homeworkItem = currentHomework[currentQuestionIndex];
            const subject = homeworkItem ? homeworkItem.subject : null;
            if (!yearGroup || !subject) return;

            fetch('/api/log-voice-usage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    event_type: eventType,
                    year_group: yearGroup,
                    subject: subject,
                    student_id: currentStudentId || null,
                })
            }).catch(() => {});
        }

        function resetSpeechButtons() {
            if (activeSpeechButton) {
                activeSpeechButton.classList.remove('speaking');
                if (activeSpeechButton.dataset.originalText) {
                    activeSpeechButton.textContent = activeSpeechButton.dataset.originalText;
                }
            }
            document.querySelectorAll('.voice-btn.speaking').forEach(b => {
                b.classList.remove('speaking');
                if (b.dataset.originalText) b.textContent = b.dataset.originalText;
            });
            activeSpeechButton = null;
        }

        function stopSpeechPlayback() {
            speechPlaybackId += 1;
            activeSpeechUtterance = null;
            resetSpeechButtons();
            if (ttsSupported && window.speechSynthesis) {
                try { window.speechSynthesis.cancel(); } catch (e) {}
            }
        }

        // Split long feedback into short phrases. Chrome and Safari can silently
        // fail or stop early when one SpeechSynthesisUtterance is too long.
        function splitSpeechText(text, maxLength = 220) {
            const sentences = text.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [text];
            const chunks = [];
            let current = '';

            sentences.forEach(sentence => {
                const words = sentence.trim().split(/\s+/).filter(Boolean);
                words.forEach(word => {
                    const candidate = current ? `${current} ${word}` : word;
                    if (candidate.length <= maxLength) {
                        current = candidate;
                    } else {
                        if (current) chunks.push(current);
                        current = word;
                    }
                });
            });
            if (current) chunks.push(current);
            return chunks;
        }

        // Centralised text-to-speech handler with toggle, UI feedback, and
        // retained utterances to prevent browser garbage collection.
        function speakText(text, btn = null) {
            if (!ttsSupported || !window.speechSynthesis) return;

            const shouldStop = Boolean(btn && btn.classList.contains('speaking'));
            stopSpeechPlayback();
            if (shouldStop) return;

            const plainText = String(text || '')
                .replace(/<[^>]*>/g, ' ')
                .replace(/[#*_`~]/g, '')
                .replace(/^\d+\.\s*/gm, '')
                .replace(/\s+/g, ' ')
                .trim();

            if (!plainText) return;

            const chunks = splitSpeechText(plainText);
            if (!chunks.length) return;

            const playbackId = speechPlaybackId;
            if (btn) {
                if (!btn.dataset.originalText) {
                    btn.dataset.originalText = btn.textContent;
                }
                activeSpeechButton = btn;
                btn.classList.add('speaking');
                btn.textContent = '⏹ Stop reading';
            }

            function finishPlayback() {
                if (playbackId !== speechPlaybackId) return;
                activeSpeechUtterance = null;
                resetSpeechButtons();
            }

            function speakChunk(index) {
                if (playbackId !== speechPlaybackId) return;
                if (index >= chunks.length) {
                    finishPlayback();
                    return;
                }

                try {
                    if (window.speechSynthesis.paused) {
                        window.speechSynthesis.resume();
                    }

                    const utterance = new SpeechSynthesisUtterance(chunks[index]);
                    activeSpeechUtterance = utterance;
                    utterance.lang = 'en-GB';
                    utterance.rate = 0.85;

                    try {
                        const femaleVoice = getFemaleVoice();
                        if (femaleVoice) utterance.voice = femaleVoice;
                    } catch (e) {
                        console.warn('Voice selection fallback:', e);
                    }

                    utterance.onend = () => speakChunk(index + 1);
                    utterance.onerror = (event) => {
                        if (playbackId !== speechPlaybackId) return;
                        if (event.error !== 'canceled' && event.error !== 'interrupted') {
                            console.error('Speech synthesis utterance error:', event);
                        }
                        finishPlayback();
                    };

                    window.speechSynthesis.speak(utterance);

                    if (window.speechSynthesis.paused) {
                        window.speechSynthesis.resume();
                    }
                } catch (err) {
                    console.error('Failed to initiate speech synthesis:', err);
                    finishPlayback();
                }
            }

            // Let cancel() finish before the first queued utterance is started.
            setTimeout(() => speakChunk(0), 75);
        }

        // Text to speech: read the current question aloud in Tutor mode
        function speakQuestion() {
            if (!ttsSupported || !window.speechSynthesis) return;
            const btn = document.getElementById('speak-question-btn');
            const card = document.querySelector('#homework-results .single-question-card');
            const textEl = card ? card.querySelector('.single-question-text') : null;
            let textToSpeak = '';
            if (textEl) {
                textToSpeak = textEl.innerText || textEl.textContent || '';
            } else if (currentHomework[currentQuestionIndex]) {
                const hw = currentHomework[currentQuestionIndex];
                textToSpeak = hw.content || hw.question || '';
            }
            speakText(textToSpeak, btn);
        }

        // Speech to text: dictate the answer into the textarea
        function toggleVoiceAnswer() {
            if (!sttSupported) return;
            const btn = document.getElementById('voice-answer-btn');
            const input = document.getElementById('tutor-answer-input');

            if (isListening) {
                recognizer.stop();
                return;
            }

            recognizer = new SpeechRec();
            recognizer.lang = 'en-GB';
            recognizer.interimResults = true;
            recognizer.continuous = false;

            recognizer.onstart = () => {
                isListening = true;
                logVoiceUsage('stt_used');
                btn.textContent = '🔴 Listening... (tap to stop)';
                btn.classList.add('listening');
            };

            recognizer.onresult = (event) => {
                const transcript = Array.from(event.results)
                    .map(r => r[0].transcript)
                    .join('');
                input.value = transcript;
            };

            recognizer.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
            };

            recognizer.onend = () => {
                isListening = false;
                btn.textContent = '🎤 Answer by voice';
                btn.classList.remove('listening');
            };

            recognizer.start();
        }

        // 标准作业模式：从按钮所在的问题卡片读取题目文本并朗读
        function speakQuestionFromCard(btn) {
            if (!ttsSupported || !window.speechSynthesis) return;
            const card = btn ? btn.closest('.single-question-card') : null;
            const textEl = card ? card.querySelector('.single-question-text') : null;
            if (textEl) {
                speakText(textEl.innerText || textEl.textContent || '', btn);
            }
        }

        // 朗读评审/反馈/解释文本
        function speakReviewFeedback() {
            if (!ttsSupported || !window.speechSynthesis) return;
            const reviewEl = document.querySelector('#review-result .review-output');
            if (!reviewEl) return;
            const btn = document.getElementById('speak-review-btn');
            speakText(reviewEl.innerText || reviewEl.textContent || '', btn);
        }

        // 标准作业模式：将语音识别结果填入指定输入框
        function toggleVoiceAnswerFor(btn, inputId) {
            if (!sttSupported) return;
            const input = document.getElementById(inputId);
            if (!input) return;

            if (isListening) {
                recognizer.stop();
                return;
            }

            recognizer = new SpeechRec();
            recognizer.lang = 'en-GB';
            recognizer.interimResults = true;
            recognizer.continuous = false;

            recognizer.onstart = () => {
                isListening = true;
                logVoiceUsage('stt_used');
                btn.textContent = '\uD83D\uDD34 Listening... (tap to stop)';
                btn.classList.add('listening');
            };

            recognizer.onresult = (event) => {
                const transcript = Array.from(event.results)
                    .map(r => r[0].transcript)
                    .join('');
                input.value = transcript;
            };

            recognizer.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
            };

            recognizer.onend = () => {
                isListening = false;
                btn.textContent = '\uD83C\uDFA4 Answer by voice';
                btn.classList.remove('listening');
            };

            recognizer.start();
        }
