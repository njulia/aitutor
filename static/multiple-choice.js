(function (root, factory) {
    'use strict';
    const api = factory(root || {});
    if (root) root.HomeworkQuestionRenderer = api;
    if (typeof module === 'object' && module.exports) module.exports = api;
}(typeof window !== 'undefined' ? window : globalThis, function (root) {
    'use strict';

    function cleanText(value) {
        return String(value || '')
            .trim()
            .replace(/^\s*#{1,6}\s+/, '')
            .replace(/^\s*\*\*(.*?)\*\*\s*$/, '$1')
            .trim();
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

    function renderMarkdown(value) {
        if (typeof root.renderSafeMarkdown === 'function') {
            return root.renderSafeMarkdown(String(value || ''));
        }
        if (root.marked && typeof root.marked.parse === 'function') {
            return root.marked.parse(String(value || ''));
        }
        return escapeHtml(value).replace(/\n/g, '<br>');
    }

    const questionPattern = /^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?(?:\*\*)?(?:(?:homework\s+)?question|q)?\s*\(?(\d+)\)?\s*(?:[\).:\-]|(?:\*\*)?\s*$)\s*(?:\*\*)?\s*(.*?)\s*$/i;
    const optionPattern = /^\s*(?:[-*]\s*)?(?:\*\*)?\(?([A-Ha-h])\)?\s*[\).:\-]\s*(?:\*\*)?\s*(.+?)\s*$/;
    const optionsLinePattern = /^\s*(?:\*\*)?options?(?:\*\*)?\s*:\s*(.*?)\s*$/i;
    const privateHeadingPattern = /^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:answers?|correct\s+answers?|answer\s+key|solutions?|explanations?|worked\s+(?:answers?|solutions?|explanations?))(?:\*\*)?\s*:?\s*$/i;
    const privateLinePattern = /^\s*(?:[-*]\s*)?(?:\*\*)?(?:correct\s+answer|answer|solution|explanation|worked\s+(?:answer|solution|explanation)|coaching\s+(?:strategy|tip)|(?:helpful|exam|11\+)?\s*tip)(?:\*\*)?\s*:/i;
    const genericHeadingPattern = /^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:questions?|practice\s+questions?|homework(?:\s+set)?|tasks?)(?:\*\*)?\s*:?\s*$/i;
    const contextTransitionPattern = /^(?:read|use|look at|study|refer to|for questions?\b|passage\b|the passage\b|read the (?:second|following|next))/i;

    function stripPrivateSections(content) {
        const kept = [];
        const lines = String(content || '').replace(/\r\n?/g, '\n').split('\n');
        for (const line of lines) {
            if (privateHeadingPattern.test(line)) break;
            kept.push(line);
        }
        return kept.join('\n').trim();
    }

    function normaliseInlineOptions(content) {
        return String(content || '')
            .replace(/\r\n?/g, '\n')
            .replace(/([^\n])\s+(?=(?:[-*]\s+)?(?:\*\*)?\(?[A-Ha-h]\)?[\).:]\s+)/g, '$1\n');
    }

    function splitCsvOptions(value) {
        const text = String(value || '').trim();
        if (!text) return [];
        const values = [];
        let current = '';
        let quote = '';
        for (let index = 0; index < text.length; index += 1) {
            const char = text[index];
            if ((char === '"' || char === "'") && (!quote || quote === char)) {
                quote = quote ? '' : char;
                current += char;
            } else if (char === ',' && !quote) {
                if (current.trim()) values.push(current.trim());
                current = '';
            } else {
                current += char;
            }
        }
        if (current.trim()) values.push(current.trim());
        if (values.length < 2 || values.length > 8) return [];
        return values.map(function (item, index) {
            return {label: String.fromCharCode(65 + index), text: cleanText(item)};
        });
    }

    function parseQuestionBlock(number, body) {
        const stemLines = [];
        const options = [];
        const trailingLines = [];
        let inOptions = false;
        let inTrailingContext = false;
        let gapAfterOptions = false;

        for (const rawLine of String(body || '').split('\n')) {
            const line = rawLine.trim();
            if (!line) {
                if (inOptions) gapAfterOptions = true;
                continue;
            }
            if (privateLinePattern.test(line) || privateHeadingPattern.test(line)) break;

            if (inTrailingContext) {
                trailingLines.push(cleanText(line));
                continue;
            }

            const optionsLine = line.match(optionsLinePattern);
            if (optionsLine) {
                inOptions = true;
                splitCsvOptions(optionsLine[1]).forEach(function (item) { options.push(item); });
                gapAfterOptions = false;
                continue;
            }

            const optionMatch = line.match(optionPattern);
            if (optionMatch) {
                inOptions = true;
                options.push({label: optionMatch[1].toUpperCase(), text: cleanText(optionMatch[2])});
                gapAfterOptions = false;
                continue;
            }

            const cleaned = cleanText(line);
            if (!cleaned || genericHeadingPattern.test(cleaned)) continue;
            if (inOptions && options.length) {
                const isContext = gapAfterOptions || contextTransitionPattern.test(cleaned);
                if (isContext) {
                    inTrailingContext = true;
                    trailingLines.push(cleaned);
                } else {
                    options[options.length - 1].text = (options[options.length - 1].text + ' ' + cleaned).trim();
                }
            } else {
                stemLines.push(cleaned);
            }
        }

        const stem = stemLines.join('\n').trim();
        const validOptions = options.filter(function (item) { return item.text; });
        if (!stem) return null;
        const result = {
            number: Number(number) || 1,
            question: stem,
            response_type: validOptions.length >= 2 ? 'single_choice' : 'text',
            options: validOptions.length >= 2 ? validOptions : []
        };
        const trailingContext = trailingLines.filter(Boolean).join('\n').trim();
        if (trailingContext) result._trailing_context = trailingContext;
        return result;
    }

    function parseQuestions(content) {
        const text = normaliseInlineOptions(stripPrivateSections(content));
        const lines = text.split('\n');
        const starts = [];
        lines.forEach(function (line, lineIndex) {
            const match = line.match(questionPattern);
            if (match) starts.push({lineIndex: lineIndex, number: Number(match[1]), firstLine: cleanText(match[2])});
        });

        if (!starts.length) {
            const fallback = lines.filter(function (line) { return !genericHeadingPattern.test(line); }).join('\n').trim();
            const parsed = fallback ? parseQuestionBlock(1, fallback) : null;
            return parsed ? [parsed] : [];
        }

        const intro = lines.slice(0, starts[0].lineIndex)
            .filter(function (line) { return line.trim() && !genericHeadingPattern.test(line); })
            .join('\n')
            .trim();
        const questions = [];
        let pendingContext = intro;
        starts.forEach(function (start, index) {
            const end = index + 1 < starts.length ? starts[index + 1].lineIndex : lines.length;
            const body = [];
            if (start.firstLine) body.push(start.firstLine);
            body.push.apply(body, lines.slice(start.lineIndex + 1, end));
            const parsed = parseQuestionBlock(start.number, body.join('\n'));
            if (parsed) {
                if (pendingContext) parsed.context = pendingContext;
                pendingContext = String(parsed._trailing_context || '').trim();
                delete parsed._trailing_context;
                questions.push(parsed);
            }
        });
        return questions;
    }

    function normaliseOptions(options) {
        if (!Array.isArray(options)) return [];
        return options.map(function (option, index) {
            if (typeof option === 'string') {
                return {label: String.fromCharCode(65 + index), text: cleanText(option)};
            }
            return {
                label: cleanText(option && option.label) || String.fromCharCode(65 + index),
                text: cleanText(option && (option.text || option.value || option.answer))
            };
        }).filter(function (option) { return option.text; });
    }

    function normaliseStructuredQuestion(question, index) {
        const options = normaliseOptions(question && question.options);
        return {
            number: Number(question && question.number) || index + 1,
            question: cleanText(question && (question.question || question.question_text || question.text || '')),
            context: cleanText(question && (question.context || question.passage || question.instructions || '')),
            response_type: options.length >= 2 ? 'single_choice' : 'text',
            options: options
        };
    }

    function getQuestions(homeworkItem) {
        if (!homeworkItem) return [];
        if (Array.isArray(homeworkItem.questions) && homeworkItem.questions.length) {
            const structured = homeworkItem.questions
                .map(normaliseStructuredQuestion)
                .filter(function (question) { return question.question; });
            if (structured.length) return structured;
        }
        if (Array.isArray(homeworkItem.options)) {
            const options = normaliseOptions(homeworkItem.options);
            const question = cleanText(homeworkItem.question_text || homeworkItem.question || '');
            if (question && options.length >= 2) {
                return [{number: 1, question: question, context: cleanText(homeworkItem.context || ''), response_type: 'single_choice', options: options}];
            }
        }
        return parseQuestions(homeworkItem.content || '');
    }

    function hasChoiceQuestions(homeworkItem) {
        return getQuestions(homeworkItem).some(function (question) {
            return question.response_type === 'single_choice' && question.options.length >= 2;
        });
    }

    function inputName(prefix, homeworkIndex, questionIndex) {
        return String(prefix || 'homework-choice') + '-' + homeworkIndex + '-' + questionIndex;
    }

    function answerMapFromValue(value, questions) {
        const map = new Map();
        const text = String(value || '').trim();
        if (!text) return map;
        text.split(/\n+/).forEach(function (line) {
            const match = line.match(/^\s*(\d+)[\).]\s*(.+?)\s*$/);
            if (match) map.set(match[1], match[2]);
        });
        if (!map.size && questions.length === 1) map.set(String(questions[0].number || 1), text);
        return map;
    }


    function chooseTextControl(question) {
        const text = String((question && question.question) || '').toLowerCase();
        const longAnswerHints = [
            'explain', 'describe', 'write a paragraph', 'write a story', 'write a sentence',
            'give reasons', 'show your working', 'how do you know', 'compare', 'summarise'
        ];
        const isLongAnswer = longAnswerHints.some(function (hint) { return text.indexOf(hint) !== -1; });
        if (isLongAnswer) return {tag: 'textarea', inputMode: '', placeholder: 'Write your answer here…'};

        const numericHints = /(?:calculate|work out|how many|how much|what is|total|difference|number|digit|\b[+×÷=−-]\b|\d\s*[+×÷−-]\s*\d)/i;
        const isNumeric = numericHints.test(String((question && question.question) || ''));
        return {
            tag: 'input',
            inputMode: isNumeric ? 'decimal' : 'text',
            placeholder: isNumeric ? 'Type your answer' : 'Type your answer here'
        };
    }

    function renderQuestion(question, homeworkIndex, questionIndex, config, savedAnswers) {
        const number = Number(question.number) || questionIndex + 1;
        const saved = savedAnswers.get(String(number)) || '';
        const heading = '<span class="multiple-choice-question-number">Question ' + number + '</span>' +
            '<span class="multiple-choice-question-text">' + renderMarkdown(question.question) + '</span>';
        const contextHtml = question.context
            ? '<div class="question-context">' + renderMarkdown(question.context) + '</div>'
            : '';
        let controlHtml = '';

        if (question.response_type === 'single_choice' && question.options.length >= 2) {
            const groupName = inputName(config.groupPrefix, homeworkIndex, questionIndex);
            const optionsHtml = question.options.map(function (option) {
                const checked = saved === option.text || saved === option.label || saved === ('Option ' + option.label) ? ' checked' : '';
                return '<label class="multiple-choice-option">' +
                    '<input class="multiple-choice-input question-response-control" type="radio"' +
                        ' name="' + escapeAttribute(groupName) + '"' +
                        ' value="' + escapeAttribute(option.text) + '"' +
                        ' data-option-label="' + escapeAttribute(option.label) + '"' + checked + '>' +
                    '<span class="multiple-choice-option-body">' +
                        '<span class="multiple-choice-letter" aria-hidden="true">' + escapeHtml(option.label) + '</span>' +
                        '<span class="multiple-choice-option-text">' + renderMarkdown(option.text) + '</span>' +
                    '</span>' +
                '</label>';
            }).join('');
            controlHtml = '<fieldset class="multiple-choice-question question-response-item" data-question-number="' + number + '" data-response-type="single_choice">' +
                '<legend>' + heading + '</legend>' +
                '<div class="multiple-choice-options">' + optionsHtml + '</div>' +
            '</fieldset>';
        } else {
            const control = chooseTextControl(question);
            const controlId = 'response-' + homeworkIndex + '-' + questionIndex;
            const inputMode = control.inputMode ? ' inputmode="' + control.inputMode + '"' : '';
            const answerControl = control.tag === 'textarea'
                ? '<textarea class="question-response-input question-response-control question-response-long" id="' + controlId + '" rows="3" placeholder="' + escapeAttribute(control.placeholder) + '">' + escapeHtml(saved) + '</textarea>'
                : '<input class="question-response-input question-response-control question-response-short" id="' + controlId + '" type="text"' + inputMode + ' autocomplete="off" spellcheck="false" placeholder="' + escapeAttribute(control.placeholder) + '" value="' + escapeAttribute(saved) + '">';
            controlHtml = '<section class="multiple-choice-question free-response-question question-response-item" data-question-number="' + number + '" data-response-type="text">' +
                '<div class="free-response-row">' +
                    '<div class="free-response-heading">' + heading + '</div>' +
                    '<div class="free-response-control-wrap">' +
                        '<label class="free-response-label" for="' + controlId + '">Answer</label>' +
                        answerControl +
                    '</div>' +
                '</div>' +
            '</section>';
        }
        return '<div class="question-response-group">' + contextHtml + controlHtml + '</div>';
    }

    function renderResponseBlock(homeworkItem, homeworkIndex, options) {
        const config = Object.assign({
            outerClass: 'homework-block question-response-block',
            headerClass: 'subject-header',
            headerText: homeworkItem.subject || 'Homework',
            groupPrefix: 'homework-choice',
            proxyId: '',
            proxyClass: 'answer-input-inline question-answer-proxy multiple-choice-answer-proxy',
            savedAnswer: '',
            showLibraryBadge: true
        }, options || {});
        const questions = getQuestions(homeworkItem);
        if (!questions.length) return '';
        const savedAnswers = answerMapFromValue(config.savedAnswer, questions);
        const questionsHtml = questions.map(function (question, questionIndex) {
            return renderQuestion(question, homeworkIndex, questionIndex, config, savedAnswers);
        }).join('');
        const proxyId = config.proxyId ? ' id="' + escapeAttribute(config.proxyId) + '"' : '';
        const badge = config.showLibraryBadge && homeworkItem.from_rag ? ' (Free - from library)' : '';
        return '<div class="' + escapeAttribute(config.outerClass) + '" data-homework-index="' + homeworkIndex + '"' +
                ' data-subject="' + escapeAttribute(homeworkItem.subject || 'Maths') + '">' +
            '<h3 class="' + escapeAttribute(config.headerClass) + '">' + escapeHtml(config.headerText) + escapeHtml(badge) + '</h3>' +
            '<div class="multiple-choice-list question-response-list">' + questionsHtml + '</div>' +
            '<textarea class="' + escapeAttribute(config.proxyClass) + '" hidden aria-hidden="true" tabindex="-1"' + proxyId +
                ' data-subject="' + escapeAttribute(homeworkItem.subject || 'Maths') + '"' +
                ' data-homework-index="' + homeworkIndex + '">' + escapeHtml(config.savedAnswer || '') + '</textarea>' +
        '</div>';
    }

    function syncBlock(block) {
        if (!block) return '';
        const proxy = block.querySelector('.question-answer-proxy');
        const answers = [];
        block.querySelectorAll('.question-response-item').forEach(function (item, index) {
            const number = item.dataset.questionNumber || String(index + 1);
            let value = '';
            if (item.dataset.responseType === 'single_choice') {
                const selected = item.querySelector('.multiple-choice-input:checked');
                value = selected ? selected.value.trim() : '';
            } else {
                const input = item.querySelector('.question-response-input');
                value = input ? input.value.trim() : '';
            }
            if (value) answers.push(number + '. ' + value);
        });
        const combined = answers.join('\n');
        if (proxy) proxy.value = combined;
        return combined;
    }

    function bindBlock(block, onChange) {
        if (!block) return;
        block.querySelectorAll('.question-response-control').forEach(function (control) {
            const eventName = control.matches('textarea, input[type="text"]') ? 'input' : 'change';
            control.addEventListener(eventName, function () {
                const value = syncBlock(block);
                if (typeof onChange === 'function') onChange(value, block);
            });
        });
        syncBlock(block);
    }

    function bindAll(container, onChange) {
        const rootElement = container || (root.document && root.document);
        if (!rootElement || !rootElement.querySelectorAll) return;
        rootElement.querySelectorAll('.question-response-block').forEach(function (block) {
            bindBlock(block, onChange);
        });
    }

    function restoreFromProxies(container) {
        const rootElement = container || (root.document && root.document);
        if (!rootElement || !rootElement.querySelectorAll) return;
        rootElement.querySelectorAll('.question-response-block').forEach(function (block) {
            const proxy = block.querySelector('.question-answer-proxy');
            if (!proxy || !proxy.value.trim()) return;
            const questions = Array.from(block.querySelectorAll('.question-response-item'));
            const map = answerMapFromValue(proxy.value, questions.map(function (item, index) {
                return {number: Number(item.dataset.questionNumber) || index + 1};
            }));
            questions.forEach(function (item, index) {
                const number = item.dataset.questionNumber || String(index + 1);
                const value = map.get(number) || '';
                if (item.dataset.responseType === 'single_choice') {
                    item.querySelectorAll('.multiple-choice-input').forEach(function (input) {
                        input.checked = input.value === value || input.dataset.optionLabel === value;
                    });
                } else {
                    const input = item.querySelector('.question-response-input');
                    if (input) input.value = value;
                }
            });
        });
    }

    function getBlockAnswer(block) {
        return syncBlock(block);
    }

    const api = {
        parseQuestions: parseQuestions,
        getQuestions: getQuestions,
        hasChoiceQuestions: hasChoiceQuestions,
        renderResponseBlock: renderResponseBlock,
        bindBlock: bindBlock,
        bindAll: bindAll,
        syncBlock: syncBlock,
        getBlockAnswer: getBlockAnswer,
        restoreFromProxies: restoreFromProxies
    };

    return api;
}));
