let currentHomework = [];
        let currentSubject = 'Maths';
        let currentProfile = null;
        let currentInputMethod = 'text';
        let currentPhotoData = null;
        let currentFileData = null;
        let extractedContent = '';
        let fileUploadPromise = null;
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
            const yearGroup = Number.isFinite(rawYear) ? Math.min(7, Math.max(1, Math.round(rawYear))) : 3;
            const rawAge = Number(source.age);
            const age = Number.isFinite(rawAge) ? Math.min(12, Math.max(5, Math.round(rawAge))) : Math.min(12, yearGroup + 4);
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

        // 检查订阅状态
        async function checkSubscription(plan = null) {
            // Always check if plan is specified, otherwise use cached status
            if (plan === null && hasSubscription !== null) return hasSubscription;

            // If not logged in, the backend will handle anonymous session ID and return has_subscription: false
            const url = plan ? `/api/check-subscription?plan=${encodeURIComponent(plan)}` : `/api/check-subscription`;
            try {
                const resp = await fetch(url);
                const data = await resp.json();
                const result = data.has_subscription === true;
                if (plan === null) hasSubscription = result;
                
                // Extra check for 11+ Premium specifically if requested
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
            // If the feature/content is free, we don't need to check subscription
            if (isFree) return true;

            // Paid features always require a logged-in user with a real student_id
            if (!currentStudentId) { // currentStudentId is only set for logged-in users
                redirectToLogin()
                return false;
            }
            const subscribed = await checkSubscription(plan); // Check subscription for the logged-in user
            if (!subscribed) {
                const planName = plan === 'elevenplus_monthly' ? '11+ Premium' : 'Premium';
                alert(`${featureName} requires a ${planName} subscription. Please subscribe to continue.`);
                redirectToPricing();
                return false;
            }
            return true;
        }

        // 状态保存（用于在功能切换时保留答案和批改结果）
        let savedHomeworkState = null;

        // Homework-mode actions are deliberately rebuilt from this fixed template.
        // Practice mode may temporarily replace the action area, but it must never
        // leave homework mode with a different or incomplete set of buttons.
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
            // 只保存一次，避免后续操作覆盖原始状态
            if (savedHomeworkState) return;
            savedHomeworkState = {
                answers: {},
                reviewHTML: document.getElementById('review-result').innerHTML,
            };
            captureVisibleAnswers(savedHomeworkState.answers);
        }

        function restoreSavedState() {
            if (!savedHomeworkState) return false;
            // 恢复答案
            restoreVisibleAnswers(savedHomeworkState.answers);
            // 恢复批改结果
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
            loadSubjects();
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
                        // Wait for subjects to load and UI to be ready
                        const restore = () => {
                            currentHomework = state.homework;
                            currentProfile = state.profile;
                            currentSubject = state.subject || 'Maths';
                            currentHomeworkMode = state.mode || 'homework'; // Restore mode
                            if (currentHomeworkMode === 'tutor') {
                                currentQuestionIndex = state.questionIndex || 0;
                                currentQuestionAnswers = state.questionAnswers || {};
                                displayTutorQuestion(currentQuestionIndex);
                            } else {
                                displayHomework(state.homework);
                            }

                            // 恢复答案
                            setTimeout(() => {
                                restoreVisibleAnswers(state.answers);
                                if (window.HomeworkQuestionRenderer) {
                                    window.HomeworkQuestionRenderer.restoreFromProxies(document);
                                }
                                // 恢复批改结果
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
            currentStudentId = null;
            currentStudentEmail = null;
            hasSubscription = null;
            window.location.assign('/');
        });

        // Input method handling
        function setInputMethod(method, selectedButton = null) {
            currentInputMethod = method;

            // Update tab styles
            document.querySelectorAll('.input-method-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            if (selectedButton) selectedButton.classList.add('active');

            // Hide all content
            document.querySelectorAll('.input-method-content').forEach(content => {
                content.style.display = 'none';
            });

            // Show selected content
            document.getElementById('input-' + method).style.display = 'block';

            // The uploaded file is marked from its own content, so no subject choice is needed.
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

                // Show preview
                document.getElementById('photo-img').src = currentPhotoData;
                document.getElementById('photo-preview').style.display = 'block';
                document.querySelector('#input-photo .upload-placeholder').style.display = 'none';

                // Process the photo
                processPhoto(currentPhotoData);
            };
            reader.readAsDataURL(file);
        }

        function clearPhoto() {
            currentPhotoData = null;
            extractedContent = '';
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
            } catch (error) {
                console.error('Photo processing failed:', error);
                alert(error.message || 'We could not read that photo.');
            } finally {
                hideLoading();
            }
        }

        // File handling
        function handleFileSelect(event) {
            const file = event.target.files[0];
            if (!file) return;

            currentFileData = file;

            // Show file info
            document.getElementById('file-name').textContent = file.name;
            document.getElementById('file-info').style.display = 'block';
            document.querySelector('#input-file .upload-placeholder').style.display = 'none';

            // Process the file and keep the promise so Get Feedback can wait for it.
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

            const detail = data.error ?? data.detail ?? data.message;
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
            fetch('/api/subjects')
                .then(response => response.json())
                .then(data => {
                    renderSubjects('homework-subjects', data.primary);
                    renderSubjects('eleven-subjects', data.eleven_plus);

                    const reviewSelect = document.getElementById('review-subject');
                    reviewSelect.innerHTML = ''; // Clear existing options
                    const allSubjects = [...new Set([...data.primary, ...data.eleven_plus])].sort();
                    allSubjects.forEach(subject => {
                        const option = document.createElement('option');
                        option.value = subject;
                        option.textContent = subject;
                        reviewSelect.appendChild(option);
                    });
                })
                .catch(error => console.error('Error loading subjects:', error));
        }

        function renderSubjects(containerId, subjects) {
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

            container.innerHTML = subjectList.map(subject => {
                // Default select 'Maths' in both homework and 11+ tabs.
                const isSelected = (containerId === 'homework-subjects' || containerId === 'eleven-subjects')
                                    && subject === 'Maths';
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
            // Deselect all other subjects in the same container
            container.querySelectorAll('.subject-item.selected').forEach(item => {
                item.classList.remove('selected');
            });
            element.classList.add('selected'); // Select the clicked subject
        }

        function getSelectedSubjects(containerId) {
            const container = document.getElementById(containerId);
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
            document.getElementById('results').style.display = 'none';
            currentHomework = [];
            isPracticeMode = false;
            currentPracticeContent = '';
            currentHomeworkMode = 'homework'; // Reset mode
            currentQuestionIndex = 0;
            currentQuestionAnswers = {};
            activeReviewContext = null;
            resetHomeworkActionButtons();
            document.getElementById('tutor-mode-buttons').style.display = 'none'; // Hide tutor buttons
            clearSavedState();
        }

        function getSelectedMode(name) {
            const radios = document.getElementsByName(name);
            for (const radio of radios) {
                if (radio.checked) {
                    return radio.value;
                }
            }
            return 'homework'; // Default to homework mode
        }

        // Generate Homework - uses selected subjects directly
        async function generateHomework() {
            const year = parseInt(document.getElementById('homework-year').value);
            const subjects = getSelectedSubjects('homework-subjects');
            const mode = getSelectedMode('homework-mode');
            const profileText = document.getElementById('homework-profile').value.trim();

            if (subjects.length === 0) {
                alert('Please select one subject!');
                return;
            }

            // Build profile
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

        // Smart Homework - uses LLM to analyze description and determine subjects/profile
        async function generateSmartHomework() {
            const profileText = document.getElementById('homework-profile').value.trim();
            const year = parseInt(document.getElementById('homework-year').value);
            const mode = getSelectedMode('homework-mode');

            if (!profileText) {
                alert('Please describe the student first! The AI will analyze the description to generate personalized homework.');
                return;
            }

            // Build profile with description for LLM analysis
            const profile = {
                description: profileText,
                year_group: year,
                age: 5 + (year - 1),
                student_id: await getEffectiveStudentId()
            };

            clearSavedState();
            showLoading();

            try {
                // Send to API - the backend will use LLM to parse the profile and determine subjects
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        profile: profile,
                        subjects: [], // Empty - let LLM determine from description
                        mode: mode,
                        student_id: profile.student_id
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
            const mode = getSelectedMode('eleven-mode');

            if (subjects.length === 0) {
                alert('Please select one subject!');
                return;
            }

            // Set student_id in profile for subscription checks
            const profile = { student_id: currentStudentId };

            clearSavedState();
            showLoading();

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        quick_select: true,
                        subjects: subjects,
                        is_eleven_plus: true,
                        mode: mode, // Pass the selected mode
                        profile: profile // Pass profile with student_id
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
                    currentHomeworkMode = mode; // Set the global mode
                    currentQuestionIndex = 0; // Reset question index for new homework
                    currentQuestionAnswers = {}; // Reset answers for new homework

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
            // Check subscription first
            if (!await requireSubscription('Smart 11+ Practice', false, 'elevenplus_monthly')) return;

            const profileText = document.getElementById('eleven-profile').value;
            const subjects = getSelectedSubjects('eleven-subjects');
            const mode = getSelectedMode('eleven-mode');

            // Set student_id in profile for subscription checks
            const profile = { description: profileText, student_id: currentStudentId };

            clearSavedState();
            showLoading();

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        profile: profile, // Pass profile with student_id
                        subjects: subjects,
                        is_eleven_plus: true,
                        mode: mode // Pass the selected mode
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
                    currentHomeworkMode = mode; // Set the global mode
                    currentQuestionIndex = 0; // Reset question index for new homework
                    currentQuestionAnswers = {}; // Reset answers for new homework

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
            // 在每个问题前后添加更好的间距和格式
            // 查找编号的问题（如 1.、2.、(1)、(2) 等）
            let formatted = html
                // 给编号问题添加间距
                .replace(/<p>(\d+\.)/g, '<p class="question-number">$1')
                // 增强列表项
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

        function normaliseQuestionText(value) {
            return String(value || '')
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
                    else current = []; // Drop headings or instructions before Question 1.
                    foundNumberedQuestion = true;
                    current.push(numbered[1].trim());
                    return;
                }

                if (!foundNumberedQuestion && looksLikeHeading(line)) return;
                current.push(line);
            });
            pushCurrent();

            if (foundNumberedQuestion && questions.length) return questions;

            // Some generators use bullets rather than numbers. Only treat bullets as
            // separate questions when at least two are present, to avoid breaking a
            // single question that contains a short list.
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
                return `
                    <section class="single-question-card" data-question-index="${questionIndex}">
                        <div class="single-question-heading">Question ${questionIndex + 1} of ${questions.length}</div>
                        <div class="${bodyClass}">
                            <div class="single-question-text">${formatQuestions(renderSafeMarkdown(questionText))}</div>
                            ${renderQuestionAnswerControl({
                                questionText: questionText,
                                homeworkIndex: idx,
                                questionIndex: questionIndex,
                                subject: subject,
                                inputSpec: inputSpec
                            })}
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

            // Save the current answer
            currentQuestionAnswers[currentQuestionIndex] = studentAnswer;

            const hw = currentHomework[currentQuestionIndex];
            const homeworkContent = hw.content;
            const subject = hw.subject;

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
                        is_tutor_mode: true, // Indicate tutor mode review
                        from_rag: hw.from_rag, // Pass from_rag status
                        homework_doc_id: hw.doc_id, // Source RAG document
                        is_eleven_plus: !!hw.is_eleven_plus,
                        question_index: Number.isInteger(hw.question_index)
                            ? hw.question_index
                            : currentQuestionIndex // Backward-compatible fallback
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
                    displayReview(data.review, {
                        homework: homeworkContent,
                        answers: studentAnswer,
                        subject: subject || 'Maths',
                        from_rag: Boolean(hw.from_rag),
                        homework_doc_id: hw.doc_id || null,
                        is_eleven_plus: Boolean(hw.is_eleven_plus)
                    });
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
            // Save the current answer before moving to the next question.
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
                    return `## ${homeworkItem.subject || `Homework ${index + 1}`}\n\n${data.review || ''}`;
                }));
                displayReview(results.join('\n\n---\n\n'), {
                    homework: reviewItems.map(item => item.homeworkItem.content || '').filter(Boolean).join('\n\n'),
                    answers: reviewItems.map(item => `--- ${item.homeworkItem.subject || 'Homework'} ---\n${item.answer}`).join('\n\n'),
                    subject: reviewItems[0].homeworkItem.subject || 'Maths',
                    from_rag: reviewItems.every(item => Boolean(item.homeworkItem.from_rag)),
                    homework_doc_id: reviewItems.length === 1 ? (reviewItems[0].homeworkItem.doc_id || null) : null,
                    is_eleven_plus: reviewItems.some(item => Boolean(item.homeworkItem.is_eleven_plus))
                });
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
            // 检查登录和订阅状态
            if (!currentStudentId) {
                saveStateToSessionStorage();
                // alert('Please login to use Mark Homework.');
                window.location.href = '/login';
                return;
            }
            if (!await requireSubscription('Mark Homework')) return;

            // 根据当前输入方式收集数据
            let homeworkText = '';
            let answersText = '';

            let subject = 'General Homework';
            let uploadedTextForDisplay = '';

            if (currentInputMethod === 'text') {
                homeworkText = document.getElementById('review-homework').value.trim();
                answersText = document.getElementById('review-answers').value.trim();
                const subjectSelect = document.getElementById('review-subject');
                subject = subjectSelect ? subjectSelect.value : 'General Homework';
            } else if (currentInputMethod === 'file') {
                if (fileUploadPromise) {
                    const uploadSucceeded = await fileUploadPromise;
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

            const submittedWork = currentInputMethod === 'file' ? {
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
                    profile: getLearnerReviewProfile()
                };
                // Add doc_id if available (for RAG answer lookup)
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
                    // alert('Please login or register to use this feature.');
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
                    data.review || 'The homework was checked, but no feedback was returned.',
                    {
                        homework: homework,
                        answers: followUpAnswers,
                        subject: subject || 'General Homework',
                        from_rag: Boolean(homeworkDocId),
                        homework_doc_id: homeworkDocId || null,
                        is_eleven_plus: Boolean(requestBody.is_eleven_plus)
                    }
                );
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

        function displayReview(review, reviewContext = null) {
            activeReviewContext = reviewContext || buildGeneratedReviewContext();

            const container = document.getElementById('review-result');
            container.innerHTML = `
                <h3 class="teacher-feedback-heading">Teacher Feedback</h3>
                <div class="review-output">${renderSafeMarkdown(review)}</div>
            `;

            // Make sure results section is visible. The uploaded homework stays
            // in the read-only box above the Get Feedback button.
            document.getElementById('results').style.display = 'block';
        }

        async function ExplainDeep() {
            const reviewContext = getReviewActionContext();
            if (!reviewContext) {
                alert('Please check the homework first, then choose Explain in Detail.');
                return;
            }

            const isFree = Boolean(reviewContext.from_rag);

            // Check subscription first
            if (!await requireSubscription('Explain in Detail', isFree)) return;

            // Save current state (answers + review results), so it can be restored when returning
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

            // Get existing review feedback (if answers have been checked)
            const reviewEl = document.querySelector('#review-result .review-output');
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
                        from_rag: isFree,
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
                <h3 style="margin-top: 20px; margin-bottom: 20px;">Deep Explanation</h3>
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

            const isFree = Boolean(reviewContext.from_rag);

            // Check subscription first
            if (!await requireSubscription('Help me improve', isFree)) return;

            // Save current state (answers + review results), so it can be restored when returning
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

            // Get existing review feedback (if answers have been checked)
            const reviewEl = document.querySelector('#review-result .review-output');
            const reviewFeedback = reviewEl ? reviewEl.innerText : '';

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
                        from_rag: isFree,
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
                    displayPracticeQuestions(data.practice, subject);
                } else {
                    const errorMsg = data.error || (data.detail && typeof data.detail === 'object' ? JSON.stringify(data.detail) : data.detail) || 'Unknown error';
                    alert('Error: ' + errorMsg);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred during practice generation');
            } finally {
                hideLoading();
            }
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
            // 重新显示原始作业
            displayHomework(currentHomework);
            // 恢复之前保存的答案和批改结果
            restoreSavedState();
            // Always restore the canonical homework-mode actions. Do not restore
            // a saved HTML snapshot because it may already contain practice controls.
            resetHomeworkActionButtons();
            clearSavedState();
        }

        // ---- 学习进度追踪 ----

        async function TrackProgress() {
            // Open the new tab immediately while this click is still a direct user action.
            // This avoids browsers blocking it after the subscription check finishes.
            const progressWindow = window.open('about:blank', '_blank');
            if (!progressWindow) {
                alert('Please allow pop-ups so Progress can open in a new tab.');
                return;
            }
            progressWindow.opener = null;

            // Check subscription before loading private progress information.
            if (!await requireSubscription('Track Progress')) {
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

            // Hidden by default. Only the server can make it visible after
            // checking the authenticated user's email against ADMIN_EMAILS.
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
