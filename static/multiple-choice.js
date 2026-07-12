(function () {
    'use strict';

    const originalDisplayHomework = window.displayHomework;
    const originalDisplayTutorQuestion = window.displayTutorQuestion;
    const originalRestoreSavedState = window.restoreSavedState;

    function cleanText(value) {
        return String(value || '')
            .trim()
            .replace(/^#{1,6}\s+/, '')
            .replace(/^\*\*(.*?)\*\*$/, '$1')
            .trim();
    }

    function renderMarkdown(value) {
        if (typeof window.renderSafeMarkdown === 'function') {
            return window.renderSafeMarkdown(String(value || ''));
        }
        if (window.marked && typeof window.marked.parse === 'function') {
            return window.marked.parse(String(value || ''));
        }
        return escapeHtml(value).replace(/\n/g, '<br>');
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function escapeAttribute(value) {
        return escapeHtml(value).replace(/`/g, '&#096;');
    }

    function parseMultipleChoiceQuestions(content) {
        if (!content) return [];

        const optionPattern = /^\s*(?:[-*]\s*)?(?:\*\*)?\(?([A-Ha-h])\)?[\)\].:\-](?:\*\*)?\s+(.+?)\s*$/;
        const questionPattern = /^\s*(?:\*\*)?(?:question\s*)?(\d+)[\)\].:\-](?:\*\*)?\s+(.+?)\s*$/i;
        const normalised = String(content)
            .replace(/\r\n?/g, '\n')
            .replace(/(\S)\s+(?=(?:\*\*)?\(?[A-Ha-h]\)?[\)\].:]\s+)/g, '$1\n');

        const questions = [];
        let current = null;
        let preface = [];

        function finishCurrent() {
            if (!current) return;
            const stem = cleanText(current.stemLines.join('\n'));
            if (stem && current.options.length >= 2) {
                questions.push({
                    number: current.number || questions.length + 1,
                    question: stem,
                    options: current.options
                });
            }
            current = null;
        }

        normalised.split('\n').forEach(function (rawLine) {
            const line = rawLine.trim();
            if (!line) return;

            const questionMatch = line.match(questionPattern);
            if (questionMatch) {
                finishCurrent();
                current = {
                    number: Number(questionMatch[1]),
                    stemLines: [cleanText(questionMatch[2])],
                    options: []
                };
                preface = [];
                return;
            }

            const optionMatch = line.match(optionPattern);
            if (optionMatch) {
                if (!current) {
                    current = {
                        number: questions.length + 1,
                        stemLines: preface.slice(-4),
                        options: []
                    };
                    preface = [];
                }
                current.options.push({
                    label: optionMatch[1].toUpperCase(),
                    text: cleanText(optionMatch[2])
                });
                return;
            }

            if (current) {
                if (current.options.length) {
                    const lastOption = current.options[current.options.length - 1];
                    lastOption.text = (lastOption.text + ' ' + cleanText(line)).trim();
                } else {
                    current.stemLines.push(cleanText(line));
                }
            } else {
                preface.push(cleanText(line));
            }
        });

        finishCurrent();
        return questions;
    }

    function normaliseOptions(options) {
        if (!Array.isArray(options)) return [];
        return options
            .map(function (option, index) {
                if (typeof option === 'string') {
                    return {
                        label: String.fromCharCode(65 + index),
                        text: cleanText(option)
                    };
                }
                return {
                    label: cleanText(option && option.label) || String.fromCharCode(65 + index),
                    text: cleanText(option && (option.text || option.value || option.answer))
                };
            })
            .filter(function (option) { return option.text; });
    }

    function getMultipleChoiceQuestions(homeworkItem) {
        if (!homeworkItem || !homeworkItem.is_eleven_plus) return [];

        if (Array.isArray(homeworkItem.questions)) {
            const structured = homeworkItem.questions.map(function (question, index) {
                return {
                    number: Number(question.number) || index + 1,
                    question: cleanText(question.question || question.question_text || ''),
                    options: normaliseOptions(question.options)
                };
            }).filter(function (question) {
                return question.question && question.options.length >= 2;
            });
            if (structured.length) return structured;
        }

        if (Array.isArray(homeworkItem.options)) {
            const options = normaliseOptions(homeworkItem.options);
            const questionText = cleanText(homeworkItem.question_text || '');
            if (questionText && options.length >= 2) {
                return [{ number: 1, question: questionText, options: options }];
            }
        }

        return parseMultipleChoiceQuestions(homeworkItem.content || '');
    }

    function optionInputName(homeworkIndex, questionIndex, tutorMode) {
        if (tutorMode) return 'tutor-multiple-choice-answer';
        return 'multiple-choice-' + homeworkIndex + '-' + questionIndex;
    }

    function renderQuestion(question, homeworkIndex, questionIndex, tutorMode, savedAnswer) {
        const groupName = optionInputName(homeworkIndex, questionIndex, tutorMode);
        const questionNumber = Number(question.number) || questionIndex + 1;
        const optionsHtml = question.options.map(function (option) {
            const answerValue = option.text;
            const checked = savedAnswer && savedAnswer === answerValue ? ' checked' : '';
            return '<label class="multiple-choice-option">' +
                '<input class="multiple-choice-input" type="radio"' +
                    ' name="' + escapeAttribute(groupName) + '"' +
                    ' value="' + escapeAttribute(answerValue) + '"' +
                    ' data-option-label="' + escapeAttribute(option.label) + '"' +
                    ' data-question-number="' + questionNumber + '"' + checked + '>' +
                '<span class="multiple-choice-option-body">' +
                    '<span class="multiple-choice-letter" aria-hidden="true">' + escapeHtml(option.label) + '</span>' +
                    '<span class="multiple-choice-option-text">' + renderMarkdown(option.text) + '</span>' +
                '</span>' +
            '</label>';
        }).join('');

        return '<fieldset class="multiple-choice-question" data-question-index="' + questionIndex + '">' +
            '<legend>' +
                '<span class="multiple-choice-question-number">Question ' + questionNumber + '</span>' +
                '<span class="multiple-choice-question-text">' + renderMarkdown(question.question) + '</span>' +
            '</legend>' +
            '<div class="multiple-choice-options">' + optionsHtml + '</div>' +
        '</fieldset>';
    }

    function renderMultipleChoiceBlock(homeworkItem, homeworkIndex) {
        const questions = getMultipleChoiceQuestions(homeworkItem);
        if (!questions.length) return '';

        const questionsHtml = questions.map(function (question, questionIndex) {
            return renderQuestion(question, homeworkIndex, questionIndex, false, '');
        }).join('');

        return '<div class="homework-block multiple-choice-block" data-homework-index="' + homeworkIndex + '">' +
            '<h3 class="subject-header">' + escapeHtml(homeworkItem.subject || '11+ Practice') +
                (homeworkItem.from_rag ? ' (Free - from library)' : '') + '</h3>' +
            '<div class="multiple-choice-list">' + questionsHtml + '</div>' +
            '<textarea class="answer-input-inline multiple-choice-answer-proxy" hidden' +
                ' aria-hidden="true" tabindex="-1"' +
                ' data-subject="' + escapeAttribute(homeworkItem.subject || 'Maths') + '"' +
                ' data-homework-index="' + homeworkIndex + '"></textarea>' +
        '</div>';
    }

    function renderStandardBlock(homeworkItem, homeworkIndex) {
        const parsed = renderMarkdown(homeworkItem.content || '');
        const formatted = typeof window.formatQuestions === 'function' ? window.formatQuestions(parsed) : parsed;
        return '<div class="homework-block" data-homework-index="' + homeworkIndex + '">' +
            '<h3 class="subject-header">' + escapeHtml(homeworkItem.subject || 'Homework') +
                (homeworkItem.from_rag ? ' (Free - from library)' : '') + '</h3>' +
            '<div class="homework-content">' +
                '<div class="question-column">' + formatted + '</div>' +
                '<div class="answer-column">' +
                    '<h4>Your Answer:</h4>' +
                    '<textarea class="answer-input-inline" placeholder="Write your answer here..."' +
                        ' data-subject="' + escapeAttribute(homeworkItem.subject || 'Maths') + '"' +
                        ' data-homework-index="' + homeworkIndex + '"></textarea>' +
                '</div>' +
            '</div>' +
        '</div>';
    }

    function syncHomeworkProxy(homeworkIndex) {
        const block = document.querySelector('.multiple-choice-block[data-homework-index="' + homeworkIndex + '"]');
        if (!block) return;
        const proxy = block.querySelector('.multiple-choice-answer-proxy');
        if (!proxy) return;

        const answers = [];
        block.querySelectorAll('.multiple-choice-question').forEach(function (questionElement, questionIndex) {
            const selected = questionElement.querySelector('.multiple-choice-input:checked');
            if (selected) {
                const number = selected.dataset.questionNumber || String(questionIndex + 1);
                answers.push(number + '. ' + selected.value);
            }
        });
        proxy.value = answers.join('\n');
    }

    function restoreHomeworkSelectionsFromProxy() {
        document.querySelectorAll('.multiple-choice-block').forEach(function (block) {
            const proxy = block.querySelector('.multiple-choice-answer-proxy');
            if (!proxy || !proxy.value.trim()) return;
            const answerMap = new Map();
            proxy.value.split(/\n+/).forEach(function (line) {
                const match = line.match(/^\s*(\d+)[\).]\s*(.+?)\s*$/);
                if (match) answerMap.set(match[1], match[2]);
            });
            block.querySelectorAll('.multiple-choice-input').forEach(function (input) {
                input.checked = answerMap.get(input.dataset.questionNumber) === input.value;
            });
        });
    }

    window.displayHomework = function (homeworkList) {
        const list = Array.isArray(homeworkList) ? homeworkList : [];
        const hasMultipleChoice = list.some(function (item) {
            return getMultipleChoiceQuestions(item).length > 0;
        });

        if (!hasMultipleChoice && typeof originalDisplayHomework === 'function') {
            originalDisplayHomework(homeworkList);
            return;
        }

        const container = document.getElementById('homework-results');
        container.innerHTML = list.map(function (homeworkItem, homeworkIndex) {
            const multipleChoiceHtml = renderMultipleChoiceBlock(homeworkItem, homeworkIndex);
            return multipleChoiceHtml || renderStandardBlock(homeworkItem, homeworkIndex);
        }).join('');

        container.querySelectorAll('.multiple-choice-input').forEach(function (input) {
            input.addEventListener('change', function () {
                const block = input.closest('.multiple-choice-block');
                if (block) syncHomeworkProxy(block.dataset.homeworkIndex);
            });
        });

        if (typeof window.showResults === 'function') window.showResults();
        const homeworkButtons = document.getElementById('homework-buttons');
        const tutorButtons = document.getElementById('tutor-mode-buttons');
        if (homeworkButtons) homeworkButtons.style.display = 'block';
        if (tutorButtons) tutorButtons.style.display = 'none';
    };

    window.displayTutorQuestion = function (index) {
        if (!Array.isArray(currentHomework) || index >= currentHomework.length) {
            alert('You have completed all questions!');
            if (typeof window.clearResults === 'function') window.clearResults();
            return;
        }

        const homeworkItem = currentHomework[index];
        const questions = getMultipleChoiceQuestions(homeworkItem);
        if (!questions.length && typeof originalDisplayTutorQuestion === 'function') {
            originalDisplayTutorQuestion(index);
            return;
        }

        const question = questions[0];
        const savedAnswer = currentQuestionAnswers[index] || '';
        const container = document.getElementById('homework-results');
        container.innerHTML = '<div class="homework-block multiple-choice-block tutor-multiple-choice-block">' +
            '<h3 class="subject-header">' + escapeHtml(homeworkItem.subject || '11+ Practice') +
                ' (Question ' + (index + 1) + ' of ' + currentHomework.length + ')' +
                (homeworkItem.from_rag ? ' (Free - from library)' : '') + '</h3>' +
            '<div class="multiple-choice-list">' +
                renderQuestion(question, index, 0, true, savedAnswer) +
            '</div>' +
            '<textarea class="answer-input-inline multiple-choice-answer-proxy" id="tutor-answer-input" hidden' +
                ' aria-hidden="true" tabindex="-1" data-subject="' +
                escapeAttribute(homeworkItem.subject || 'Maths') + '">' + escapeHtml(savedAnswer) + '</textarea>' +
        '</div>';

        const proxy = document.getElementById('tutor-answer-input');
        container.querySelectorAll('.multiple-choice-input').forEach(function (input) {
            input.addEventListener('change', function () {
                proxy.value = input.value;
                currentQuestionAnswers[index] = input.value;
            });
        });

        if (typeof window.showResults === 'function') window.showResults();
        const homeworkButtons = document.getElementById('homework-buttons');
        const tutorButtons = document.getElementById('tutor-mode-buttons');
        if (homeworkButtons) homeworkButtons.style.display = 'none';
        if (tutorButtons) tutorButtons.style.display = 'block';
        const reviewResult = document.getElementById('review-result');
        if (reviewResult) reviewResult.innerHTML = '';
    };

    // Always send the original RAG question position when Tutor Mode is reviewed.
    // The RAG metadata stores answers as an ordered list. Without question_index,
    // the backend can accidentally use answer 1 for a later question.
    window.reviewCurrentQuestion = async function () {
        const answerInput = document.getElementById('tutor-answer-input');
        const studentAnswer = answerInput ? answerInput.value.trim() : '';

        if (!studentAnswer) {
            alert('Please enter your answer for this question!');
            return;
        }

        currentQuestionAnswers[currentQuestionIndex] = studentAnswer;

        const homeworkItem = currentHomework[currentQuestionIndex];
        if (!homeworkItem) {
            alert('This question could not be found. Please generate the homework again.');
            return;
        }

        const sourceQuestionIndex = Number.isInteger(homeworkItem.question_index)
            ? homeworkItem.question_index
            : currentQuestionIndex;

        const requestBody = {
            // full_content keeps the original number, giving the backend a second,
            // text-based way to match the question if needed.
            homework: homeworkItem.full_content || homeworkItem.content || '',
            answers: studentAnswer,
            subject: homeworkItem.subject || 'Maths',
            profile: currentProfile || { student_id: currentStudentId },
            is_tutor_mode: true,
            from_rag: Boolean(homeworkItem.from_rag),
            homework_doc_id: homeworkItem.doc_id || null,
            question_index: sourceQuestionIndex,
            is_eleven_plus: Boolean(homeworkItem.is_eleven_plus)
        };

        if (typeof window.showLoading === 'function') window.showLoading();

        try {
            const response = await fetch('/api/review', {
                method: 'POST',
                credentials: 'same-origin',
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
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'The question could not be checked.');
            }

            if (typeof window.displayReview === 'function') {
                window.displayReview(data.review || '');
            }
        } catch (error) {
            console.error('Tutor review failed:', error);
            alert(error.message || 'An error occurred during review');
        } finally {
            if (typeof window.hideLoading === 'function') window.hideLoading();
        }
    };

    if (typeof originalRestoreSavedState === 'function') {
        window.restoreSavedState = function () {
            const restored = originalRestoreSavedState();
            restoreHomeworkSelectionsFromProxy();
            return restored;
        };
    }
})();
