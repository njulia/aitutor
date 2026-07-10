let currentHomework = [];
        let currentSubject = 'Maths';
        let currentProfile = null;
        let currentInputMethod = 'text';
        let currentPhotoData = null;
        let currentFileData = null;
        let extractedContent = '';
        // 练习模式状态
        let isPracticeMode = false;
        let currentPracticeContent = '';
        let currentPracticeSubject = 'Maths';

        // Homework mode and current question index
        let currentHomeworkMode = 'homework'; // 'homework' or 'tutor'
        let currentQuestionIndex = 0;
        let currentQuestionAnswers = {}; // Store answers for each question in tutor mode
        let currentStudentId = localStorage.getItem('student_id'); // Only for logged-in users
        let currentStudentEmail = localStorage.getItem('student_email'); // Only for logged-in users
        let anonymousClientId = null; // IP-based ID for anonymous users

        // Get effective student ID: logged-in user's email, or anonymous IP-based ID
        async function getEffectiveStudentId() {
            // If logged in, return the user's email
            if (currentStudentId) {
                return currentStudentId;
            }
            // If we already have an anonymous ID, return it
            if (anonymousClientId) {
                return anonymousClientId;
            }
            // Check localStorage for cached anonymous ID
            const cached = localStorage.getItem('anonymous_client_id');
            if (cached) {
                anonymousClientId = cached;
                return cached;
            }
            // Fetch IP-based ID from server
            try {
                const resp = await fetch('/api/client-id');
                const data = await resp.json();
                anonymousClientId = data.client_id;
                localStorage.setItem('anonymous_client_id', anonymousClientId);
                return anonymousClientId;
            } catch (e) {
                console.error('Failed to get client ID:', e);
                // Fallback to a random ID
                anonymousClientId = 'anon_' + Math.random().toString(36).substring(2, 14);
                localStorage.setItem('anonymous_client_id', anonymousClientId);
                return anonymousClientId;
            }
        }

        // Synchronous version for places that can't await
        function getEffectiveStudentIdSync() {
            if (currentStudentId) return currentStudentId;
            return localStorage.getItem('anonymous_client_id') || null;
        }


        // Subscription status
        let hasSubscription = null; // null = 未检查, true/false = 已检查

        // 检查订阅状态
        async function checkSubscription() {
            if (hasSubscription !== null) return hasSubscription; // Already checked
            
            // If not logged in, the backend will handle anonymous session ID and return has_subscription: false
            const url = `/api/check-subscription`;
            try {
                const resp = await fetch(url);
                const data = await resp.json();
                hasSubscription = data.has_subscription === true;
                // The backend sets the anon_session_id cookie. Frontend doesn't need to store it in localStorage.
                // currentStudentId is only for logged-in users.
                return hasSubscription;
            } catch(e) {
                console.error('Failed to check subscription:', e);
                hasSubscription = false;
                return false;
            }
        }

        // 检查是否需要订阅才能使用高级功能
        async function requireSubscription(featureName) {
            // Paid features always require a logged-in user with a real student_id
            if (!currentStudentId) { // currentStudentId is only set for logged-in users
                alert(`Please login or register to use ${featureName}.`);
                window.location.href = '/login'; // Redirect to login/register
                return false;
            }
            const subscribed = await checkSubscription(); // Check subscription for the logged-in user
            if (!subscribed) {
                alert(`${featureName} requires a subscription. Please subscribe to continue.`);
                window.location.href = '/pricing';
                return false;
            }
            return true;
        }

        // 状态保存（用于在功能切换时保留答案和批改结果）
        let savedHomeworkState = null;
        let savedButtonsHTML = null;

        function saveCurrentState() {
            // 只保存一次，避免后续操作覆盖原始状态
            if (savedHomeworkState) return;
            savedHomeworkState = {
                answers: {},
                reviewHTML: document.getElementById('review-result').innerHTML,
            };
            document.querySelectorAll('.answer-input-inline').forEach(input => {
                savedHomeworkState.answers[input.dataset.subject] = input.value;
            });
            // 保存按钮区域 HTML
            const btnArea = document.getElementById('homework-buttons');
            if (btnArea) savedButtonsHTML = btnArea.innerHTML;
        }

        function restoreSavedState() {
            if (!savedHomeworkState) return false;
            // 恢复答案
            document.querySelectorAll('.answer-input-inline').forEach(input => {
                if (savedHomeworkState.answers[input.dataset.subject] !== undefined) {
                    input.value = savedHomeworkState.answers[input.dataset.subject];
                }
            });
            // 恢复批改结果
            document.getElementById('review-result').innerHTML = savedHomeworkState.reviewHTML || '';
            return true;
        }

        function clearSavedState() {
            savedHomeworkState = null;
            savedButtonsHTML = null;
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
        document.addEventListener('DOMContentLoaded', function() {
            loadSubjects();
            checkDevMode(); // Check dev mode and admin status on load

            // Update UI based on login status
            if (currentStudentId) {
                document.getElementById('logout-link').style.display = 'block';
                document.querySelector('nav.nav-links a[href="/login"]').style.display = 'none';
                document.querySelector('nav.nav-links a[href="/register"]').style.display = 'none';
                // If logged in, re-check admin status to ensure it's up to date
                checkDevMode();
            }

            // Check for tab parameter in URL
            const urlParams = new URLSearchParams(window.location.search);
            const tabParam = urlParams.get('tab');
            if (tabParam) {
                setTimeout(() => switchTab(tabParam), 100);
            }

            // 从 sessionStorage 恢复状态（Track Progress 返回时）
            try {
                const savedStr = sessionStorage.getItem('homeworkState');
                if (savedStr) {
                    sessionStorage.removeItem('homeworkState');
                    const state = JSON.parse(savedStr);
                    if (state.homework && state.homework.length > 0) {
                        setTimeout(() => {
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
                            document.querySelectorAll('.answer-input-inline').forEach(input => {
                                if (state.answers && state.answers[input.dataset.subject] !== undefined) {
                                    input.value = state.answers[input.dataset.subject];
                                }
                            });
                            // 恢复批改结果
                            if (state.reviewHTML) {
                                document.getElementById('review-result').innerHTML = state.reviewHTML;
                            }
                        }, 300);
                    }
                }
            } catch(e) {
                console.error('Failed to restore state from sessionStorage:', e);
                sessionStorage.removeItem('homeworkState');
            }
        });

        // Logout functionality
        document.getElementById('logout-link').addEventListener('click', function(event) {
            event.preventDefault();
            localStorage.removeItem('student_id');
            localStorage.removeItem('student_email');
            currentStudentId = null;
            currentStudentEmail = null;
            hasSubscription = null; // Reset subscription status
            checkDevMode(); // Re-check admin status on logout
            window.location.href = '/'; // Redirect to home or login page
        });

        // Input method handling
        function setInputMethod(method) {
            currentInputMethod = method;

            // Update tab styles
            document.querySelectorAll('.input-method-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            event.target.classList.add('active');

            // Hide all content
            document.querySelectorAll('.input-method-content').forEach(content => {
                content.style.display = 'none';
            });

            // Show selected content
            document.getElementById('input-' + method).style.display = 'block';
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

                const data = await response.json();

                if (data.success) {
                    extractedContent = data.content;
                    console.log('Extracted content:', extractedContent);
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred while processing photo');
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

            // Process the file
            processFile(file);
        }

        function clearFile() {
            currentFileData = null;
            extractedContent = '';
            document.getElementById('file-info').style.display = 'none';
            document.querySelector('#input-file .upload-placeholder').style.display = 'block';
            document.getElementById('file-input').value = '';
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

                const data = await response.json();

                if (data.success) {
                    extractedContent = data.content;
                    console.log('Extracted content:', extractedContent);
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred while processing file');
            } finally {
                hideLoading();
            }
        }

        function loadSubjects() {
            fetch('/api/subjects')
                .then(response => response.json())
                .then(data => {
                    console.log("Subjects received:", data);
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

        function switchTab(tabId) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));

            // Find the tab button - either from event or by onclick attribute
            let tabButton = event && event.target ? event.target : null;
            if (!tabButton) {
                tabButton = document.querySelector(`.tab[onclick*="${tabId}"]`);
            }
            if (tabButton) {
                tabButton.classList.add('active');
            }
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
        }

        function clearResults() {
            document.getElementById('results').style.display = 'none';
            currentHomework = [];
            isPracticeMode = false;
            currentPracticeContent = '';
            currentHomeworkMode = 'homework'; // Reset mode
            currentQuestionIndex = 0;
            currentQuestionAnswers = {};
            document.getElementById('homework-buttons').style.display = 'block'; // Show homework buttons
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

                if (response.status === 402) {
                    alert('Subscription required for this feature.');
                    window.location.href = '/pricing';
                    return;
                }
                if (response.status === 401) {
                    alert('Please login or register to use this feature.');
                    window.location.href = '/login';
                    return;
                }

                const data = await response.json();

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

                if (response.status === 402) {
                    alert('Subscription required for this feature.');
                    window.location.href = '/pricing';
                    return;
                }
                if (response.status === 401) {
                    alert('Please login or register to use this feature.');
                    window.location.href = '/login';
                    return;
                }

                const data = await response.json();

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

                if (response.status === 402) { // Payment Required - subscription required
                    alert('Subscription required for this feature.');
                    window.location.href = '/pricing';
                    return;
                }
                if (response.status === 401) { // Unauthorized - login required
                    alert('Please login or register to use this feature.');
                    window.location.href = '/login';
                    return;
                }

                const data = await response.json();

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
            if (!await requireSubscription('Smart 11+ Practice')) return;

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

                if (response.status === 402) { // Payment Required - subscription required
                    alert('Subscription required for this feature.');
                    window.location.href = '/pricing';
                    return;
                }
                if (response.status === 401) { // Unauthorized - login required
                    alert('Please login or register to use this feature.');
                    window.location.href = '/login';
                    return;
                }

                const data = await response.json();

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

        function displayHomework(homeworkList) {
            const container = document.getElementById('homework-results');
            container.innerHTML = homeworkList.map(hw => `
                <div class="homework-block">
                    <h3 class="subject-header">${hw.subject} ${hw.from_rag ? '(Free - from library)' : ''}</h3>
                    <div class="homework-content">
                        <div class="question-column">
                            ${formatQuestions(marked.parse(hw.content))}
                        </div>
                        <div class="answer-column">
                            <h4>Your Answer:</h4>
                            <textarea class="answer-input-inline"
                                      placeholder="Write your answer here..."
                                      data-subject="${hw.subject}"></textarea>
                        </div>
                    </div>
                </div>
            `).join('');

            showResults();
            document.getElementById('homework-buttons').style.display = 'block';
            document.getElementById('tutor-mode-buttons').style.display = 'none';
        }

        function displayTutorQuestion(index) {
            if (index >= currentHomework.length) {
                alert('You have completed all questions!');
                clearResults(); // Or show a completion message
                return;
            }

            const hw = currentHomework[index];
            const container = document.getElementById('homework-results');
            container.innerHTML = `
                <div class="homework-block">
                    <h3 class="subject-header">${hw.subject} (Question ${index + 1} of ${currentHomework.length}) ${hw.from_rag ? '(Free - from library)' : ''}</h3>
                    <div class="homework-content">
                        <div class="question-column">
                            ${formatQuestions(marked.parse(hw.content))}
                        </div>
                        <div class="answer-column">
                            <h4>Your Answer:</h4>
                            <textarea class="answer-input-inline"
                                      id="tutor-answer-input"
                                      placeholder="Write your answer here..."
                                      data-subject="${hw.subject}"></textarea>
                        </div>
                    </div>
                </div>
            `;

            // Restore saved answer for this question if exists
            const savedAnswer = currentQuestionAnswers[index] || '';
            document.getElementById('tutor-answer-input').value = savedAnswer;

            showResults();
            document.getElementById('homework-buttons').style.display = 'none';
            document.getElementById('tutor-mode-buttons').style.display = 'block';
            document.getElementById('review-result').innerHTML = ''; // Clear previous review
        }

        async function reviewCurrentQuestion() {
            const answerInput = document.getElementById('tutor-answer-input');
            const studentAnswer = answerInput ? answerInput.value.trim() : '';

            if (!studentAnswer) {
                alert('Please enter your answer for this question!');
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
                        profile: { student_id: currentStudentId }, // Pass student_id for subscription check
                        is_tutor_mode: true, // Indicate tutor mode review
                        from_rag: hw.from_rag, // Pass from_rag status
                        homework_doc_id: hw.doc_id, // Source RAG document
                        question_index: Number.isInteger(hw.question_index)
                            ? hw.question_index
                            : currentQuestionIndex // Backward-compatible fallback
                    })
                });

                if (response.status === 402) { // Payment Required - subscription required
                    alert('Subscription required for this feature.');
                    window.location.href = '/pricing';
                    return;
                }
                if (response.status === 401) { // Unauthorized - login required
                    alert('Please login or register to use this feature.');
                    window.location.href = '/login';
                    return;
                }

                const data = await response.json();

                if (data.success) {
                    displayReview(data.review);
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
            // Save the current answer before moving to the next question
            const answerInput = document.getElementById('tutor-answer-input');
            if (answerInput) {
                currentQuestionAnswers[currentQuestionIndex] = answerInput.value.trim();
            }

            currentQuestionIndex++;
            displayTutorQuestion(currentQuestionIndex);
        }


        async function reviewGeneratedHomework() {
            // Collect all answers
            const answerInputs = document.querySelectorAll('.answer-input-inline');
            let allAnswers = [];

            answerInputs.forEach(input => {
                const subject = input.dataset.subject;
                const answer = input.value.trim();
                if (answer) {
                    allAnswers.push(`--- ${subject} ---\n${answer}`);
                }
            });

            const combinedAnswers = allAnswers.join('\n\n');

            if (!combinedAnswers.trim()) {
                alert('Please enter your answers first!');
                return;
            }

            const homework = currentHomework.map(h => h.content).join('\n\n');
            const subject = currentHomework[0]?.subject || 'Maths';
            // Get doc_id from the first homework item (for RAG answer lookup)
            const homeworkDocId = currentHomework[0]?.doc_id || null;

            currentSubject = subject;
            // Homework mode review is free, no subscription check needed here.
            reviewHomeworkWithContent(homework, combinedAnswers, subject, homeworkDocId);
        }

        async function reviewHomework() {
            // 检查登录和订阅状态
            if (!currentStudentId) {
                alert('Please login to use Mark Homework.');
                window.location.href = '/login';
                return;
            }
            if (!await requireSubscription('Mark Homework')) return;

            // 根据当前输入方式收集数据
            let homeworkText = '';
            let answersText = '';

            if (currentInputMethod === 'text') {
                homeworkText = document.getElementById('review-homework').value.trim();
                answersText = document.getElementById('review-answers').value.trim();
            } else if (currentInputMethod === 'file') {
                homeworkText = document.getElementById('review-homework-file').value.trim();
                // 文件内容作为答案（如果有提取的内容则使用提取的内容）
                answersText = extractedContent || '';
            }

            const subject = document.getElementById('review-subject').value;

            if (!answersText) {
                alert('Please provide the student\'s answers.');
                return;
            }

            reviewHomeworkWithContent(homeworkText, answersText, subject);
        }

        async function reviewHomeworkWithContent(homework, answers, subject, homeworkDocId = null) {
            console.log("=== Starting Review ===");
            console.log("Homework:", homework);
            console.log("Answers:", answers);
            console.log("Subject:", subject);
            console.log("Doc ID:", homeworkDocId);

            showLoading();

            try {
                const requestBody = {
                    homework: homework,
                    answers: answers,
                    subject: subject,
                    profile: { student_id: currentStudentId }
                };
                // Add doc_id if available (for RAG answer lookup)
                if (homeworkDocId) {
                    requestBody.homework_doc_id = homeworkDocId;
                }

                const response = await fetch('/api/review', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody)
                });

                if (response.status === 402) {
                    alert('Subscription required for this feature.');
                    window.location.href = '/pricing';
                    return;
                }
                if (response.status === 401) {
                    alert('Please login or register to use this feature.');
                    window.location.href = '/login';
                    return;
                }
                const data = await response.json();

                if (data.success) {
                    console.log("Calling displayReview with review:", data.review);
                    displayReview(data.review);
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

        function displayReview(review) {
            const container = document.getElementById('review-result');
            container.innerHTML = `
                <h3 style="margin-top: 30px; margin-bottom: 20px;">Teacher Feedback</h3>
                <div class="review-output">${marked.parse(review)}</div>
            `;

            // Make sure results section is visible
            document.getElementById('results').style.display = 'block';
        }

        async function ExplainDeep() {
            // Check subscription first
            if (!await requireSubscription('Explain in Detail')) return;

            // Save current state (answers + review results), so it can be restored when returning
            saveCurrentState();

            // Collect all answers
            const answerInputs = document.querySelectorAll('.answer-input-inline');
            let allAnswers = [];

            answerInputs.forEach(input => {
                const subject = input.dataset.subject;
                const answer = input.value.trim();
                if (answer) {
                    allAnswers.push(`--- ${subject} ---\n${answer}`);
                }
            });

            const combinedAnswers = allAnswers.join('\n\n');

            if (!combinedAnswers.trim()) {
                alert('Please enter your answers first!');
                return;
            }

            const homework = currentHomework.map(h => h.content).join('\n\n');
            const subject = currentHomework[0]?.subject || 'Maths';

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
                        profile: { student_id: currentStudentId }, // Pass student_id for subscription check
                        review_feedback: reviewFeedback
                    })
                });

                if (response.status === 402) { // Payment Required - subscription required
                    alert('Subscription required for this feature.');
                    window.location.href = '/pricing';
                    return;
                }
                if (response.status === 401) { // Unauthorized - login required
                    alert('Please login or register to use this feature.');
                    window.location.href = '/login';
                    return;
                }

                const data = await response.json();

                if (data.success) {
                    displayExplainDeep(data.explanation);
                } else {
                    alert('Error: ' + data.error);
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
                <div class="review-output">${marked.parse(explanation)}</div>
            `;

            document.getElementById('results').style.display = 'block';
        }

        function backToReview() {
            if (savedHomeworkState && savedHomeworkState.reviewHTML) {
                document.getElementById('review-result').innerHTML = savedHomeworkState.reviewHTML;
            }
        }

        async function ImprovePractice() {
            // Check subscription first
            if (!await requireSubscription('Help me improve')) return;

            // Save current state (answers + review results), so it can be restored when returning
            saveCurrentState();

            // Collect all answers
            const answerInputs = document.querySelectorAll('.answer-input-inline');
            let allAnswers = [];

            answerInputs.forEach(input => {
                const subject = input.dataset.subject;
                const answer = input.value.trim();
                if (answer) {
                    allAnswers.push(`--- ${subject} ---\n${answer}`);
                }
            });

            const combinedAnswers = allAnswers.join('\n\n');

            if (!combinedAnswers.trim()) {
                alert('Please enter your answers first!');
                return;
            }

            const homework = currentHomework.map(h => h.content).join('\n\n');
            const subject = currentHomework[0]?.subject || 'Maths';

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
                        profile: { student_id: currentStudentId }, // Pass student_id for subscription check
                        review_feedback: reviewFeedback
                    })
                });

                if (response.status === 402) { // Payment Required - subscription required
                    alert('Subscription required for this feature.');
                    window.location.href = '/pricing';
                    return;
                }
                if (response.status === 401) { // Unauthorized - login required
                    alert('Please login or register to use this feature.');
                    window.location.href = '/login';
                    return;
                }

                const data = await response.json();

                if (data.success) {
                    displayPracticeQuestions(data.practice, subject);
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred during practice generation');
            } finally {
                hideLoading();
            }
        }

        function displayPracticeQuestions(practiceContent, subject) {
            // 将练习内容显示在题目区域，学生可以在旁边输入答案
            const container = document.getElementById('homework-results');

            // 保存练习内容用于后续批改
            currentPracticeContent = practiceContent;
            currentPracticeSubject = subject;
            isPracticeMode = true;

            container.innerHTML = `
                <div class="homework-block">
                    <h3 class="subject-header" style="background: linear-gradient(135deg, #f57c00 0%, #ff9800 100%);">
                        Practice - ${subject}
                    </h3>
                    <div class="homework-content">
                        <div class="question-column" style="border-left-color: #f57c00;">
                            ${marked.parse(practiceContent)}
                        </div>
                        <div class="answer-column">
                            <h4 style="color: #f57c00;">Your Answers:</h4>
                            <textarea class="answer-input-inline"
                                      id="practice-answer-input"
                                      style="border-color: #f57c00;"
                                      placeholder="Work through the practice questions above and write your answers here..."></textarea>
                        </div>
                    </div>
                </div>
            `;

            // 更新按钮区域
            const resultsCard = document.querySelector('#results .card');
            const buttonArea = resultsCard.querySelector('div[style*="text-align: center"]');
            if (buttonArea) {
                buttonArea.innerHTML = `
                    <button class="btn btn-primary" onclick="checkPracticeAnswers()" style="background: linear-gradient(135deg, #f57c00, #ff9800);">
                        Check Answers
                    </button>
                    <button class="btn btn-secondary" onclick="exitPracticeMode()">
                        Back to Homework
                    </button>
                `;
            }

            // 清空之前的批改结果
            document.getElementById('review-result').innerHTML = '';
            document.getElementById('results').style.display = 'block';
        }

        function checkPracticeAnswers() {
            const answerInput = document.getElementById('practice-answer-input');
            const answers = answerInput ? answerInput.value.trim() : '';

            if (!answers) {
                alert('Please write your answers first!');
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
                    profile: { student_id: currentStudentId } // Pass student_id for potential future use
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const container = document.getElementById('review-result');
                    container.innerHTML = `
                        <h3 style="margin-top: 30px; margin-bottom: 20px;">Practice Feedback</h3>
                        <div class="review-output" style="border-left-color: #f57c00;">${marked.parse(data.review)}</div>
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
            // 恢复原始按钮区域
            if (savedButtonsHTML) {
                const btnArea = document.getElementById('homework-buttons');
                if (btnArea) btnArea.innerHTML = savedButtonsHTML;
            }
            clearSavedState();
        }

        // ---- 学习进度追踪 ----

        async function TrackProgress() {
            // Check subscription first
            if (!await requireSubscription('Track Progress')) return;

            // Save current state to sessionStorage, so it can be restored when returning from pricing page
            const state = {
                homework: currentHomework,
                profile: currentProfile,
                subject: currentSubject,
                answers: {},
                reviewHTML: document.getElementById('review-result').innerHTML,
                mode: currentHomeworkMode, // Save current mode
                questionIndex: currentQuestionIndex, // Save current question index
                questionAnswers: currentQuestionAnswers // Save tutor mode answers
            };
            document.querySelectorAll('.answer-input-inline').forEach(input => {
                state.answers[input.dataset.subject] = input.value;
            });
            try {
                sessionStorage.setItem('homeworkState', JSON.stringify(state));
            } catch(e) {
                console.error('Failed to save state to sessionStorage:', e);
            }
            window.location.href = '/progress'; // Redirect to progress page
        }

        // ---- Admin Tools Functions ----
        let isDevMode = false; // Will be set by checkDevMode

        async function checkDevMode() {
            try {
                const response = await fetch('/api/admin/dev-mode-status'); // New endpoint to check dev mode
                const data = await response.json();
                isDevMode = data.is_dev_mode;
                const isAdmin = data.is_admin;
                if (isAdmin) {
                    document.getElementById('admin-tools-tab').style.display = 'block';
                } else {
                    document.getElementById('admin-tools-tab').style.display = 'none';
                }
            } catch (error) {
                console.error('Failed to check dev mode status:', error);
                isDevMode = false; // Assume not dev mode if check fails
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
